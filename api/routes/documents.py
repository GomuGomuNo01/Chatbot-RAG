"""
Routes Documents / Workspaces (refonte v2) :

  GET    /api/workspaces                       — liste tous les workspaces (utilisateur)
  POST   /api/workspaces                       — crée un workspace
  DELETE /api/workspaces/{key}                 — supprime un workspace
  GET    /api/documents                        — liste les documents indexés
  POST   /api/documents/upload                 — upload non bloquant dans un workspace
  POST   /api/documents/reindex                — reconstruction complète (arrière-plan)
  GET    /api/index/status                     — état d'indexation
  DELETE /api/documents/{workspace}/{filename} — supprime un document
  POST   /api/documents/{workspace}/{filename}/reindex — ré-indexe un document

Plus aucune catégorie « native ». Tout est utilisateur.
"""

import gc
import logging
import threading
import time as _time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path, PurePosixPath, PureWindowsPath

from config import (
    BASE_DIR,
    DOCS_DIR,
    WORKSPACES_FILE,
    delete_workspace,
    get_workspace,
    get_workspaces,
    is_r2_enabled,
    is_valid_workspace_key,
    register_workspace,
)
from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile

from api.schemas import (
    CreateWorkspaceRequest,
    DeleteDocumentResponse,
    DeleteWorkspaceResponse,
    DocumentInfo,
    DocumentsResponse,
    IndexStatusResponse,
    ReindexFileResponse,
    ReindexResponse,
    UploadedFile,
    UploadResponse,
    WorkspaceInfo,
    WorkspacesResponse,
)

router = APIRouter()
logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 Mo


# ============================================================
# Statut d'indexation (thread-safe)
# ============================================================

_indexation_status: dict = {
    "running": False,
    "chunks": 0,
    "files": 0,
    "done_at": None,
    "error": None,
    "warnings": [],
}
_status_lock = threading.Lock()

# Fichier verrou : écrit au démarrage d'une indexation, effacé à la fin.
# S'il est présent au startup, le process a crashé pendant une indexation.
_LOCK_FILE = BASE_DIR / "data" / "indexing.lock"


def _write_lock() -> None:
    """Crée le fichier verrou d'indexation."""
    try:
        _LOCK_FILE.write_text("running", encoding="utf-8")
    except Exception as e:
        logger.warning(f"[lock] Écriture ignorée : {e}")


def _clear_lock() -> None:
    """Supprime le fichier verrou d'indexation."""
    try:
        if _LOCK_FILE.exists():
            _LOCK_FILE.unlink()
    except Exception as e:
        logger.warning(f"[lock] Suppression ignorée : {e}")


def _set_running() -> None:
    _write_lock()
    with _status_lock:
        _indexation_status.update(
            {
                "running": True,
                "chunks": 0,
                "files": 0,
                "done_at": None,
                "error": None,
                "warnings": [],
            }
        )


def _set_done(chunks: int, files: int = 0, warnings: list | None = None) -> None:
    _clear_lock()
    with _status_lock:
        _indexation_status.update(
            {
                "running": False,
                "chunks": chunks,
                "files": files,
                "done_at": _time.time(),
                "error": None,
                "warnings": warnings or [],
            }
        )


def _set_error(err: str) -> None:
    _clear_lock()
    with _status_lock:
        _indexation_status.update(
            {
                "running": False,
                "chunks": 0,
                "files": 0,
                "done_at": None,
                "error": err,
                "warnings": [],
            }
        )


# ============================================================
# Chargement parallèle
# ============================================================


def _load_files_parallel(files: list, max_workers: int = 1) -> tuple:
    """Charge et chunke en parallèle. files = [(Path, workspace_key), …]."""
    from src.loader import get_and_clear_truncation_notices, load_file

    n = len(files)
    if n == 0:
        return [], []

    docs_by_idx: dict[int, list] = {}
    warnings: list[str] = []
    workers = min(max_workers, n)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(load_file, path, ws): (idx, path, ws)
            for idx, (path, ws) in enumerate(files)
        }
        for future in as_completed(futures):
            idx, path, ws = futures[future]
            try:
                docs = future.result()
                if not docs:
                    msg = (
                        f"« {path.name} » ({ws}) : aucun texte extractible "
                        "(fichier scanné, protégé ou vide ?)"
                    )
                    warnings.append(msg)
                    logger.warning(f"[load] {msg}")
                else:
                    docs_by_idx[idx] = docs
                    logger.info(f"[load] {path.name} → {len(docs)} chunks")
            except Exception as e:
                msg = f"« {path.name} » ({ws}) : erreur d'extraction — {e}"
                warnings.append(msg)
                logger.warning(f"[load] {msg}", exc_info=True)

    # Récupère les avertissements de troncature PDF (PDFs > MAX_PDF_PAGES pages)
    truncation_notices = get_and_clear_truncation_notices()
    warnings.extend(truncation_notices)

    all_docs: list = []
    for idx in range(n):
        if idx in docs_by_idx:
            all_docs.extend(docs_by_idx[idx])
    return all_docs, warnings


# ============================================================
# Tâches d'arrière-plan
# ============================================================


def _invalidate_caches() -> None:
    """Vide le cache de réponses (à appeler après changement d'index)."""
    try:
        from src.cache import get_cache

        get_cache().clear()
    except Exception as e:
        logger.warning(f"[cache] Invalidation échouée : {e}")


def _push_to_hub_daemon() -> None:
    """Pousse l'index FAISS vers HF Hub dans un thread daemon — non bloquant pour l'UI."""

    def _do() -> None:
        try:
            from src.hf_store import push_index_to_hub

            push_index_to_hub()
        except Exception as e:
            logger.warning(f"[HF Hub] Push ignoré : {e}")

    threading.Thread(target=_do, daemon=True).start()


def _run_upload_indexation(saved_files: list, manifest_updates: dict) -> None:
    gc.collect()  # libère la mémoire avant de commencer (réduit le pic initial)
    _set_running()
    t_start = _time.perf_counter()
    try:
        from src.bm25_store import reset_bm25_index
        from src.indexer import (
            add_documents_to_index,
            create_index,
            index_exists,
            load_manifest,
            save_manifest,
        )
        from src.retriever import reset_vectorstore

        manifest = load_manifest()
        manifest.update(manifest_updates)

        t0 = _time.perf_counter()
        all_docs, file_warnings = _load_files_parallel(saved_files, max_workers=1)
        logger.info(f"[BG-upload] Extraction : {_time.perf_counter() - t0:.1f}s")

        if not all_docs:
            detail = (
                "Aucun texte extractible dans les fichiers uploadés. "
                "Vérifiez que les PDFs ne sont pas scannés (images) et ne sont pas protégés."
            )
            if file_warnings:
                detail += " Détails : " + " | ".join(file_warnings)
            _set_error(detail)
            return

        t0 = _time.perf_counter()
        if index_exists():
            add_documents_to_index(all_docs, manifest)
        else:
            create_index(all_docs)
            save_manifest(manifest)
        reset_vectorstore()
        reset_bm25_index()
        _invalidate_caches()
        logger.info(f"[BG-upload] Index : {_time.perf_counter() - t0:.1f}s")

        elapsed = _time.perf_counter() - t_start
        _set_done(len(all_docs), len(saved_files), warnings=file_warnings)
        logger.info(f"[BG-upload] OK en {elapsed:.1f}s — {len(all_docs)} chunks")
        _push_to_hub_daemon()

    except Exception as e:
        logger.error(f"[BG-upload] Erreur : {e}", exc_info=True)
        _set_error(f"Erreur d'indexation : {e}")


def _run_reindex_all_background() -> None:
    gc.collect()  # libère la mémoire avant de commencer (réduit le pic initial)
    _set_running()
    t_start = _time.perf_counter()
    try:
        from pathlib import Path as P

        from src.indexer import _file_hash, create_index, save_manifest
        from src.loader import SUPPORTED_EXTENSIONS as EXT
        from src.retriever import reset_vectorstore

        if is_r2_enabled():
            try:
                from src.storage import sync_r2_to_local

                downloaded = sync_r2_to_local(DOCS_DIR)
                if downloaded:
                    logger.info(f"[BG-reindex] R2 → local : {downloaded} fichier(s)")
            except Exception as e:
                logger.warning(f"[BG-reindex] R2 sync ignorée : {e}", exc_info=True)

        workspaces = get_workspaces()
        all_files: list = []
        for key, cfg in workspaces.items():
            directory = P(cfg["dir"])
            if not directory.exists():
                continue
            for f in directory.iterdir():
                if f.suffix.lower() in EXT:
                    all_files.append((f, key))

        if not all_files:
            _set_error(
                "Aucun document trouvé. Uploadez des fichiers avant de relancer l'indexation."
            )
            return

        t0 = _time.perf_counter()
        all_docs, file_warnings = _load_files_parallel(all_files, max_workers=1)
        logger.info(f"[BG-reindex] Extraction : {_time.perf_counter() - t0:.1f}s")

        if not all_docs:
            detail = "Aucun contenu extractible."
            if file_warnings:
                detail += " Détails : " + " | ".join(file_warnings)
            _set_error(detail)
            return

        t0 = _time.perf_counter()
        create_index(all_docs)
        manifest = {str(f.resolve()): _file_hash(f) for f, _ in all_files}
        save_manifest(manifest)
        reset_vectorstore()
        _invalidate_caches()
        logger.info(f"[BG-reindex] Index : {_time.perf_counter() - t0:.1f}s")

        elapsed = _time.perf_counter() - t_start
        _set_done(len(all_docs), len(all_files), warnings=file_warnings)
        logger.info(
            f"[BG-reindex] OK en {elapsed:.1f}s — {len(all_docs)} chunks, "
            f"{len(all_files)} fichier(s)"
        )
        _push_to_hub_daemon()

    except Exception as e:
        logger.error(f"[BG-reindex] Erreur : {e}", exc_info=True)
        _set_error(f"Erreur reconstruction index : {e}")


def _run_rebuild_after_delete(all_files: list) -> None:
    """Reconstruction après suppression. all_files vide ⇒ index vidé."""
    gc.collect()  # libère la mémoire avant de commencer (réduit le pic initial)
    _set_running()
    t_start = _time.perf_counter()
    try:
        from src.indexer import (
            INDEX_PATH,
            MANIFEST_FILE,
            _file_hash,
            create_index,
            save_manifest,
        )
        from src.retriever import reset_vectorstore

        if not all_files:
            for idx_file in ("index.faiss", "index.pkl"):
                p = INDEX_PATH / idx_file
                if p.exists():
                    p.unlink()
            if MANIFEST_FILE.exists():
                MANIFEST_FILE.write_text("{}", encoding="utf-8")
            # Vider aussi le BM25
            from config import BM25_INDEX_FILE

            if BM25_INDEX_FILE.exists():
                BM25_INDEX_FILE.unlink()
            reset_vectorstore()
            _invalidate_caches()
            _set_done(0, 0)
            logger.info("[BG-delete] Index vidé — aucun document restant.")
            return

        all_docs, file_warnings = _load_files_parallel(all_files, max_workers=1)
        if not all_docs:
            _set_error("Aucun contenu extractible dans les documents restants.")
            return

        create_index(all_docs)
        manifest = {str(f.resolve()): _file_hash(f) for f, _ in all_files}
        save_manifest(manifest)
        reset_vectorstore()
        _invalidate_caches()

        elapsed = _time.perf_counter() - t_start
        _set_done(len(all_docs), len(all_files), warnings=file_warnings)
        logger.info(
            f"[BG-delete] Reconstruit en {elapsed:.1f}s — {len(all_docs)} chunks, "
            f"{len(all_files)} fichier(s)"
        )
        _push_to_hub_daemon()

    except Exception as e:
        logger.error(f"[BG-delete] Erreur : {e}", exc_info=True)
        _set_error(f"Erreur reconstruction après suppression : {e}")


# ============================================================
# Helpers
# ============================================================


def _parse_manifest_path(path_str: str) -> tuple[str, str | None]:
    """Extrait (nom_fichier, workspace) depuis un chemin du manifest."""
    workspaces = get_workspaces()
    for P in (PureWindowsPath, PurePosixPath):
        try:
            p = P(path_str)
            ws = p.parent.name
            return p.name, ws if ws in workspaces else None
        except Exception:
            continue
    return Path(path_str).name, None


def _list_remaining_files() -> list:
    """Tous les fichiers de tous les workspaces, format [(Path, ws), …]."""
    from src.loader import SUPPORTED_EXTENSIONS as EXT

    out: list = []
    for key, cfg in get_workspaces().items():
        directory = Path(cfg["dir"])
        if not directory.exists():
            continue
        for f in directory.iterdir():
            if f.suffix.lower() in EXT:
                out.append((f, key))
    return out


def _push_workspaces_to_r2() -> None:
    if not is_r2_enabled():
        return
    try:
        from src.storage import upload_metadata_r2

        upload_metadata_r2(WORKSPACES_FILE, "workspaces.json")
    except Exception as e:
        logger.warning(f"R2 workspaces.json push ignoré : {e}")


# ============================================================
# GET /api/workspaces
# ============================================================


@router.get("/workspaces", response_model=WorkspacesResponse, summary="Liste des workspaces")
def list_workspaces() -> WorkspacesResponse:
    result: list[WorkspaceInfo] = []
    for key, cfg in get_workspaces().items():
        directory = Path(cfg["dir"])
        nb = 0
        if directory.exists():
            nb = sum(1 for f in directory.iterdir() if f.suffix.lower() in SUPPORTED_EXTENSIONS)
        result.append(
            WorkspaceInfo(
                key=key,
                label=cfg["label"],
                emoji=cfg["emoji"],
                couleur=cfg["couleur"],
                nb_docs=nb,
            )
        )
    return WorkspacesResponse(workspaces=result, total=len(result))


# ============================================================
# POST /api/workspaces
# ============================================================


@router.post(
    "/workspaces",
    response_model=WorkspaceInfo,
    status_code=201,
    summary="Crée un workspace utilisateur",
)
def create_workspace(body: CreateWorkspaceRequest) -> WorkspaceInfo:
    if not is_valid_workspace_key(body.key):
        raise HTTPException(
            status_code=409,
            detail=(
                f"L'identifiant « {body.key} » est invalide ou réservé. "
                "Choisissez un identifiant différent (lettres minuscules, chiffres, tirets/underscores, 2-32 caractères)."
            ),
        )
    try:
        register_workspace(
            key=body.key,
            label=body.label,
            emoji=body.emoji,
            couleur=body.couleur,
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    _push_workspaces_to_r2()

    return WorkspaceInfo(
        key=body.key, label=body.label, emoji=body.emoji, couleur=body.couleur, nb_docs=0
    )


# ============================================================
# DELETE /api/workspaces/{key}
# ============================================================


@router.delete(
    "/workspaces/{key}",
    response_model=DeleteWorkspaceResponse,
    status_code=202,
    summary="Supprime un workspace et reconstruit l'index",
)
async def remove_workspace(key: str, background_tasks: BackgroundTasks) -> DeleteWorkspaceResponse:
    with _status_lock:
        if _indexation_status["running"]:
            raise HTTPException(
                status_code=409,
                detail="Une indexation est déjà en cours. Attendez qu'elle se termine.",
            )

    ws = get_workspace(key)
    if not ws:
        raise HTTPException(status_code=404, detail=f"Workspace « {key} » introuvable.")

    label = ws["label"]
    cat_dir = Path(ws["dir"])
    docs_deleted = 0

    # Suppression locale
    if cat_dir.exists():
        for f in list(cat_dir.iterdir()):
            if f.suffix.lower() in SUPPORTED_EXTENSIONS:
                docs_deleted += 1
                f.unlink()
        try:
            cat_dir.rmdir()
        except OSError:
            pass  # dossier non vide

    # Suppression R2
    if is_r2_enabled():
        try:
            from src.storage import delete_prefix_r2

            nb = delete_prefix_r2(key)
            if nb:
                logger.info(f"[delete-ws] R2 : {nb} fichier(s) supprimés pour {key}")
        except Exception as e:
            logger.warning(f"[delete-ws] R2 delete partiel : {e}")

    # Suppression du registre
    try:
        delete_workspace(key)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    _push_workspaces_to_r2()

    all_files = _list_remaining_files()
    background_tasks.add_task(_run_rebuild_after_delete, all_files)

    return DeleteWorkspaceResponse(
        key=key,
        label=label,
        docs_deleted=docs_deleted,
        message=f"Workspace « {label} » supprimé avec {docs_deleted} document(s). Index en cours de reconstruction.",
        background=True,
    )


# ============================================================
# GET /api/documents
# ============================================================


@router.get("/documents", response_model=DocumentsResponse, summary="Liste des documents indexés")
def get_documents() -> DocumentsResponse:
    workspaces = get_workspaces()
    documents: list[DocumentInfo] = []
    seen: set[str] = set()

    # Disque
    for key, cfg in workspaces.items():
        directory = Path(cfg["dir"])
        if not directory.exists():
            continue
        for f in sorted(directory.iterdir()):
            if f.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            entry_key = f"{key}/{f.name}"
            if entry_key in seen:
                continue
            seen.add(entry_key)
            documents.append(
                DocumentInfo(
                    nom=f.name,
                    workspace=key,
                    workspace_label=cfg["label"],
                    workspace_emoji=cfg["emoji"],
                )
            )

    # R2 (compléter)
    if is_r2_enabled():
        try:
            from src.storage import list_files_r2

            for item in list_files_r2():
                ws = item["workspace"]
                filename = item["filename"]
                if ws not in workspaces:
                    continue
                if Path(filename).suffix.lower() not in SUPPORTED_EXTENSIONS:
                    continue
                entry_key = f"{ws}/{filename}"
                if entry_key in seen:
                    continue
                seen.add(entry_key)
                documents.append(
                    DocumentInfo(
                        nom=filename,
                        workspace=ws,
                        workspace_label=workspaces[ws]["label"],
                        workspace_emoji=workspaces[ws]["emoji"],
                    )
                )
        except Exception as e:
            logger.warning(f"R2 list ignoré : {e}")

    # Manifeste
    try:
        from src.indexer import load_manifest

        for path_str in load_manifest():
            nom, ws = _parse_manifest_path(path_str)
            if not nom or not ws or ws not in workspaces:
                continue
            entry_key = f"{ws}/{nom}"
            if entry_key in seen:
                continue
            seen.add(entry_key)
            documents.append(
                DocumentInfo(
                    nom=nom,
                    workspace=ws,
                    workspace_label=workspaces[ws]["label"],
                    workspace_emoji=workspaces[ws]["emoji"],
                )
            )
    except Exception as e:
        logger.warning(f"Manifest lecture ignorée : {e}")

    if not documents:
        # 200 + tableau vide est plus pratique côté frontend ; on garde 404 pour
        # respecter la sémantique existante (le frontend gère ce code).
        raise HTTPException(status_code=404, detail="Aucun document indexé pour l'instant.")

    return DocumentsResponse(
        documents=documents,
        total=len(documents),
        workspaces=list(workspaces.keys()),
    )


# ============================================================
# POST /api/documents/upload
# ============================================================


@router.post(
    "/documents/upload",
    response_model=UploadResponse,
    summary="Upload de documents (non bloquant)",
)
async def upload_documents(
    background_tasks: BackgroundTasks,
    workspace: str = Form(..., description="Clé du workspace cible"),
    files: list[UploadFile] = File(..., description="Fichiers à uploader"),
) -> UploadResponse:
    with _status_lock:
        if _indexation_status["running"]:
            raise HTTPException(
                status_code=409,
                detail="Une indexation est déjà en cours. Attendez qu'elle se termine.",
            )

    ws = get_workspace(workspace)
    if not ws:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Workspace inconnu : « {workspace} ». Créez-le d'abord via POST /api/workspaces."
            ),
        )
    if not files:
        raise HTTPException(status_code=422, detail="Aucun fichier fourni.")

    cat_dir = Path(ws["dir"])
    cat_dir.mkdir(parents=True, exist_ok=True)

    from src.indexer import _file_hash

    results: list[UploadedFile] = []
    saved_files: list = []
    manifest_updates: dict = {}

    for upload in files:
        filename = Path(upload.filename or "fichier").name
        ext = Path(filename).suffix.lower()

        if ext not in SUPPORTED_EXTENSIONS:
            results.append(
                UploadedFile(
                    nom=filename,
                    chunks=0,
                    statut="erreur",
                    detail=f"Format non supporté ({ext}). Acceptés : {', '.join(SUPPORTED_EXTENSIONS)}",
                )
            )
            continue

        content = await upload.read()
        if len(content) > MAX_FILE_SIZE:
            results.append(
                UploadedFile(
                    nom=filename,
                    chunks=0,
                    statut="erreur",
                    detail=f"Fichier trop volumineux ({len(content) // (1024 * 1024)} Mo > 50 Mo).",
                )
            )
            continue

        dest = cat_dir / filename
        r2_duplicate = False
        if is_r2_enabled():
            try:
                from src.storage import file_exists_r2

                r2_duplicate = file_exists_r2(workspace, filename)
            except Exception as e:
                logger.warning(f"R2 head échec {filename} : {e}")

        if dest.exists() or r2_duplicate:
            results.append(
                UploadedFile(
                    nom=filename,
                    chunks=0,
                    statut="erreur",
                    detail=(
                        f"« {filename} » existe déjà dans « {ws['label']} ». "
                        "Renommez ou supprimez l'existant pour le remplacer."
                    ),
                )
            )
            continue

        dest.write_bytes(content)
        logger.info(f"[upload] Fichier sauvegardé : {dest}")

        if is_r2_enabled():
            try:
                from src.storage import upload_file_r2

                upload_file_r2(content, workspace, filename)
            except Exception as e:
                logger.warning(f"R2 upload {filename} échoué : {e}")

        saved_files.append((dest, workspace))
        manifest_updates[str(dest.resolve())] = _file_hash(dest)
        results.append(UploadedFile(nom=filename, chunks=0, statut="ok"))

    nb_ok = sum(1 for r in results if r.statut == "ok")
    nb_err = len(results) - nb_ok

    if saved_files:
        background_tasks.add_task(_run_upload_indexation, saved_files, manifest_updates)

    if nb_ok > 0 and nb_err == 0:
        msg = f"{nb_ok} fichier(s) sauvegardé(s). Indexation en cours en arrière-plan."
    elif nb_ok > 0:
        msg = f"{nb_ok} fichier(s) sauvegardé(s), {nb_err} erreur(s). Indexation lancée."
    else:
        msg = f"{nb_err} erreur(s). Aucun fichier sauvegardé."

    return UploadResponse(
        workspace=workspace,
        fichiers=results,
        total_chunks=0,
        message=msg,
        background=nb_ok > 0,
    )


# ============================================================
# GET /api/index/status
# ============================================================


@router.get("/index/status", response_model=IndexStatusResponse, summary="État de l'indexation")
def get_index_status() -> IndexStatusResponse:
    with _status_lock:
        s = dict(_indexation_status)

    if s["running"]:
        msg = "Indexation en cours…"
    elif s["error"]:
        msg = f"Erreur d'indexation : {s['error']}"
    elif s["done_at"]:
        warn_count = len(s.get("warnings", []))
        msg = f"Indexation terminée — {s['chunks']} chunk(s) depuis {s['files']} fichier(s)."
        if warn_count:
            msg += f" ({warn_count} avertissement(s))"
    else:
        msg = "Aucune indexation récente."

    return IndexStatusResponse(
        running=s["running"],
        chunks=s["chunks"],
        files=s["files"],
        done_at=s["done_at"],
        error=s["error"],
        warnings=s.get("warnings", []),
        message=msg,
    )


# ============================================================
# POST /api/documents/reindex
# ============================================================


@router.post(
    "/documents/reindex",
    response_model=ReindexResponse,
    summary="Relance l'indexation complète (arrière-plan)",
)
async def reindex_all(background_tasks: BackgroundTasks) -> ReindexResponse:
    with _status_lock:
        if _indexation_status["running"]:
            raise HTTPException(status_code=409, detail="Une indexation est déjà en cours.")

    background_tasks.add_task(_run_reindex_all_background)
    return ReindexResponse(
        total_chunks=0,
        total_files=0,
        message="Ré-indexation complète lancée en arrière-plan.",
        background=True,
    )


# ============================================================
# DELETE /api/documents/{workspace}/{filename}
# ============================================================


@router.delete(
    "/documents/{workspace}/{filename}",
    response_model=DeleteDocumentResponse,
    status_code=202,
    summary="Supprime un document et reconstruit l'index",
)
async def delete_document(
    workspace: str,
    filename: str,
    background_tasks: BackgroundTasks,
) -> DeleteDocumentResponse:
    with _status_lock:
        if _indexation_status["running"]:
            raise HTTPException(status_code=409, detail="Une indexation est déjà en cours.")

    ws = get_workspace(workspace)
    if not ws:
        raise HTTPException(status_code=404, detail=f"Workspace inconnu : « {workspace} ».")

    cat_dir = Path(ws["dir"])
    dest = cat_dir / filename

    file_found = dest.exists()
    if not file_found and is_r2_enabled():
        try:
            from src.storage import file_exists_r2

            file_found = file_exists_r2(workspace, filename)
        except Exception:
            pass

    if not file_found:
        raise HTTPException(
            status_code=404,
            detail=f"Document « {filename} » introuvable dans « {ws['label']} ».",
        )

    if dest.exists():
        dest.unlink()
        logger.info(f"[delete] Supprimé local : {dest}")

    if is_r2_enabled():
        try:
            from src.storage import delete_file_r2

            delete_file_r2(workspace, filename)
        except Exception as e:
            logger.warning(f"R2 delete {filename} ignoré : {e}")

    # Pas de reindex automatique — trop lourd pour Render free (512 MB).
    # L'index FAISS conserve les anciens vecteurs du document supprimé ;
    # ils deviennent inactifs (fichier absent) et disparaîtront au prochain
    # reindex manuel via POST /api/documents/reindex.
    _invalidate_caches()

    return DeleteDocumentResponse(
        nom=filename,
        workspace=workspace,
        message=(
            f"Document « {filename} » supprimé. "
            "Lancez une ré-indexation manuelle pour mettre à jour l'index."
        ),
        background=False,
    )


# ============================================================
# POST /api/documents/{workspace}/{filename}/reindex
# ============================================================


@router.post(
    "/documents/{workspace}/{filename}/reindex",
    response_model=ReindexFileResponse,
    summary="Ré-indexe un document précis (reconstruction complète)",
)
async def reindex_file(
    workspace: str,
    filename: str,
    background_tasks: BackgroundTasks,
) -> ReindexFileResponse:
    with _status_lock:
        if _indexation_status["running"]:
            raise HTTPException(status_code=409, detail="Une indexation est déjà en cours.")

    ws = get_workspace(workspace)
    if not ws:
        raise HTTPException(status_code=404, detail=f"Workspace inconnu : « {workspace} ».")

    cat_dir = Path(ws["dir"])
    dest = cat_dir / filename

    if not dest.exists() and is_r2_enabled():
        try:
            from src.storage import download_file_r2, file_exists_r2

            if file_exists_r2(workspace, filename):
                cat_dir.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(download_file_r2(workspace, filename))
        except Exception as e:
            logger.warning(f"R2 download {filename} ignoré : {e}")

    if not dest.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Document « {filename} » introuvable dans « {ws['label']} ».",
        )

    all_files = _list_remaining_files()
    background_tasks.add_task(_run_reindex_all_background)
    return ReindexFileResponse(
        nom=filename,
        workspace=workspace,
        chunks=0,
        total_chunks=0,
        total_files=len(all_files),
        message=f"Ré-indexation de « {filename} » lancée. Suivez /api/index/status.",
    )
