"""
Chain : pipeline RAG complet avec LangChain + Groq
"""

import logging
import re
from typing import Optional, cast
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from src.retriever import search, format_sources
from src.memory import ConversationMemory
from src.utils import format_context_from_docs
from config import (
    GROQ_API_KEY,
    GROQ_LLM_MODEL,
    GROQ_TEMPERATURE,
    GROQ_MAX_TOKENS,
    SYSTEM_PROMPT
)

logger = logging.getLogger(__name__)

# Mots fréquents anglais absents du français courant
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
    """Détecte la langue dominante (fr/en) par fréquence de mots marqueurs."""
    words = set(re.sub(r"[^\w\s]", "", text.lower()).split())
    en = len(words & _EN_WORDS)
    fr = len(words & _FR_WORDS)
    return "en" if en > fr else "fr"


def _lang_instruction(lang: str) -> str:
    """Retourne une consigne de langue explicite à injecter dans le prompt."""
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
    """Initialise et retourne le LLM Groq."""
    if not GROQ_API_KEY:
        raise ValueError(
            "GROQ_API_KEY manquante. "
            "Vérifie ton fichier .env"
        )

    return ChatGroq(
        api_key=GROQ_API_KEY,
        model=GROQ_LLM_MODEL,
        temperature=GROQ_TEMPERATURE,
        max_tokens=GROQ_MAX_TOKENS
    )


# ============================================================
# CONSTRUCTION DU PROMPT
# ============================================================

def build_prompt() -> ChatPromptTemplate:
    """Construit le template de prompt RAG."""
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
# PIPELINE RAG PRINCIPAL
# ============================================================

class RAGChain:
    """
    Pipeline RAG complet :
    Question → Retrieval → Prompt → LLM → Réponse + Sources
    """

    def __init__(self):
        self.llm     = get_llm()
        self.prompt  = build_prompt()
        self.parser  = StrOutputParser()
        self.chain   = self.prompt | self.llm | self.parser
        logger.info("RAGChain initialisée avec succès.")

    def ask(
        self,
        question: str,
        memory: ConversationMemory,
        categorie: Optional[str] = None
    ) -> dict:
        """
        Pose une question et retourne la réponse avec ses sources.

        Args:
            question  : question de l'utilisateur
            memory    : historique conversationnel
            categorie : filtre optionnel de catégorie

        Returns:
            dict avec :
                - answer   : réponse générée
                - sources  : liste des sources utilisées
                - question : question originale
        """
        logger.info(f"Question reçue : {question[:80]}")

        # ---- Étape 1 : Retrieval ----
        documents = search(
            query=question,
            categorie=categorie
        )

        # ---- Étape 2 : Vérifier si des docs pertinents existent ----
        if not documents:
            filtre = f" dans la catégorie « {categorie} »" if categorie else ""
            answer = (
                f"Je n'ai pas trouvé d'information{filtre} "
                "correspondant à votre question dans les documents disponibles. "
                "Essayez de reformuler votre question, d'élargir le filtre de catégorie, "
                "ou vérifiez que les documents sont bien indexés (python ingest.py)."
            )
            memory.add_exchange(question, answer)
            return {
                "answer":   answer,
                "sources":  [],
                "question": question
            }

        # ---- Étape 3 : Construire le contexte ----
        context  = format_context_from_docs(documents)
        history  = memory.format_for_prompt()
        lang     = _detect_lang(question)
        lang_ins = _lang_instruction(lang)
        logger.info(f"Langue détectée : {lang}")

        # ---- Étape 4 : Appel LLM ----
        logger.info(f"Appel LLM avec {len(documents)} chunks de contexte…")
        answer = self.chain.invoke({
            "question":        question,
            "context":         context,
            "history":         history,
            "lang_instruction": lang_ins,
        })

        # ---- Étape 5 : Formater les sources ----
        sources = format_sources(documents)

        # ---- Étape 6 : Sauvegarder dans la mémoire ----
        memory.add_exchange(question, answer)

        logger.info("Réponse générée avec succès.")

        return {
            "answer":   answer,
            "sources":  sources,
            "question": question
        }

    async def ask_stream(
        self,
        question: str,
        memory: ConversationMemory,
        categorie: Optional[str] = None
    ):
        """
        Version streaming : génère les tokens un par un via SSE.
        Yields des dicts : {"token": str} puis {"sources": list, "done": True}
        """
        logger.info(f"[STREAM] Question : {question[:80]}")

        documents = search(query=question, categorie=categorie)

        if not documents:
            filtre = f" dans la catégorie « {categorie} »" if categorie else ""
            answer = (
                f"Je n'ai pas trouvé d'information{filtre} "
                "correspondant à votre question dans les documents disponibles. "
                "Essayez de reformuler votre question ou d'élargir le filtre de catégorie."
            )
            memory.add_exchange(question, answer)
            yield {"token": answer}
            yield {"sources": [], "question": question, "done": True}
            return

        context  = format_context_from_docs(documents)
        history  = memory.format_for_prompt()
        lang     = _detect_lang(question)
        lang_ins = _lang_instruction(lang)
        full_ans = ""
        logger.info(f"[STREAM] Langue détectée : {lang} — appel LLM avec {len(documents)} chunks…")

        async for token in self.chain.astream({
            "question":         question,
            "context":          context,
            "history":          history,
            "lang_instruction": lang_ins,
        }):
            full_ans += token
            yield {"token": token}

        sources = format_sources(documents)
        memory.add_exchange(question, full_ans)
        logger.info("[STREAM] Réponse complète envoyée.")
        yield {"sources": sources, "question": question, "done": True}


# ============================================================
# INSTANCE GLOBALE (singleton)
# ============================================================

_rag_chain_instance: Optional[RAGChain] = None


def get_rag_chain() -> RAGChain:
    """Retourne l'instance RAGChain (singleton)."""
    global _rag_chain_instance
    if _rag_chain_instance is None:
        _rag_chain_instance = RAGChain()
    return cast(RAGChain, _rag_chain_instance)