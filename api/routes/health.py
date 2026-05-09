"""
Route GET /api/health — Statut de l'API
"""

import logging
from pathlib import Path

from config import (
    API_VERSION,
    EMBEDDING_MODEL,
    GROQ_LLM_MODEL,
    get_all_categories,
    is_hf_enabled,
    is_r2_enabled,
)
from fastapi import APIRouter

from api.schemas import HealthResponse
from src.indexer import index_exists

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Statut de l'API",
    description=(
        "Vérifie que l'API est opérationnelle : index FAISS, "
        "stockage R2, HuggingFace Hub, nombre de documents."
    ),
)
def health_check() -> HealthResponse:
    cats = get_all_categories()

    # Compter les documents présents dans docs/
    nb_docs = 0
    try:
        from src.loader import SUPPORTED_EXTENSIONS as EXT

        for cfg in cats.values():
            d = Path(cfg["dir"])
            if d.exists():
                nb_docs += sum(1 for f in d.iterdir() if f.suffix.lower() in EXT)
    except Exception as e:
        logger.warning(f"[health] Impossible de compter les documents : {e}")

    return HealthResponse(
        status="ok",
        index_disponible=index_exists(),
        nb_categories=len(cats),
        nb_documents=nb_docs,
        modele_llm=GROQ_LLM_MODEL,
        modele_embedding=EMBEDDING_MODEL,
        version=API_VERSION,
        r2_enabled=is_r2_enabled(),
        hf_enabled=is_hf_enabled(),
    )
