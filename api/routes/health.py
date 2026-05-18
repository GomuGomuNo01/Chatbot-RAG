"""Route GET /api/health — Statut de l'API (refonte v2)."""

import logging
from pathlib import Path

from config import (
    ANTHROPIC_MODEL,
    API_VERSION,
    EMBEDDING_MODEL,
    RERANKER_ENABLED,
    get_workspaces,
    is_hf_enabled,
    is_r2_enabled,
)
from fastapi import APIRouter

from api.schemas import HealthResponse
from src.indexer import index_exists
from src.rate_limiter import status as rate_status

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Statut de l'API",
)
def health_check() -> HealthResponse:
    workspaces = get_workspaces()

    nb_docs = 0
    try:
        from src.loader import SUPPORTED_EXTENSIONS as EXT

        for cfg in workspaces.values():
            d = Path(cfg["dir"])
            if d.exists():
                nb_docs += sum(1 for f in d.iterdir() if f.suffix.lower() in EXT)
    except Exception as e:
        logger.warning(f"[health] Comptage docs : {e}")

    rl = rate_status()

    return HealthResponse(
        status="ok",
        index_disponible=index_exists(),
        nb_workspaces=len(workspaces),
        nb_documents=nb_docs,
        modele_llm=ANTHROPIC_MODEL,
        modele_embedding=EMBEDDING_MODEL,
        reranker_actif=RERANKER_ENABLED,
        version=API_VERSION,
        r2_enabled=is_r2_enabled(),
        hf_enabled=is_hf_enabled(),
        requetes_utilisees=rl["used_today"],
        requetes_limite=rl["limit"],
        requetes_restantes=rl["remaining"],
    )
