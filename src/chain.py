"""
chain.py — Pipeline RAG complet avec LangChain + Groq

Pipeline amélioré v2 :
  Question
    ↓ [1] expand_acronyms()        — CDI → CDI (contrat à durée indéterminée)
    ↓ [2] contextualize_query()    — "ses conditions ?" → "conditions du CDI ?"
    ↓ [3] multi_search()           — cherche avec query originale + query enrichie
    ↓ [4] format_context()         — mise en forme des chunks trouvés
    ↓ [5] LLM generation           — réponse structurée en Markdown
    ↓ [6] memory.add_exchange()    — mémorisation + extraction de topics
"""

import logging
import re
from typing import Optional, cast
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from src.retriever import search, multi_search, format_sources
from src.memory import ConversationMemory
from src.utils import format_context_from_docs
from src.query_processor import (
    expand_acronyms,
    build_search_query,
    build_search_query_async,
)
from config import (
    GROQ_API_KEY,
    GROQ_LLM_MODEL,
    GROQ_TEMPERATURE,
    GROQ_MAX_TOKENS,
    SYSTEM_PROMPT
)

logger = logging.getLogger(__name__)

# ── Détection de langue ───────────────────────────────────────

_EN_WORDS = {
    'what','how','does','can','the','are','why','when','where','which','who',
    'give','me','tell','explain','show','find','list','do','make','get','is',
    'was','were','will','would','could','should','have','has','had','been',
    'this','that','these','those','with','from','about','into','through',
    'during','before','after','above','below','between','each','few','more',
    'most','other','some','such','than','then','there','they','its','our',
}
_FR_WORDS = {
    'quoi','comment','pourquoi','quand','où','qui','quel','quelle','quels',
    'quelles','moi','expliquer','trouver','faire','les','des','une','que',
    'qu','je','tu','il','nous','vous','ils','elles','est','sont','était',
    'être','avoir','fait','peut','dois','doit','votre','notre','leur',
    'leurs','cette','cet','ces','sur','dans','avec','pour','par','mais',
    'donc','car','si','aussi','comme','plus','très','bien','tout','tous',
}


def _detect_lang(text: str) -> str:
    words = set(re.sub(r"[^\w\s]", "", text.lower()).split())
    en = len(words & _EN_WORDS)
    fr = len(words & _FR_WORDS)
    return "en" if en > fr else "fr"


def _lang_instruction(lang: str) -> str:
    if lang == "en":
        return (
            "\n\n⚠️ LANGUAGE RULE (mandatory): The user wrote in **English**. "
            "Your entire response MUST be in English only. "
            "Do not use French under any circumstances."
        )
    return ""


# ============================================================
# INITIALISATION DU LLM
# ============================================================

def get_llm() -> ChatGroq:
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY manquante. Vérifie ton fichier .env")
    return ChatGroq(
        api_key=GROQ_API_KEY,
        model=GROQ_LLM_MODEL,
        temperature=GROQ_TEMPERATURE,
        max_tokens=GROQ_MAX_TOKENS,
    )


# ============================================================
# PROMPT
# ============================================================

def build_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", """\
{history}
---
## Extraits documentaires disponibles
{context}

---
**Question :** {question}{lang_instruction}
""")
    ])


# ============================================================
# PIPELINE RAG
# ============================================================

class RAGChain:
    """
    Pipeline RAG complet :
      Question → QueryProcessor → MultiRetrieval → LLM → Réponse + Sources
    """

    def __init__(self):
        self.llm    = get_llm()
        self.prompt = build_prompt()
        self.parser = StrOutputParser()
        self.chain  = self.prompt | self.llm | self.parser
        logger.info("RAGChain v2 initialisée.")

    # ── Utilitaires internes ──────────────────────────────────

    def _build_search_queries(
        self,
        question: str,
        history_compact: str,
        *,
        is_stream: bool = False,
    ) -> list[str]:
        """
        Construit la liste de requêtes à envoyer au retriever.
        Toujours au moins [requête originale étendue].
        Si contextualisation utile : [originale étendue, requête contextualisée].
        """
        expanded = expand_acronyms(question)
        queries = [expanded]
        # La réécriture contextuelle synchrone (pour ask())
        if not is_stream:
            rewritten = build_search_query(question, history_compact, self.llm)
            if rewritten != expanded and rewritten not in queries:
                queries.append(rewritten)
        return queries

    async def _build_search_queries_async(
        self,
        question: str,
        history_compact: str,
    ) -> list[str]:
        """Version async pour ask_stream()."""
        expanded  = expand_acronyms(question)
        queries   = [expanded]
        rewritten = await build_search_query_async(question, history_compact, self.llm)
        if rewritten != expanded and rewritten not in queries:
            queries.append(rewritten)
        return queries

    def _no_result_answer(
        self,
        question: str,
        search_query: str,
        categorie: Optional[str],
        lang: str,
    ) -> str:
        """Message affiché quand aucun chunk pertinent n'est trouvé."""
        filtre = f" dans la catégorie « {categorie} »" if categorie else ""
        tip = (
            f"La recherche a porté sur : *{search_query}*\n\n"
            "Suggestions :\n"
            "- Reformulez votre question avec plus de mots-clés\n"
            "- Élargissez ou retirez le filtre de catégorie\n"
            "- Vérifiez que les documents sont bien indexés"
        ) if lang == "fr" else (
            f"Search was performed on: *{search_query}*\n\n"
            "Suggestions:\n"
            "- Rephrase with more keywords\n"
            "- Remove or broaden the category filter\n"
            "- Check that documents are indexed"
        )
        prefix = (
            f"Je n'ai pas trouvé d'information{filtre} correspondant à votre question.\n\n"
            if lang == "fr"
            else f"No information found{filtre} matching your question.\n\n"
        )
        return prefix + tip

    # ── Mode synchrone ────────────────────────────────────────

    def ask(
        self,
        question: str,
        memory: ConversationMemory,
        categorie: Optional[str] = None,
    ) -> dict:
        logger.info(f"Question : {question[:80]}")
        lang          = _detect_lang(question)
        history_text  = memory.format_for_prompt()
        compact_hist  = memory.format_compact()

        # ── [1+2] Construire les requêtes enrichies ─────────
        queries = self._build_search_queries(question, compact_hist)
        logger.info(f"Requêtes retrieval : {queries}")

        # ── [3] Multi-retrieval ──────────────────────────────
        documents = (
            multi_search(queries, categorie)
            if len(queries) > 1
            else search(queries[0], categorie)
        )

        if not documents:
            answer = self._no_result_answer(question, queries[0], categorie, lang)
            memory.add_exchange(question, answer)
            return {"answer": answer, "sources": [], "question": question}

        # ── [4] Contexte + prompt ────────────────────────────
        context  = format_context_from_docs(documents)
        lang_ins = _lang_instruction(lang)
        logger.info(f"Appel LLM — {len(documents)} chunks | lang={lang}")

        # ── [5] Génération ───────────────────────────────────
        answer = self.chain.invoke({
            "question":         question,   # question ORIGINALE pour la génération
            "context":          context,
            "history":          history_text,
            "lang_instruction": lang_ins,
        })

        # ── [6] Mémoire + sources ────────────────────────────
        sources = format_sources(documents)
        memory.add_exchange(question, answer)
        logger.info("Réponse générée.")
        return {"answer": answer, "sources": sources, "question": question}

    # ── Mode streaming ────────────────────────────────────────

    async def ask_stream(
        self,
        question: str,
        memory: ConversationMemory,
        categorie: Optional[str] = None,
    ):
        logger.info(f"[STREAM] Question : {question[:80]}")
        lang         = _detect_lang(question)
        history_text = memory.format_for_prompt()
        compact_hist = memory.format_compact()

        # ── [1+2] Requêtes enrichies (async) ─────────────────
        queries = await self._build_search_queries_async(question, compact_hist)
        logger.info(f"[STREAM] Requêtes retrieval : {queries}")

        # ── [3] Multi-retrieval ───────────────────────────────
        documents = (
            multi_search(queries, categorie)
            if len(queries) > 1
            else search(queries[0], categorie)
        )

        if not documents:
            answer = self._no_result_answer(question, queries[0], categorie, lang)
            memory.add_exchange(question, answer)
            yield {"token": answer}
            yield {"sources": [], "question": question, "done": True}
            return

        # ── [4] Contexte + prompt ─────────────────────────────
        context  = format_context_from_docs(documents)
        lang_ins = _lang_instruction(lang)
        full_ans = ""
        logger.info(f"[STREAM] LLM — {len(documents)} chunks | lang={lang}")

        # ── [5] Génération en streaming ───────────────────────
        async for token in self.chain.astream({
            "question":         question,
            "context":          context,
            "history":          history_text,
            "lang_instruction": lang_ins,
        }):
            full_ans += token
            yield {"token": token}

        # ── [6] Mémoire + sources ─────────────────────────────
        sources = format_sources(documents)
        memory.add_exchange(question, full_ans)
        logger.info("[STREAM] Terminé.")
        yield {"sources": sources, "question": question, "done": True}


# ============================================================
# SINGLETON
# ============================================================

_rag_chain_instance: Optional[RAGChain] = None


def get_rag_chain() -> RAGChain:
    global _rag_chain_instance
    if _rag_chain_instance is None:
        _rag_chain_instance = RAGChain()
    return cast(RAGChain, _rag_chain_instance)
