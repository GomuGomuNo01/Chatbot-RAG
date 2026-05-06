"""
Chain : pipeline RAG complet avec LangChain + Groq
"""

import logging
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
        ("human", """
Historique de conversation :
{history}

Contexte documentaire :
{context}

Question : {question}

Réponds en te basant uniquement sur le contexte fourni.
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
        context = format_context_from_docs(documents)
        history = memory.format_for_prompt()

        # ---- Étape 4 : Appel LLM ----
        logger.info(
            f"Appel LLM avec {len(documents)} chunks "
            f"de contexte..."
        )
        answer = self.chain.invoke({
            "question": question,
            "context":  context,
            "history":  history
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