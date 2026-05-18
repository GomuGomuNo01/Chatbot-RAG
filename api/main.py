"""
main.py — Application FastAPI principale (refonte v2).

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
# LIFESPAN
# ============================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 55)
    logger.info(f"  DocAssist v{API_VERSION} — DÉMARRAGE")
    logger.info("=" * 55)

    try:
        from pathlib import Path as _Path

        from config import (
            DOCS_DIR,
            WORKSPACES_FILE,
            auto_provision_workspaces_from_disk,
            get_workspaces,
            is_hf_enabled,
            is_r2_enabled,
        )

        from src.indexer import index_exists, is_chunk_config_stale
        from src.loader import SUPPORTED_EXTENSIONS as _EXT

        # 1. Restauration R2 (fichiers sources + registre workspaces)
        if is_r2_enabled():
            logger.info("[startup] R2 configuré — restauration des fichiers…")

            if not WORKSPACES_FILE.exists():
                try:
                    from src.storage import download_metadata_r2

                    if download_metadata_r2("workspaces.json", WORKSPACES_FILE):
                        logger.info("[startup] R2 → local : workspaces.json restauré")
                except Exception as e:
                    logger.warning(f"[startup] R2 workspaces restore ignorée : {e}", exc_info=True)

            try:
                from src.storage import sync_r2_to_local

                downloaded = sync_r2_to_local(DOCS_DIR)
                if downloaded:
                    logger.info(f"[startup] R2 → local : {downloaded} fichier(s) restauré(s)")
            except Exception as e:
                logger.warning(f"[startup] R2 sync ignorée : {e}", exc_info=True)
        else:
            logger.info("[startup] R2 non configuré (mode local).")

        # 2. Auto-provisionnement des workspaces depuis docs/ existants (legacy)
        try:
            n = auto_provision_workspaces_from_disk()
            if n:
                logger.info(f"[startup] {n} workspace(s) auto-provisionné(s) depuis docs/")
        except Exception as e:
            logger.warning(f"[startup] Auto-provision workspaces ignorée : {e}")

        # 3. Index FAISS depuis HF Hub si absent
        if not index_exists() and is_hf_enabled():
            try:
                from src.hf_store import pull_index_from_hub

                pulled = pull_index_from_hub()
                if pulled:
                    logger.info("[startup] Index FAISS récupéré depuis HF Hub")
            except Exception as e:
                logger.warning(f"[startup] HF Hub pull ignoré : {e}", exc_info=True)
        elif not is_hf_enabled():
            logger.info("[startup] HF Hub non configuré.")

        # 3b. Détection d'indexation interrompue (crash/OOM lors d'un run précédent)
        try:
            from api.routes.documents import _LOCK_FILE
            from api.routes.documents import _set_error as _set_idx_error

            if _LOCK_FILE.exists():
                _LOCK_FILE.unlink()
                _set_idx_error(
                    "Indexation interrompue par un redémarrage du service (mémoire insuffisante ?). "
                    "Relancez l'indexation manuellement."
                )
                logger.warning(
                    "[startup] Lock d'indexation détecté — la dernière indexation n'a pas abouti."
                )
        except Exception as e:
            logger.warning(f"[startup] Vérification lock ignorée : {e}")

        # 4. Pré-chargement / auto-reindex
        if index_exists():
            if is_chunk_config_stale():
                logger.warning("[startup] Config chunking modifiée — ré-indexation automatique…")
                try:
                    import threading

                    from api.routes.documents import _run_reindex_all_background

                    threading.Thread(
                        target=_run_reindex_all_background,
                        daemon=True,
                        name="startup-stale-reindex",
                    ).start()
                except Exception as e:
                    logger.warning(f"[startup] Reindex stale échoué : {e}", exc_info=True)
            else:
                try:
                    from src.retriever import get_vectorstore

                    get_vectorstore()
                    logger.info("[startup] Index FAISS pré-chargé")
                except Exception as preload_err:
                    logger.warning(
                        f"[startup] Pré-chargement index ignoré "
                        f"({type(preload_err).__name__}) — chargement différé."
                    )
        else:
            workspaces = get_workspaces()
            has_docs = False
            for cfg in workspaces.values():
                d = _Path(cfg["dir"])
                if d.exists() and any(f.suffix.lower() in _EXT for f in d.iterdir()):
                    has_docs = True
                    break

            if has_docs:
                # ⚠️ Ne pas lancer de ré-indexation automatique au démarrage :
                # sur Render free (512 Mo), cela provoquerait un OOM immédiat,
                # suivi d'un redémarrage → re-OOM → boucle infinie.
                # L'utilisateur doit déclencher la ré-indexation manuellement
                # depuis l'interface (bouton « Relancer l'indexation »).
                logger.warning(
                    "[startup] Index absent mais des documents sont présents. "
                    "Relancez l'indexation manuellement depuis l'interface."
                )
                try:
                    from api.routes.documents import _set_error as _set_idx_error

                    _set_idx_error(
                        "Index absent après redémarrage du service. "
                        "Cliquez sur « Relancer l'indexation » dans l'interface pour reconstruire l'index."
                    )
                except Exception:
                    pass
            else:
                logger.info("[startup] Index absent et aucun document — uploadez via l'interface.")

    except Exception as e:
        logger.error(f"[startup] Erreur critique : {e}", exc_info=True)

    logger.info("=" * 55)
    logger.info(f"  API prête — http://0.0.0.0:8000  (v{API_VERSION})")
    logger.info("=" * 55)

    yield

    # Shutdown propre : effacer le verrou pour ne pas créer de faux positif au prochain démarrage
    try:
        from api.routes.documents import _clear_lock

        _clear_lock()
    except Exception:
        pass
    logger.info("[shutdown] DocAssist — Arrêt propre.")


# ============================================================
# APP
# ============================================================

app = FastAPI(
    title=API_TITLE,
    version=API_VERSION,
    description=API_DESCRIPTION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    ref = str(uuid.uuid4())[:8].upper()
    logger.error(
        f"[{ref}] Exception non gérée sur {request.method} {request.url.path} : {exc}",
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": f"Erreur interne inattendue (réf. {ref}). Réessayez dans quelques instants."
        },
    )


# Routers
app.include_router(health.router, prefix="/api", tags=["Santé"])
app.include_router(documents.router, prefix="/api", tags=["Documents & Workspaces"])
app.include_router(chat.router, prefix="/api", tags=["Chat"])

# Frontend statique
frontend_dir = Path(__file__).parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="static")
