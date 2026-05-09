"""
main.py — Application FastAPI principale
Lancer : uvicorn api.main:app --reload --port 8000
"""

import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from config import API_DESCRIPTION, API_TITLE, API_VERSION
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from api.routes import chat, documents, health

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# ============================================================
# LIFESPAN — Démarrage et arrêt de l'app
# ============================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Exécuté au démarrage et à l'arrêt de l'API."""
    logger.info("=" * 55)
    logger.info("  CHATBOT RAG — DÉMARRAGE")
    logger.info("=" * 55)

    try:
        from pathlib import Path as _Path

        from config import (
            DOCS_DIR,
            get_all_categories,
            is_hf_enabled,
            is_r2_enabled,
        )

        from src.indexer import index_exists
        from src.loader import SUPPORTED_EXTENSIONS as _EXT

        # ── 1. Restaurer les fichiers sources depuis Cloudflare R2 ────────────
        # Render (et tout PaaS avec filesystem éphémère) perd les fichiers locaux
        # entre les redémarrages. R2 est la source de vérité permanente.
        if is_r2_enabled():
            logger.info("[startup] Cloudflare R2 configuré — restauration des fichiers sources…")

            # 1a. Restaurer custom_categories.json en premier (nécessaire pour
            #     que sync_r2_to_local crée les bons sous-dossiers de catégories)
            from config import CUSTOM_CATEGORIES_FILE

            if not CUSTOM_CATEGORIES_FILE.exists():
                try:
                    from src.storage import download_metadata_r2

                    restored = download_metadata_r2(
                        "custom_categories.json", CUSTOM_CATEGORIES_FILE
                    )
                    if restored:
                        logger.info("[startup] ✓ R2 → local : custom_categories.json restauré")
                    else:
                        logger.info(
                            "[startup] · R2 → local : custom_categories.json absent (1er déploiement ?)"
                        )
                except Exception as e:
                    logger.warning(
                        f"[startup] ✗ R2 custom_categories restore ignorée : {e}", exc_info=True
                    )

            # 1b. Restaurer les fichiers documents (PDF, DOCX, TXT)
            try:
                from src.storage import sync_r2_to_local

                downloaded = sync_r2_to_local(DOCS_DIR)
                if downloaded:
                    logger.info(f"[startup] ✓ R2 → local : {downloaded} fichier(s) restauré(s)")
                else:
                    logger.info("[startup] · R2 → local : aucun nouveau fichier à restaurer")
            except Exception as e:
                logger.warning(f"[startup] ✗ R2 sync ignorée : {e}", exc_info=True)
        else:
            logger.info("[startup] Cloudflare R2 : non configuré (mode filesystem local)")

        # ── 2. Récupérer l'index FAISS depuis HuggingFace Hub ────────────────
        if not index_exists() and is_hf_enabled():
            logger.info("[startup] Index FAISS absent — pull depuis HuggingFace Hub…")
            try:
                from src.hf_store import pull_index_from_hub

                pulled = pull_index_from_hub()
                if pulled:
                    logger.info("[startup] ✓ Index FAISS récupéré depuis HF Hub")
                else:
                    logger.info("[startup] · HF Hub : index absent (premier déploiement ?)")
            except Exception as e:
                logger.warning(f"[startup] ✗ HF Hub pull ignoré : {e}", exc_info=True)
        elif not is_hf_enabled():
            logger.info("[startup] HuggingFace Hub : non configuré (persistance index désactivée)")

        # ── 3. Pré-charger l'index ou lancer une reconstruction automatique ──
        if index_exists():
            # Pré-chargement optionnel : accélère la 1ère requête mais non critique.
            # Encapsulé séparément du try global pour éviter un crash OOM silencieux
            # (le kernel tue le process avant que l'exception ne soit catchée).
            # Si les embeddings échouent (HF_TOKEN absent, modèle local manquant),
            # on continue — l'index se chargera lazily à la première requête.
            try:
                from src.retriever import get_vectorstore

                get_vectorstore()
                logger.info("[startup] ✓ Index FAISS pré-chargé")
            except Exception as preload_err:
                logger.warning(
                    f"[startup] · Pré-chargement index ignoré ({type(preload_err).__name__}) "
                    "— chargement différé à la première requête. "
                    "Vérifiez que HF_TOKEN est défini si vous utilisez requirements-prod.txt."
                )
        else:
            # Vérifier si des documents locaux sont présents
            cats = get_all_categories()
            has_docs = False
            for cat_cfg in cats.values():
                cat_dir = _Path(cat_cfg["dir"])
                if cat_dir.exists() and any(f.suffix.lower() in _EXT for f in cat_dir.iterdir()):
                    has_docs = True
                    break

            if has_docs:
                logger.info("[startup] Documents présents sans index → reconstruction automatique…")
                try:
                    import threading

                    from api.routes.documents import _run_reindex_all_background

                    t = threading.Thread(
                        target=_run_reindex_all_background,
                        daemon=True,
                        name="startup-auto-reindex",
                    )
                    t.start()
                    logger.info("[startup] ✓ Reconstruction d'index lancée en arrière-plan")
                except Exception as e:
                    logger.warning(f"[startup] ✗ Reconstruction auto échouée : {e}", exc_info=True)
            else:
                logger.warning(
                    "[startup] · Index FAISS absent — uploadez des documents via l'interface"
                )

    except Exception as e:
        logger.error(f"[startup] Erreur critique au démarrage : {e}", exc_info=True)

    logger.info("=" * 55)
    logger.info("  API prête — http://0.0.0.0:8000")
    logger.info("=" * 55)

    yield  # L'app tourne ici

    logger.info("[shutdown] Chatbot RAG — Arrêt propre.")


# ============================================================
# APPLICATION FASTAPI
# ============================================================

app = FastAPI(
    title=API_TITLE,
    version=API_VERSION,
    description=API_DESCRIPTION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---- CORS — autorise le frontend à appeler l'API ----
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# GESTIONNAIRE D'ERREURS GLOBAL
# ============================================================


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Intercepte toute exception non gérée par les routes.
    Évite d'exposer la stack Python au client tout en loggant l'erreur complète.
    """
    ref = str(uuid.uuid4())[:8].upper()
    logger.error(
        f"[{ref}] Exception non gérée sur {request.method} {request.url.path} : {exc}",
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": (f"Erreur interne inattendue (réf. {ref}). Réessayez dans quelques instants.")
        },
    )


# ---- Routes API ----
app.include_router(health.router, prefix="/api", tags=["Santé"])
app.include_router(documents.router, prefix="/api", tags=["Documents"])
app.include_router(chat.router, prefix="/api", tags=["Chat"])

# ---- Servir le frontend statique ----
# Monté en dernier pour que les routes /api/* restent prioritaires.
# html=True : sert index.html pour / et tout chemin sans fichier correspondant.
frontend_dir = Path(__file__).parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="static")
