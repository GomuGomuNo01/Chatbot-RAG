"""
Route POST /api/chat — Endpoint principal du chatbot
"""

import logging
from fastapi import APIRouter, HTTPException
from api.schemas import (
    ChatRequest,
    ChatResponse,
    ClearMemoryRequest,
    SourceResponse,
    ErrorResponse
)
from src.chain import get_rag_chain
from src.memory import ConversationMemory
from src.indexer import index_exists

logger = logging.getLogger(__name__)
router = APIRouter()

# Stockage des sessions en mémoire
# (dict session_id → ConversationMemory)
_sessions: dict[str, ConversationMemory] = {}


def get_session(session_id: str) -> ConversationMemory:
    """Retourne ou crée une session de mémoire conversationnelle."""
    if session_id not in _sessions:
        _sessions[session_id] = ConversationMemory()
        logger.info(f"Nouvelle session créée : {session_id}")
    return _sessions[session_id]


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Poser une question au chatbot",
    description=(
        "Envoie une question et reçoit une réponse générée "
        "par RAG avec les sources citées."
    ),
    responses={
        503: {"model": ErrorResponse, "description": "Index non disponible"},
        422: {"model": ErrorResponse, "description": "Requête invalide"}
    }
)
def chat(request: ChatRequest) -> ChatResponse:

    # Vérifier que l'index existe
    if not index_exists():
        raise HTTPException(
            status_code=503,
            detail=(
                "L'index FAISS n'est pas disponible. "
                "Lance python ingest.py d'abord."
            )
        )

    # Valider la catégorie si fournie
    from config import CATEGORIES
    if request.categorie and request.categorie not in CATEGORIES:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Catégorie invalide : {request.categorie}. "
                f"Valeurs acceptées : {list(CATEGORIES.keys())}"
            )
        )

    try:
        # Récupérer la session
        session_id = request.session_id or "default"
        memory     = get_session(session_id)

        # Appel RAG
        rag    = get_rag_chain()
        result = rag.ask(
            question=request.question,
            memory=memory,
            categorie=request.categorie
        )

        # Formater les sources
        sources = [
            SourceResponse(**src)
            for src in result["sources"]
        ]

        return ChatResponse(
            answer     = result["answer"],
            sources    = sources,
            question   = result["question"],
            session_id = session_id,
            nb_sources = len(sources)
        )

    except Exception as e:
        logger.error(f"Erreur lors du traitement : {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Erreur interne : {str(e)}"
        )


@router.post(
    "/chat/clear",
    summary="Effacer l'historique d'une session",
    description="Réinitialise la mémoire conversationnelle d'une session."
)
def clear_memory(request: ClearMemoryRequest) -> dict:
    session_id = request.session_id
    if session_id in _sessions:
        _sessions[session_id].clear()
        return {
            "message":    f"Session '{session_id}' effacée.",
            "session_id": session_id
        }
    return {
        "message":    f"Session '{session_id}' introuvable ou déjà vide.",
        "session_id": session_id
    }


@router.get(
    "/chat/sessions",
    summary="Liste des sessions actives"
)
def get_sessions() -> dict:
    return {
        "sessions": [
            {
                "session_id": sid,
                "exchanges":  mem.exchange_count
            }
            for sid, mem in _sessions.items()
        ],
        "total": len(_sessions)
    }