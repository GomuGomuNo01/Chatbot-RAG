"""
Route /api/chat — endpoint principal du chatbot (refonte v2).

Le paramètre `categorie` devient `workspace`. Plus aucune catégorie native.
"""

import json
import logging
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from api.schemas import ChatRequest, ChatResponse, ClearMemoryRequest, ErrorResponse, SourceResponse
from src.chain import get_rag_chain
from src.indexer import index_exists
from src.memory import ConversationMemory
from src.rate_limiter import check_limit, get_limit, get_today_count, increment, status as rate_status

logger = logging.getLogger(__name__)
router = APIRouter()

# Sessions en mémoire (session_id → ConversationMemory)
_sessions: dict[str, ConversationMemory] = {}


def get_session(session_id: str) -> ConversationMemory:
    if session_id not in _sessions:
        _sessions[session_id] = ConversationMemory()
        logger.info(f"Nouvelle session : {session_id}")
    return _sessions[session_id]


def _check_index() -> None:
    if not index_exists():
        raise HTTPException(
            status_code=503,
            detail=(
                "L'index documentaire n'est pas disponible. "
                "Uploadez des documents via l'interface ou lancez : python ingest.py"
            ),
        )


def _check_rate_limit(from_cache: bool = False) -> None:
    allowed, count, limit = check_limit()
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Limite journalière atteinte ({count}/{limit} requêtes). "
                "Revenez demain ou augmentez DAILY_REQUEST_LIMIT dans votre .env"
            ),
        )


def _check_workspace(workspace: str | None) -> None:
    if not workspace:
        return
    from config import get_workspaces

    workspaces = get_workspaces()
    if workspace not in workspaces:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Workspace invalide : « {workspace} ». "
                f"Workspaces disponibles : {', '.join(workspaces.keys()) or 'aucun'}"
            ),
        )


def _internal_error(e: Exception, context: str) -> HTTPException:
    ref = str(uuid.uuid4())[:8].upper()
    logger.error(f"[{ref}] {context} : {e}", exc_info=True)
    return HTTPException(
        status_code=500,
        detail=(
            f"Une erreur interne s'est produite (réf. {ref}). "
            "Réessayez dans quelques instants."
        ),
    )


# ============================================================
# POST /api/chat
# ============================================================


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Poser une question au chatbot",
    responses={
        503: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
def chat(request: ChatRequest) -> ChatResponse:
    _check_index()
    _check_workspace(request.workspace)
    _check_rate_limit()

    try:
        session_id = request.session_id or "default"
        memory = get_session(session_id)
        rag = get_rag_chain()
        result = rag.ask(
            question=request.question,
            memory=memory,
            workspace=request.workspace,
        )
        if not result.get("from_cache"):
            increment()
        sources = [SourceResponse(**src) for src in result["sources"]]
        return ChatResponse(
            answer=result["answer"],
            sources=sources,
            question=result["question"],
            session_id=session_id,
            nb_sources=len(sources),
            from_cache=bool(result.get("from_cache")),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise _internal_error(e, "Pipeline RAG (chat)")


# ============================================================
# POST /api/chat/stream
# ============================================================


@router.post(
    "/chat/stream",
    summary="Réponse en streaming (SSE)",
)
async def chat_stream(request: ChatRequest):
    _check_index()
    _check_workspace(request.workspace)
    _check_rate_limit()

    session_id = request.session_id or "default"
    memory = get_session(session_id)
    rag = get_rag_chain()

    async def generate():
        ref = str(uuid.uuid4())[:8].upper()
        incremented = False
        try:
            async for event in rag.ask_stream(request.question, memory, request.workspace):
                if not incremented and not event.get("from_cache"):
                    increment()
                    incremented = True
                # Injecter le compteur de requêtes dans l'événement final (done=True)
                # pour que le client mette à jour le badge sans requête supplémentaire.
                if event.get("done"):
                    lim   = get_limit()
                    used  = get_today_count()
                    event["rate_limit"]     = lim
                    event["rate_used"]      = used
                    event["rate_remaining"] = max(0, lim - used) if lim > 0 else None
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error(f"[{ref}] Stream RAG : {e}", exc_info=True)
            error_payload = {
                "error": (
                    f"Erreur lors de la génération de la réponse (réf. {ref}). "
                    "Réessayez dans quelques instants."
                ),
                "done": True,
            }
            yield f"data: {json.dumps(error_payload, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ============================================================
# POST /api/chat/clear
# ============================================================


@router.post("/chat/clear", summary="Efface l'historique d'une session")
def clear_memory(request: ClearMemoryRequest) -> dict:
    session_id = request.session_id
    try:
        if session_id in _sessions:
            _sessions[session_id].clear()
            return {"message": f"Session « {session_id} » effacée.", "session_id": session_id}
        return {"message": f"Session « {session_id} » introuvable ou déjà vide.", "session_id": session_id}
    except Exception as e:
        raise _internal_error(e, f"Effacement session {session_id}")


# ============================================================
# GET /api/chat/sessions
# ============================================================


@router.get("/chat/sessions", summary="Liste des sessions actives")
def get_sessions() -> dict:
    return {
        "sessions": [
            {"session_id": sid, "exchanges": mem.exchange_count} for sid, mem in _sessions.items()
        ],
        "total": len(_sessions),
    }
