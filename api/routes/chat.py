"""
Route POST /api/chat — Endpoint principal du chatbot
"""

import json
import logging
import uuid
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
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

# Stockage des sessions en mémoire (dict session_id → ConversationMemory)
_sessions: dict[str, ConversationMemory] = {}


def get_session(session_id: str) -> ConversationMemory:
    """Retourne ou crée une session de mémoire conversationnelle."""
    if session_id not in _sessions:
        _sessions[session_id] = ConversationMemory()
        logger.info(f"Nouvelle session créée : {session_id}")
    return _sessions[session_id]


def _check_index() -> None:
    """Lève HTTPException 503 si l'index FAISS est absent."""
    if not index_exists():
        raise HTTPException(
            status_code=503,
            detail=(
                "L'index FAISS n'est pas disponible. "
                "Uploadez des documents via l'interface ou lancez : python ingest.py"
            ),
        )


def _check_categorie(categorie: str | None) -> None:
    """Lève HTTPException 422 si la catégorie est inconnue."""
    if not categorie:
        return
    from config import get_all_categories
    cats = get_all_categories()
    if categorie not in cats:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Catégorie invalide : « {categorie} ». "
                f"Catégories disponibles : {', '.join(cats.keys())}"
            ),
        )


def _internal_error(e: Exception, context: str) -> HTTPException:
    """
    Crée une HTTPException 500 sûre :
    - Logue la stack complète + un identifiant de corrélation côté serveur
    - N'expose PAS les détails techniques au client
    """
    ref = str(uuid.uuid4())[:8].upper()
    logger.error(f"[{ref}] {context} : {e}", exc_info=True)
    return HTTPException(
        status_code=500,
        detail=(
            f"Une erreur interne s'est produite (réf. {ref}). "
            "Réessayez dans quelques instants ou contactez le support si le problème persiste."
        ),
    )


# ============================================================
# POST /api/chat  (synchrone)
# ============================================================

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
        422: {"model": ErrorResponse, "description": "Requête invalide"},
        500: {"model": ErrorResponse, "description": "Erreur interne"},
    },
)
def chat(request: ChatRequest) -> ChatResponse:
    _check_index()
    _check_categorie(request.categorie)

    try:
        session_id = request.session_id or "default"
        memory     = get_session(session_id)
        rag        = get_rag_chain()
        result     = rag.ask(
            question  = request.question,
            memory    = memory,
            categorie = request.categorie,
        )
        sources = [SourceResponse(**src) for src in result["sources"]]
        return ChatResponse(
            answer     = result["answer"],
            sources    = sources,
            question   = result["question"],
            session_id = session_id,
            nb_sources = len(sources),
        )

    except HTTPException:
        raise  # re-propager sans modifier
    except Exception as e:
        raise _internal_error(e, "Erreur pipeline RAG (chat)")


# ============================================================
# POST /api/chat/stream  (SSE)
# ============================================================

@router.post(
    "/chat/stream",
    summary="Réponse en streaming (SSE)",
    description="Envoie les tokens au fur et à mesure via Server-Sent Events.",
)
async def chat_stream(request: ChatRequest):
    _check_index()
    _check_categorie(request.categorie)

    session_id = request.session_id or "default"
    memory     = get_session(session_id)
    rag        = get_rag_chain()

    async def generate():
        ref = str(uuid.uuid4())[:8].upper()
        try:
            async for event in rag.ask_stream(request.question, memory, request.categorie):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error(f"[{ref}] Erreur pipeline RAG (stream) : {e}", exc_info=True)
            error_payload = {
                "error": (
                    f"Une erreur s'est produite lors de la génération de la réponse (réf. {ref}). "
                    "Réessayez dans quelques instants."
                ),
                "done": True,
            }
            yield f"data: {json.dumps(error_payload, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":     "no-cache",
            "X-Accel-Buffering": "no",
            "Connection":        "keep-alive",
        },
    )


# ============================================================
# POST /api/chat/clear
# ============================================================

@router.post(
    "/chat/clear",
    summary="Effacer l'historique d'une session",
    description="Réinitialise la mémoire conversationnelle d'une session.",
)
def clear_memory(request: ClearMemoryRequest) -> dict:
    session_id = request.session_id
    try:
        if session_id in _sessions:
            _sessions[session_id].clear()
            logger.info(f"Session effacée : {session_id}")
            return {"message": f"Session '{session_id}' effacée.", "session_id": session_id}
        return {"message": f"Session '{session_id}' introuvable ou déjà vide.", "session_id": session_id}
    except Exception as e:
        raise _internal_error(e, f"Erreur lors de l'effacement de la session {session_id}")


# ============================================================
# GET /api/chat/sessions
# ============================================================

@router.get(
    "/chat/sessions",
    summary="Liste des sessions actives",
)
def get_sessions() -> dict:
    return {
        "sessions": [
            {"session_id": sid, "exchanges": mem.exchange_count}
            for sid, mem in _sessions.items()
        ],
        "total": len(_sessions),
    }
