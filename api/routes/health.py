"""
Route GET /api/health — Statut de l'API
"""

from fastapi import APIRouter
from api.schemas import HealthResponse
from src.indexer import index_exists
from config import (
    GROQ_LLM_MODEL,
    EMBEDDING_MODEL,
    API_VERSION,
    CATEGORIES
)

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Statut de l'API",
    description="Vérifie que l'API est opérationnelle et que l'index existe."
)
def health_check() -> HealthResponse:
    return HealthResponse(
        status           = "ok",
        index_disponible = index_exists(),
        nb_categories    = len(CATEGORIES),
        modele_llm       = GROQ_LLM_MODEL,
        modele_embedding = EMBEDDING_MODEL,
        version          = API_VERSION
    )