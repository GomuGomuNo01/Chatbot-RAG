"""
main.py — Application FastAPI principale
Lancer : uvicorn api.main:app --reload --port 8000
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from api.routes import chat, documents, health
from config import (
    API_TITLE,
    API_VERSION,
    API_DESCRIPTION
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


# ============================================================
# LIFESPAN — Démarrage et arrêt de l'app
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Exécuté au démarrage et à l'arrêt de l'API."""
    logger.info("=" * 50)
    logger.info("  CHATBOT RAG - DEMARRAGE")
    logger.info("=" * 50)

    # Pré-charger l'index et le modèle au démarrage
    try:
        from src.indexer import index_exists
        from config import is_hf_enabled

        if not index_exists() and is_hf_enabled():
            # Index absent localement → tentative de pull depuis HF Hub
            logger.info("Index FAISS absent — tentative de pull depuis HuggingFace Hub…")
            try:
                from src.hf_store import pull_index_from_hub
                pulled = pull_index_from_hub()
                if pulled:
                    logger.info("Index FAISS récupéré depuis HF Hub : OK")
                else:
                    logger.warning("HF Hub : index absent (premier déploiement ?)")
            except Exception as e:
                logger.warning(f"HF Hub pull ignoré : {e}")

        if index_exists():
            from src.retriever import get_vectorstore
            get_vectorstore()
            logger.info("Index FAISS pre-charge : OK")
        else:
            logger.warning(
                "Index FAISS absent — uploadez des documents via l'interface "
                "ou lancez : python ingest.py"
            )
    except Exception as e:
        logger.error(f"Erreur pre-chargement : {e}")

    yield  # L'app tourne ici

    logger.info("Chatbot RAG - Arret propre.")


# ============================================================
# APPLICATION FASTAPI
# ============================================================

app = FastAPI(
    title       = API_TITLE,
    version     = API_VERSION,
    description = API_DESCRIPTION,
    lifespan    = lifespan,
    docs_url    = "/docs",
    redoc_url   = "/redoc"
)

# ---- CORS — autorise le frontend à appeler l'API ----
app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["*"],
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"]
)

# ---- Routes API ----
app.include_router(
    health.router,
    prefix="/api",
    tags=["Santé"]
)
app.include_router(
    documents.router,
    prefix="/api",
    tags=["Documents"]
)
app.include_router(
    chat.router,
    prefix="/api",
    tags=["Chat"]
)

# ---- Servir le frontend statique ----
# Monté en dernier pour que les routes /api/* restent prioritaires.
# html=True : sert index.html pour / et tout chemin sans fichier correspondant.
frontend_dir = Path(__file__).parent.parent / "frontend"
if frontend_dir.exists():
    app.mount(
        "/",
        StaticFiles(directory=str(frontend_dir), html=True),
        name="static"
    )