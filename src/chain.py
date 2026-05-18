"""
chain.py — Pipeline RAG complet (refonte v2).

Pipeline générique, sans biais domaine :

  Question
    ↓ [0] Détection langue
    ↓ [1] Cache sémantique : hit ?  → réponse directe
    ↓ [2] Expand acronyms + décomposition comparative + réécriture contextuelle
    ↓ [3] Recherche hybride (FAISS + BM25) + RRF + reranking
    ↓ [4] Construction du contexte
    ↓ [5] Génération LLM (Claude)
    ↓ [6] Stockage cache + mémoire conversationnelle
"""

import logging
import re
from typing import cast

from config import (
    ANTHROPIC_API_KEY,
    ANTHROPIC_MAX_TOKENS,
    ANTHROPIC_MODEL,
    ANTHROPIC_TEMPERATURE,
    SYSTEM_PROMPT,
)
from langchain_anthropic import ChatAnthropic
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from src.cache import get_cache
from src.embedder import get_embeddings
from src.memory import ConversationMemory
from src.query_processor import (
    build_search_query,
    build_search_query_async,
    decompose_comparative_query,
    expand_acronyms,
    extract_article_queries,
)
from src.retriever import format_sources, hybrid_search
from src.utils import format_context_from_docs

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# Détection rapide de langue
# ──────────────────────────────────────────────────────────────

_EN_WORDS = frozenset(
    {
        "what",
        "how",
        "does",
        "can",
        "the",
        "are",
        "why",
        "when",
        "where",
        "which",
        "who",
        "give",
        "me",
        "tell",
        "explain",
        "show",
        "find",
        "list",
        "do",
        "make",
        "is",
        "was",
        "were",
        "will",
        "would",
        "could",
        "should",
        "have",
        "has",
        "this",
        "that",
        "these",
        "with",
        "from",
        "about",
        "into",
        "their",
        "them",
    }
)
_FR_WORDS = frozenset(
    {
        "quoi",
        "comment",
        "pourquoi",
        "quand",
        "où",
        "qui",
        "quel",
        "quelle",
        "quels",
        "quelles",
        "moi",
        "expliquer",
        "trouver",
        "faire",
        "les",
        "des",
        "une",
        "que",
        "qu",
        "je",
        "tu",
        "il",
        "nous",
        "vous",
        "ils",
        "elles",
        "est",
        "sont",
        "était",
        "être",
        "avoir",
        "fait",
        "peut",
        "doit",
        "votre",
        "notre",
        "leur",
        "cette",
        "cet",
        "ces",
        "sur",
        "dans",
        "avec",
        "pour",
    }
)


def _detect_lang(text: str) -> str:
    words = set(re.sub(r"[^\w\s]", "", text.lower()).split())
    return "en" if len(words & _EN_WORDS) > len(words & _FR_WORDS) else "fr"


def _lang_instruction(lang: str) -> str:
    if lang == "en":
        return (
            "\n\n⚠️ LANGUAGE RULE (mandatory): the user wrote in **English**. "
            "Your entire response MUST be in English only."
        )
    return ""


# ──────────────────────────────────────────────────────────────
# LLM
# ──────────────────────────────────────────────────────────────


def get_llm() -> ChatAnthropic:
    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY manquante. Ajoute ta clé dans le fichier .env")
    logger.info(f"LLM : Claude ({ANTHROPIC_MODEL})")
    return ChatAnthropic(
        api_key=ANTHROPIC_API_KEY,
        model=ANTHROPIC_MODEL,
        temperature=ANTHROPIC_TEMPERATURE,
        max_tokens=ANTHROPIC_MAX_TOKENS,
    )


def build_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            (
                "human",
                """\
{history}
---
## Extraits documentaires disponibles
{context}

---
**Question :** {question}{lang_instruction}
""",
            ),
        ]
    )


# ──────────────────────────────────────────────────────────────
# Helpers internes
# ──────────────────────────────────────────────────────────────


def _safe_embed_query(text: str) -> list[float]:
    """Embed une question pour le cache. Retourne [] si l'embedder est indisponible."""
    try:
        return get_embeddings().embed_query(text)
    except Exception as e:
        logger.warning(f"[chain] Embedding question échoué : {e}")
        return []


_MAX_QUERIES = 3  # limite le nb d'appels retriever pour économiser les ressources


def _build_queries(question: str) -> list[str]:
    """Construit la liste de reformulations envoyées au retriever hybride."""
    expanded = expand_acronyms(question)
    queries: list[str] = [expanded]
    for sq in decompose_comparative_query(question):
        if sq not in queries:
            queries.append(sq)
        if len(queries) >= _MAX_QUERIES:
            break
    if len(queries) < _MAX_QUERIES:
        for sq in extract_article_queries(question):
            if sq not in queries:
                queries.append(sq)
            if len(queries) >= _MAX_QUERIES:
                break
    return queries


_NO_ANSWER_PATTERNS = (
    # Français
    "je n'ai pas trouvé",
    "aucune information",
    "pas d'information",
    "n'est pas mentionné",
    "ne figure pas",
    "ne contiennent pas",
    "ne mentionnent pas",
    "ne précisent pas",
    "les documents ne",
    "les extraits ne",
    "aucun extrait",
    "information n'est pas disponible",
    "n'apparaît pas",
    # English
    "no information",
    "not found in",
    "not mentioned in",
    "the documents do not",
    "the context does not",
    "cannot find",
    "I could not find",
)


def _is_no_answer(text: str) -> bool:
    """Détecte si la réponse LLM indique une absence d'information dans les documents."""
    low = text.lower()
    return any(p.lower() in low for p in _NO_ANSWER_PATTERNS)


_MAX_DISPLAY_SOURCES = 3


def _promote_cited_sources(answer: str, sources: list[dict]) -> list[dict]:
    """
    Réordonne les sources pour mettre en tête celles dont le nom de fichier
    est explicitement mentionné dans la réponse du LLM.
    Cas typique : le LLM cite "Curriculum_vitae_X.pdf" dans sa réponse mais le
    Code du Travail (énorme document) a un rrf_score plus élevé grâce à BM25 —
    on corrige en promouvant la source réellement utilisée.
    Renormalise les scores dans l'ensemble final de 3 sources.
    """
    if not answer or not sources:
        return sources[:_MAX_DISPLAY_SOURCES]

    low = answer.lower()
    mentioned: list[dict] = []
    other: list[dict] = []

    for s in sources:
        fname = s["fichier"].lower()
        stem = fname.rsplit(".", 1)[0].replace("_", " ").replace("-", " ")
        if fname in low or stem in low:
            mentioned.append(s)
        else:
            other.append(s)

    # Si le LLM cite explicitement des sources, n'afficher que celles-là.
    # Les sources non citées (ex: Code du Travail récupéré par BM25 mais
    # non utilisé dans la réponse) ne sont ajoutées qu'en l'absence de citations.
    if mentioned:
        reordered = mentioned[:_MAX_DISPLAY_SOURCES]
    else:
        reordered = other[:_MAX_DISPLAY_SOURCES]

    return reordered


def _no_result_answer(question: str, query: str, workspace: str | None, lang: str) -> str:
    filtre = f" dans le workspace « {workspace} »" if workspace else ""
    if lang == "fr":
        return (
            f"Je n'ai pas trouvé d'information{filtre} correspondant à votre question.\n\n"
            f"La recherche a porté sur : *{query}*\n\n"
            "Suggestions :\n"
            "- Reformulez avec plus de mots-clés\n"
            "- Retirez le filtre de workspace\n"
            "- Vérifiez que les documents sont bien indexés"
        )
    return (
        f"No information found{filtre} matching your question.\n\n"
        f"Search was performed on: *{query}*\n\n"
        "Suggestions:\n"
        "- Rephrase with more keywords\n"
        "- Remove the workspace filter\n"
        "- Check that documents are indexed"
    )


# ──────────────────────────────────────────────────────────────
# RAG Chain
# ──────────────────────────────────────────────────────────────


class RAGChain:
    def __init__(self) -> None:
        self.llm = get_llm()
        self.prompt = build_prompt()
        self.parser = StrOutputParser()
        self.chain = self.prompt | self.llm | self.parser
        self.cache = get_cache()
        logger.info("RAGChain v2 initialisée.")

    # ── Sync ──
    def ask(
        self,
        question: str,
        memory: ConversationMemory,
        workspace: str | None = None,
    ) -> dict:
        logger.info(f"Question : {question[:80]}")
        lang = _detect_lang(question)
        history_text = memory.format_for_prompt()
        compact_hist = memory.format_compact()

        # [1] Cache sémantique
        q_embed = _safe_embed_query(question)
        cached = self.cache.lookup(question, workspace, q_embed)
        if cached:
            answer = cached["answer"]
            sources = cached.get("sources", [])
            memory.add_exchange(question, answer)
            return {
                "answer": answer,
                "sources": sources,
                "question": question,
                "from_cache": True,
            }

        # [2] Construction des requêtes (acronymes + comparatif + contextuel)
        queries = _build_queries(question)
        rewritten = build_search_query(question, compact_hist, self.llm)
        if rewritten and rewritten != queries[0] and rewritten not in queries:
            queries.append(rewritten)
            for sq in decompose_comparative_query(rewritten):
                if sq not in queries:
                    queries.append(sq)
        logger.info(f"Requêtes retrieval ({len(queries)}) : {queries}")

        # [3] Recherche hybride
        documents = hybrid_search(queries, workspace=workspace)

        if not documents:
            answer = _no_result_answer(question, queries[0], workspace, lang)
            memory.add_exchange(question, answer)
            return {"answer": answer, "sources": [], "question": question, "from_cache": False}

        # [4] Contexte + [5] génération LLM
        context = format_context_from_docs(documents)
        lang_ins = _lang_instruction(lang)
        logger.info(f"Appel LLM — {len(documents)} chunks | lang={lang}")

        answer = self.chain.invoke(
            {
                "question": question,
                "context": context,
                "history": history_text,
                "lang_instruction": lang_ins,
            }
        )

        # [6] Mémoire + cache
        if _is_no_answer(answer):
            sources = []
        else:
            raw = format_sources(documents, max_sources=9)
            sources = _promote_cited_sources(answer, raw)
        memory.add_exchange(question, answer)
        self.cache.store(question, workspace, q_embed, answer, sources)
        logger.info("Réponse générée.")
        return {"answer": answer, "sources": sources, "question": question, "from_cache": False}

    # ── Async (streaming) ──
    async def ask_stream(
        self,
        question: str,
        memory: ConversationMemory,
        workspace: str | None = None,
    ):
        logger.info(f"[STREAM] Question : {question[:80]}")
        lang = _detect_lang(question)
        history_text = memory.format_for_prompt()
        compact_hist = memory.format_compact()

        # Cache hit → on stream la réponse cachée en un seul token (rapide)
        q_embed = _safe_embed_query(question)
        cached = self.cache.lookup(question, workspace, q_embed)
        if cached:
            memory.add_exchange(question, cached["answer"])
            yield {"token": cached["answer"], "from_cache": True}
            yield {
                "sources": cached.get("sources", []),
                "question": question,
                "done": True,
                "from_cache": True,
            }
            return

        # Construction des requêtes
        queries = _build_queries(question)
        rewritten = await build_search_query_async(question, compact_hist, self.llm)
        if rewritten and rewritten != queries[0] and rewritten not in queries:
            queries.append(rewritten)
            for sq in decompose_comparative_query(rewritten):
                if sq not in queries:
                    queries.append(sq)
        logger.info(f"[STREAM] Requêtes retrieval ({len(queries)}) : {queries}")

        documents = hybrid_search(queries, workspace=workspace)

        if not documents:
            answer = _no_result_answer(question, queries[0], workspace, lang)
            memory.add_exchange(question, answer)
            yield {"token": answer}
            yield {"sources": [], "question": question, "done": True}
            return

        context = format_context_from_docs(documents)
        lang_ins = _lang_instruction(lang)
        logger.info(f"[STREAM] LLM — {len(documents)} chunks | lang={lang}")

        # Retry sur overloaded_error Anthropic (transitoire, max 2 tentatives).
        # On ne réessaie que si aucun token n'a encore été émis.
        full_ans = ""
        _inputs = {
            "question": question,
            "context": context,
            "history": history_text,
            "lang_instruction": lang_ins,
        }
        for _attempt in range(3):
            try:
                async for token in self.chain.astream(_inputs):
                    full_ans += token
                    yield {"token": token}
                break  # succès
            except Exception as _exc:
                _is_overloaded = "overloaded" in str(_exc).lower()
                if _is_overloaded and not full_ans and _attempt < 2:
                    import asyncio as _asyncio

                    _wait = 2**_attempt
                    logger.warning(
                        f"[LLM] Anthropic surchargé "
                        f"(tentative {_attempt + 1}/3) — reprise dans {_wait}s…"
                    )
                    await _asyncio.sleep(_wait)
                else:
                    raise

        if _is_no_answer(full_ans):
            sources = []
        else:
            raw = format_sources(documents, max_sources=9)
            sources = _promote_cited_sources(full_ans, raw)
        memory.add_exchange(question, full_ans)
        self.cache.store(question, workspace, q_embed, full_ans, sources)
        logger.info("[STREAM] Terminé.")
        yield {"sources": sources, "question": question, "done": True}


# ──────────────────────────────────────────────────────────────
# Singleton
# ──────────────────────────────────────────────────────────────

_rag_chain_instance: RAGChain | None = None


def get_rag_chain() -> RAGChain:
    global _rag_chain_instance
    if _rag_chain_instance is None:
        _rag_chain_instance = RAGChain()
    return cast(RAGChain, _rag_chain_instance)


def reset_rag_chain() -> None:
    global _rag_chain_instance
    _rag_chain_instance = None
