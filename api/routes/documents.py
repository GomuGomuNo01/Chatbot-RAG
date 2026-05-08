"""
Routes Documents :
  GET  /api/documents              — liste des documents indexés
  GET  /api/categories             — liste toutes les catégories
  POST /api/categories             — crée une catégorie personnalisée
  POST /api/documents/upload       — upload (rapide) + indexation en arrière-plan
  POST /api/documents/reindex      — reconstruction complète de l'index (arrière-plan)
  GET  /api/index/status           — état de l'indexation en cours
  DELETE /api/documents/{cat}/{f}  — supprime un document + reconstruit l'index
  DELETE /api/categories/{key}     — supprime une catégorie personnalisée
  POST /api/documents/{cat}/{f}/reindex — ré-indexe un document précis
"""

import logging
import threading
import time as _time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path, PureWindowsPath, PurePosixPath
from typing import List

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile, File, Form
from api.schemas import (
    DocumentsResponse,
    DocumentInfo,
    CategoryInfo,
    CategoriesResponse,
    CreateCategoryRequest,
    UploadResponse,
    UploadedFile,
    ReindexResponse,
    IndexStatusResponse,
    DeleteDocumentResponse,
    DeleteCategoryResponse,
    ReindexFileResponse,
)
from config import (
    get_all_categories, register_custom_category, delete_custom_category,
    DOCS_DIR, CATEGORIES, is_r2_enabled,
)

router = APIRouter()
logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 Mo

# Identifiants de catégorie interdits (conflits avec routes API / dossiers système)
_RESERVED_CATEGORY_KEYS: frozenset = frozenset({
    "api", "admin", "docs", "static", "data", "index", "health",
    "chat", "documents", "categories", "settings", "config",
    "all", "upload", "reindex", "status", "search",
})


# ============================================================
# Store de statut d'indexation (thread-safe, in-memory)
# ============================================================

_indexation_status: dict = {
    "running":  False,
    "chunks":   0,
    "files":    0,
    "done_at":  None,
    "error":    None,
    "warnings": [],   # liste de messages d'avertissement (succès partiel)
}
_status_lock = threading.Lock()


def _set_running() -> None:
    with _status_lock:
        _indexation_status.update({
            "running": True, "chunks": 0, "files": 0,
            "done_at": None, "error": None, "warnings": [],
        })


def _set_done(chunks: int, files: int = 0, warnings: list | None = None) -> None:
    with _status_lock:
        _indexation_status.update({
            "running": False, "chunks": chunks, "files": files,
            "done_at": _time.time(), "error": None,
            "warnings": warnings or [],
        })


def _set_error(err: str) -> None:
    with _status_lock:
        _indexation_status.update({
            "running": False, "chunks": 0, "files": 0,
            "done_at": None, "error": err, "warnings": [],
        })


# ============================================================
# Chargement parallèle des fichiers
# ============================================================

def _load_files_parallel(
    files: list,           # [(Path, categorie_str), ...]
    max_workers: int = 4,
) -> tuple:               # (all_docs: list, warnings: list[str])
    """
    Charge et découpe les fichiers en parallèle (I/O + extraction texte).
    PyMuPDF libère le GIL → réel gain en parallèle pour les PDFs.

    Préserve l'ordre d'insertion pour un index FAISS déterministe.
    Retourne (all_docs, warnings) — warnings listant les fichiers en erreur.
    """
    from src.loader import load_file

    n = len(files)
    if n == 0:
        return [], []

    # Résultats indexés pour préserver l'ordre
    docs_by_idx: dict[int, list] = {}
    warnings:    list[str]       = []
    workers = min(max_workers, n)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(load_file, path, cat): (idx, path, cat)
            for idx, (path, cat) in enumerate(files)
        }
        for future in as_completed(futures):
            idx, path, cat = futures[future]
            try:
                docs = future.result()
                if not docs:
                    msg = (
                        f"« {path.name} » ({cat}) : aucun texte extractible "
                        "(fichier scanné, protégé ou vide ?)"
                    )
                    warnings.append(msg)
                    logger.warning(f"[load_parallel] {msg}")
                else:
                    docs_by_idx[idx] = docs
                    logger.info(f"[load_parallel] {path.name} → {len(docs)} chunks")
            except Exception as e:
                msg = f"« {path.name} » ({cat}) : erreur d'extraction — {e}"
                warnings.append(msg)
                logger.warning(f"[load_parallel] {msg}", exc_info=True)

    # Recomposer dans l'ordre d'origine
    all_docs: list = []
    for idx in range(n):
        if idx in docs_by_idx:
            all_docs.extend(docs_by_idx[idx])

    logger.info(
        f"[load_parallel] {n} fichier(s) → {len(all_docs)} chunks "
        f"({len(warnings)} ignoré(s))"
    )
    return all_docs, warnings


# ============================================================
# Tâches d'arrière-plan
# ============================================================

def _run_upload_indexation(
    saved_files: list,      # [(Path, categorie_str), ...]
    manifest_updates: dict, # {path_str: hash}
) -> None:
    """
    Embed + indexe les fichiers déjà sauvegardés sur disque.
    Appelée par BackgroundTasks après que l'upload HTTP a répondu 202.
    """
    _set_running()
    t_start = _time.perf_counter()
    try:
        from src.indexer import (
            add_documents_to_index, create_index,
            index_exists, load_manifest, save_manifest,
        )
        from src.retriever import reset_vectorstore

        manifest = load_manifest()
        manifest.update(manifest_updates)

        # ── Chargement parallèle des fichiers ────────────────
        t0 = _time.perf_counter()
        all_docs, file_warnings = _load_files_parallel(saved_files, max_workers=4)
        logger.info(f"[BG-upload] Extraction : {_time.perf_counter() - t0:.1f}s")

        if not all_docs:
            detail = "Aucun contenu indexable extrait des fichiers uploadés."
            if file_warnings:
                detail += " Détails : " + " | ".join(file_warnings)
            _set_error(detail)
            return

        # ── Indexation FAISS ──────────────────────────────────
        t0 = _time.perf_counter()
        if index_exists():
            add_documents_to_index(all_docs, manifest)
        else:
            create_index(all_docs)
            save_manifest(manifest)
        reset_vectorstore()
        logger.info(f"[BG-upload] Embedding + FAISS : {_time.perf_counter() - t0:.1f}s")

        elapsed = _time.perf_counter() - t_start
        _set_done(len(all_docs), len(saved_files), warnings=file_warnings)
        logger.info(
            f"[BG-upload] Terminé en {elapsed:.1f}s — {len(all_docs)} chunks"
            + (f", {len(file_warnings)} avertissement(s)" if file_warnings else "")
        )

    except Exception as e:
        logger.error(f"[BG-upload] Erreur inattendue : {e}", exc_info=True)
        _set_error(f"Erreur d'indexation : {e}")


def _run_reindex_all_background() -> None:
    """
    Reconstruction complète de l'index FAISS depuis tous les docs/.
    Appelée par BackgroundTasks après que la route reindex a répondu 202.
    """
    _set_running()
    t_start = _time.perf_counter()
    try:
        from src.loader import SUPPORTED_EXTENSIONS as EXT
        from src.indexer import create_index, save_manifest, _file_hash
        from src.retriever import reset_vectorstore
        from pathlib import Path as P

        cats = get_all_categories()

        # ── Synchroniser R2 → local (Render = filesystem éphémère) ───────────
        if is_r2_enabled():
            try:
                from src.storage import sync_r2_to_local
                downloaded = sync_r2_to_local(DOCS_DIR)
                if downloaded:
                    logger.info(f"[BG-reindex] R2 → local : {downloaded} fichier(s) synchronisé(s)")
            except Exception as e:
                logger.warning(f"[BG-reindex] Synchronisation R2 → local ignorée : {e}", exc_info=True)

        all_files: list = []
        for cat_key, cat_cfg in cats.items():
            directory = P(cat_cfg["dir"])
            if not directory.exists():
                continue
            for f in directory.iterdir():
                if f.suffix.lower() in EXT:
                    all_files.append((f, cat_key))

        if not all_files:
            _set_error(
                "Aucun document trouvé dans docs/. "
                "Uploadez des fichiers via l'interface avant de lancer une ré-indexation."
            )
            return

        # ── Chargement parallèle des fichiers ────────────────
        t0 = _time.perf_counter()
        all_docs, file_warnings = _load_files_parallel(all_files, max_workers=4)
        logger.info(f"[BG-reindex] Extraction : {_time.perf_counter() - t0:.1f}s")

        if not all_docs:
            detail = "Aucun contenu extractible dans les documents présents."
            if file_warnings:
                detail += " Détails : " + " | ".join(file_warnings)
            _set_error(detail)
            return

        # ── Indexation FAISS ──────────────────────────────────
        t0 = _time.perf_counter()
        create_index(all_docs)
        manifest = {str(f.resolve()): _file_hash(f) for f, _ in all_files}
        save_manifest(manifest)
        reset_vectorstore()
        logger.info(f"[BG-reindex] Embedding + FAISS : {_time.perf_counter() - t0:.1f}s")

        elapsed = _time.perf_counter() - t_start
        _set_done(len(all_docs), len(all_files), warnings=file_warnings)
        logger.info(
            f"[BG-reindex] Terminé en {elapsed:.1f}s — "
            f"{len(all_docs)} chunks, {len(all_files)} fichier(s)"
            + (f", {len(file_warnings)} avertissement(s)" if file_warnings else "")
        )

    except Exception as e:
        logger.error(f"[BG-reindex] Erreur inattendue : {e}", exc_info=True)
        _set_error(f"Erreur lors de la reconstruction de l'index : {e}")


def _run_rebuild_after_delete(all_files: list) -> None:
    """
    Reconstruit l'index FAISS après suppression d'un document ou d'une catégorie.
    Appelée par BackgroundTasks — ne bloque pas la réponse HTTP.

    Si all_files est vide, vide l'index (plus aucun document).
    """
    _set_running()
    t_start = _time.perf_counter()
    try:
        from src.indexer import (
            create_index, save_manifest, _file_hash,
            INDEX_PATH, MANIFEST_FILE,
        )
        from src.retriever import reset_vectorstore

        if not all_files:
            # Plus aucun document : vider complètement l'index
            for idx_file in ["index.faiss", "index.pkl"]:
                p = INDEX_PATH / idx_file
                if p.exists():
                    p.unlink()
            if MANIFEST_FILE.exists():
                MANIFEST_FILE.write_text("{}", encoding="utf-8")
            reset_vectorstore()
            _set_done(0, 0)
            logger.info("[BG-delete] Index vidé — aucun document restant.")
            return

        # Charger et indexer les fichiers restants
        all_docs, file_warnings = _load_files_parallel(all_files, max_workers=4)

        if not all_docs:
            _set_error("Aucun contenu extractible dans les documents restants après suppression.")
            return

        create_index(all_docs)
        manifest = {str(f.resolve()): _file_hash(f) for f, _ in all_files}
        save_manifest(manifest)
        reset_vectorstore()

        elapsed = _time.perf_counter() - t_start
        _set_done(len(all_docs), len(all_files), warnings=file_warnings)
        logger.info(
            f"[BG-delete] Index reconstruit en {elapsed:.1f}s — "
            f"{len(all_docs)} chunks, {len(all_files)} fichier(s)"
            + (f", {len(file_warnings)} avertissement(s)" if file_warnings else "")
        )

    except Exception as e:
        logger.error(f"[BG-delete] Erreur inattendue : {e}", exc_info=True)
        _set_error(f"Erreur reconstruction index après suppression : {e}")


# ============================================================
# Utilitaires
# ============================================================

def _get_categories() -> dict:
    """Récupère toutes les catégories à jour (hardcodées + custom)."""
    return get_all_categories()


def _parse_manifest_path(path_str: str) -> tuple[str, str | None]:
    """Extrait (nom_fichier, categorie) depuis un chemin absolu."""
    cats = _get_categories()
    for P in (PureWindowsPath, PurePosixPath):
        try:
            p   = P(path_str)
            cat = p.parent.name
            return p.name, cat if cat in cats else None
        except Exception:
            continue
    return Path(path_str).name, None


# ============================================================
# GET /api/documents
# ============================================================

@router.get(
    "/documents",
    response_model=DocumentsResponse,
    summary="Liste des documents indexés",
)
def get_documents() -> DocumentsResponse:
    cats      = _get_categories()
    documents = []
    seen: set[str] = set()

    # ── 1. Scanner le dossier docs/ (fichiers physiquement présents) ──────────
    for cat_key, cat_config in cats.items():
        directory = Path(cat_config["dir"])
        if not directory.exists():
            continue
        for f in sorted(directory.iterdir()):
            if f.suffix.lower() in SUPPORTED_EXTENSIONS:
                key = f"{cat_key}/{f.name}"
                if key not in seen:
                    seen.add(key)
                    documents.append(DocumentInfo(
                        nom       = f.name,
                        categorie = cat_key,
                        label     = cat_config["label"],
                        emoji     = cat_config["emoji"],
                    ))

    # ── 2. Compléter depuis Cloudflare R2 (si configuré) ─────────────────────
    if is_r2_enabled():
        try:
            from src.storage import list_files_r2
            for item in list_files_r2():
                cat      = item["categorie"]
                filename = item["filename"]
                if cat not in cats:
                    continue
                if Path(filename).suffix.lower() not in SUPPORTED_EXTENSIONS:
                    continue
                key = f"{cat}/{filename}"
                if key not in seen:
                    seen.add(key)
                    documents.append(DocumentInfo(
                        nom       = filename,
                        categorie = cat,
                        label     = cats[cat]["label"],
                        emoji     = cats[cat]["emoji"],
                    ))
        except Exception as e:
            logger.warning(f"Impossible de lister les fichiers R2 : {e}")

    # ── 3. Compléter avec le manifeste FAISS ─────────────────────────────────
    try:
        from src.indexer import load_manifest
        manifest = load_manifest()
        for path_str in manifest:
            nom, cat = _parse_manifest_path(path_str)
            if not nom or not cat:
                continue
            key = f"{cat}/{nom}"
            if key not in seen:
                seen.add(key)
                documents.append(DocumentInfo(
                    nom       = nom,
                    categorie = cat,
                    label     = cats[cat]["label"],
                    emoji     = cats[cat]["emoji"],
                ))
    except Exception as e:
        logger.warning(f"Impossible de lire le manifeste : {e}")

    if not documents:
        raise HTTPException(
            status_code=404,
            detail="Aucun document indexé. Lance python ingest.py d'abord."
        )

    return DocumentsResponse(
        documents  = documents,
        total      = len(documents),
        categories = list(cats.keys()),
    )


# ============================================================
# GET /api/categories
# ============================================================

@router.get(
    "/categories",
    response_model=CategoriesResponse,
    summary="Liste toutes les catégories disponibles",
)
def get_categories() -> CategoriesResponse:
    cats   = _get_categories()
    result = []
    for key, cfg in cats.items():
        directory = Path(cfg["dir"])
        nb_docs   = 0
        if directory.exists():
            nb_docs = sum(
                1 for f in directory.iterdir()
                if f.suffix.lower() in SUPPORTED_EXTENSIONS
            )
        result.append(CategoryInfo(
            key     = key,
            label   = cfg["label"],
            emoji   = cfg["emoji"],
            couleur = cfg["couleur"],
            nb_docs = nb_docs,
        ))
    return CategoriesResponse(categories=result, total=len(result))


# ============================================================
# POST /api/categories
# ============================================================

@router.post(
    "/categories",
    response_model=CategoryInfo,
    status_code=201,
    summary="Crée une nouvelle catégorie de documents",
)
def create_category(body: CreateCategoryRequest) -> CategoryInfo:
    cats = _get_categories()

    # Identifiants système réservés
    if body.key in _RESERVED_CATEGORY_KEYS:
        raise HTTPException(
            status_code=409,
            detail=(
                f"L'identifiant « {body.key} » est réservé par le système. "
                "Choisissez un identifiant différent (ex. : marketing, finance, rse)."
            ),
        )

    if body.key in cats:
        raise HTTPException(
            status_code=409,
            detail=f"Une catégorie existe déjà avec l'identifiant « {body.key} »."
        )

    label_lower = body.label.strip().lower()
    for existing_key, existing_cfg in cats.items():
        if existing_cfg["label"].strip().lower() == label_lower:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Une catégorie existe déjà avec ce nom : "
                    f"« {existing_cfg['label']} » (identifiant : {existing_key})."
                )
            )
    try:
        register_custom_category(
            key     = body.key,
            label   = body.label,
            emoji   = body.emoji,
            couleur = body.couleur,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return CategoryInfo(
        key     = body.key,
        label   = body.label,
        emoji   = body.emoji,
        couleur = body.couleur,
        nb_docs = 0,
    )


# ============================================================
# POST /api/documents/upload  (non bloquant — répond en < 5 s)
# ============================================================

@router.post(
    "/documents/upload",
    response_model=UploadResponse,
    summary="Upload de documents (sauvegarde immédiate, indexation en arrière-plan)",
    description=(
        "Phase 1 (rapide, < 5 s) : valide, sauvegarde sur disque et pousse vers R2. "
        "Retourne immédiatement avec background=true. "
        "Phase 2 (arrière-plan) : extraction de texte + embeddings + FAISS. "
        "Interrogez GET /api/index/status pour suivre la progression."
    ),
)
async def upload_documents(
    background_tasks: BackgroundTasks,
    categorie: str = Form(..., description="Clé de catégorie cible"),
    files:     List[UploadFile] = File(..., description="Fichiers à uploader"),
) -> UploadResponse:

    # Refuser si une indexation est déjà en cours
    with _status_lock:
        if _indexation_status["running"]:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Une indexation est déjà en cours. "
                    "Attendez qu'elle se termine avant d'uploader de nouveaux fichiers."
                ),
            )

    cats = _get_categories()
    if categorie not in cats:
        raise HTTPException(
            status_code=422,
            detail=f"Catégorie inconnue : '{categorie}'. "
                   f"Créez-la d'abord via POST /api/categories."
        )
    if not files:
        raise HTTPException(status_code=422, detail="Aucun fichier fourni.")

    cat_dir = Path(cats[categorie]["dir"])
    cat_dir.mkdir(parents=True, exist_ok=True)

    from src.indexer import _file_hash

    results:          List[UploadedFile] = []
    saved_files:      list               = []   # [(Path, categorie), ...]
    manifest_updates: dict               = {}   # {str(path): hash}

    for upload in files:
        filename = Path(upload.filename or "fichier").name
        ext      = Path(filename).suffix.lower()

        # Validation extension
        if ext not in SUPPORTED_EXTENSIONS:
            results.append(UploadedFile(
                nom    = filename,
                chunks = 0,
                statut = "erreur",
                detail = f"Format non supporté ({ext}). Acceptés : {', '.join(SUPPORTED_EXTENSIONS)}",
            ))
            continue

        # Lire contenu
        content = await upload.read()
        if len(content) > MAX_FILE_SIZE:
            results.append(UploadedFile(
                nom    = filename,
                chunks = 0,
                statut = "erreur",
                detail = f"Fichier trop volumineux ({len(content) // (1024*1024)} Mo > 50 Mo).",
            ))
            continue

        # Vérifier doublon
        dest = cat_dir / filename
        r2_duplicate = False
        if is_r2_enabled():
            try:
                from src.storage import file_exists_r2
                r2_duplicate = file_exists_r2(categorie, filename)
            except Exception as e:
                logger.warning(f"Impossible de vérifier R2 pour {filename} : {e}")

        if dest.exists() or r2_duplicate:
            results.append(UploadedFile(
                nom    = filename,
                chunks = 0,
                statut = "erreur",
                detail = (
                    f"Le document « {filename} » existe déjà dans la catégorie "
                    f"« {cats[categorie]['label']} ». "
                    "Renommez le fichier ou supprimez l'existant pour le remplacer."
                ),
            ))
            continue

        # ── Phase 1 : sauvegarder sur disque ──────────────────
        dest.write_bytes(content)
        logger.info(f"[upload] Fichier sauvegardé : {dest}")

        # ── Phase 1 : pousser vers R2 (fast — réseau serveur) ─
        if is_r2_enabled():
            try:
                from src.storage import upload_file_r2
                upload_file_r2(content, categorie, filename)
            except Exception as e:
                logger.warning(f"[upload] R2 upload {filename} échoué (non bloquant) : {e}")

        # Préparer pour la phase 2 (indexation en arrière-plan)
        saved_files.append((dest, categorie))
        manifest_updates[str(dest.resolve())] = _file_hash(dest)

        results.append(UploadedFile(
            nom    = filename,
            chunks = 0,       # connu seulement après indexation
            statut = "ok",
        ))
        logger.info(f"[upload] {filename} sauvegardé, en attente d'indexation.")

    # ── Phase 2 : déléguer l'indexation à un thread d'arrière-plan ────────────
    nb_ok  = sum(1 for r in results if r.statut == "ok")
    nb_err = len(results) - nb_ok

    if saved_files:
        background_tasks.add_task(_run_upload_indexation, saved_files, manifest_updates)
        logger.info(f"[upload] {len(saved_files)} fichier(s) en file d'indexation.")

    if nb_ok > 0 and nb_err == 0:
        msg = (
            f"{nb_ok} fichier(s) sauvegardé(s). "
            "Indexation en cours en arrière-plan — suivez l'avancement via /api/index/status."
        )
    elif nb_ok > 0:
        msg = f"{nb_ok} fichier(s) sauvegardé(s), {nb_err} erreur(s). Indexation lancée."
    else:
        msg = f"{nb_err} erreur(s). Aucun fichier sauvegardé."

    return UploadResponse(
        categorie    = categorie,
        fichiers     = results,
        total_chunks = 0,
        message      = msg,
        background   = nb_ok > 0,
    )


# ============================================================
# GET /api/index/status
# ============================================================

@router.get(
    "/index/status",
    response_model=IndexStatusResponse,
    summary="État de l'indexation en arrière-plan",
)
def get_index_status() -> IndexStatusResponse:
    with _status_lock:
        s = dict(_indexation_status)

    if s["running"]:
        msg = "Indexation en cours… Veuillez patienter."
    elif s["error"]:
        msg = f"Erreur d'indexation : {s['error']}"
    elif s["done_at"]:
        warn_count = len(s.get("warnings", []))
        msg = f"Indexation terminée — {s['chunks']} chunk(s) depuis {s['files']} fichier(s)."
        if warn_count:
            msg += f" ({warn_count} fichier(s) ignoré(s) — voir warnings)"
    else:
        msg = "Aucune indexation récente."

    return IndexStatusResponse(
        running  = s["running"],
        chunks   = s["chunks"],
        files    = s["files"],
        done_at  = s["done_at"],
        error    = s["error"],
        warnings = s.get("warnings", []),
        message  = msg,
    )


# ============================================================
# POST /api/documents/reindex  (non bloquant)
# ============================================================

@router.post(
    "/documents/reindex",
    response_model=ReindexResponse,
    summary="Relance l'indexation complète de tous les documents (arrière-plan)",
    description=(
        "Lance la reconstruction de l'index FAISS en arrière-plan et retourne immédiatement. "
        "Interrogez GET /api/index/status pour suivre la progression."
    ),
)
async def reindex_all(background_tasks: BackgroundTasks) -> ReindexResponse:
    with _status_lock:
        if _indexation_status["running"]:
            raise HTTPException(
                status_code=409,
                detail="Une indexation est déjà en cours. Attendez qu'elle se termine.",
            )

    background_tasks.add_task(_run_reindex_all_background)
    logger.info("[reindex] Reconstruction complète lancée en arrière-plan.")

    return ReindexResponse(
        total_chunks = 0,
        total_files  = 0,
        message      = (
            "Ré-indexation complète lancée en arrière-plan. "
            "Suivez l'avancement via GET /api/index/status."
        ),
        background   = True,
    )


# ============================================================
# DELETE /api/documents/{categorie}/{filename}
# ============================================================

@router.delete(
    "/documents/{categorie}/{filename}",
    response_model=DeleteDocumentResponse,
    status_code=202,
    summary="Supprime un document et reconstruit l'index en arrière-plan",
    description=(
        "Phase 1 (rapide) : supprime le fichier localement et sur R2. "
        "Phase 2 (arrière-plan) : reconstruction de l'index FAISS. "
        "Interrogez GET /api/index/status pour suivre la progression."
    ),
)
async def delete_document(
    categorie: str,
    filename: str,
    background_tasks: BackgroundTasks,
) -> DeleteDocumentResponse:
    from src.loader import SUPPORTED_EXTENSIONS as EXT

    # Refuser si une indexation est déjà en cours
    with _status_lock:
        if _indexation_status["running"]:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Une indexation est déjà en cours. "
                    "Attendez qu'elle se termine avant de supprimer un document."
                ),
            )

    cats = _get_categories()
    if categorie not in cats:
        raise HTTPException(status_code=404, detail=f"Catégorie inconnue : '{categorie}'.")

    cat_dir = Path(cats[categorie]["dir"])
    dest    = cat_dir / filename

    # Vérifier que le fichier existe (localement ou sur R2)
    file_found = dest.exists()
    if not file_found and is_r2_enabled():
        try:
            from src.storage import file_exists_r2
            file_found = file_exists_r2(categorie, filename)
        except Exception:
            pass

    if not file_found:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Document « {filename} » introuvable dans "
                f"la catégorie « {cats[categorie]['label']} »."
            ),
        )

    # ── Phase 1 : suppression immédiate (rapide) ──────────────────────────────
    if dest.exists():
        dest.unlink()
        logger.info(f"[delete] Fichier supprimé localement : {dest}")

    if is_r2_enabled():
        try:
            from src.storage import delete_file_r2
            delete_file_r2(categorie, filename)
        except Exception as e:
            logger.warning(f"[delete] R2 delete {filename} ignoré : {e}")

    # ── Collecter les fichiers restants pour la reconstruction ────────────────
    all_files: list = []
    for cat_key, cat_cfg in cats.items():
        directory = Path(cat_cfg["dir"])
        if not directory.exists():
            continue
        for f in directory.iterdir():
            if f.suffix.lower() in EXT:
                all_files.append((f, cat_key))

    # ── Phase 2 : reconstruction en arrière-plan ──────────────────────────────
    background_tasks.add_task(_run_rebuild_after_delete, all_files)
    logger.info(
        f"[delete] « {filename} » supprimé — "
        f"reconstruction index en arrière-plan ({len(all_files)} fichier(s) restant(s))."
    )

    return DeleteDocumentResponse(
        nom        = filename,
        categorie  = categorie,
        message    = (
            f"Document « {filename} » supprimé. "
            "Reconstruction de l'index en cours en arrière-plan."
        ),
        background = True,
    )


# ============================================================
# DELETE /api/categories/{key}
# ============================================================

@router.delete(
    "/categories/{key}",
    response_model=DeleteCategoryResponse,
    status_code=202,
    summary="Supprime une catégorie personnalisée et reconstruit l'index en arrière-plan",
    description=(
        "Phase 1 (rapide) : supprime les fichiers localement, sur R2 et du registre. "
        "Phase 2 (arrière-plan) : reconstruction de l'index FAISS. "
        "Interrogez GET /api/index/status pour suivre la progression."
    ),
)
async def delete_category(
    key: str,
    background_tasks: BackgroundTasks,
) -> DeleteCategoryResponse:

    if key in CATEGORIES:
        raise HTTPException(
            status_code=403,
            detail=(
                f"La catégorie « {key} » est native et ne peut pas être supprimée. "
                "Seules les catégories personnalisées sont supprimables."
            ),
        )

    # Refuser si une indexation est déjà en cours
    with _status_lock:
        if _indexation_status["running"]:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Une indexation est déjà en cours. "
                    "Attendez qu'elle se termine avant de supprimer une catégorie."
                ),
            )

    cats = _get_categories()
    if key not in cats:
        raise HTTPException(
            status_code=404,
            detail=f"Catégorie « {key} » introuvable.",
        )

    cat_label = cats[key]["label"]
    cat_dir   = Path(cats[key]["dir"])
    docs_deleted = 0

    # ── Phase 1 : supprimer les fichiers localement ──────────────────────────
    if cat_dir.exists():
        for f in list(cat_dir.iterdir()):
            if f.suffix.lower() in SUPPORTED_EXTENSIONS:
                docs_deleted += 1
                f.unlink()
                logger.info(f"[delete-cat] Fichier supprimé : {f}")
        try:
            cat_dir.rmdir()
        except OSError:
            pass  # dossier non vide (fichiers non-doc) → on laisse

    # ── Phase 1 : supprimer de R2 ────────────────────────────────────────────
    if is_r2_enabled():
        try:
            from src.storage import delete_prefix_r2
            nb_r2 = delete_prefix_r2(key)
            if nb_r2:
                logger.info(f"[delete-cat] R2 : {nb_r2} fichier(s) de « {key} » supprimés")
        except Exception as e:
            logger.warning(f"[delete-cat] R2 delete catégorie {key} partiel : {e}")

    # ── Phase 1 : supprimer du registre custom ───────────────────────────────
    try:
        delete_custom_category(key)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # ── Collecter les fichiers restants ──────────────────────────────────────
    remaining_cats = _get_categories()
    all_files: list = []
    for cat_key, cat_cfg in remaining_cats.items():
        directory = Path(cat_cfg["dir"])
        if not directory.exists():
            continue
        for f in directory.iterdir():
            if f.suffix.lower() in SUPPORTED_EXTENSIONS:
                all_files.append((f, cat_key))

    # ── Phase 2 : reconstruction en arrière-plan ─────────────────────────────
    background_tasks.add_task(_run_rebuild_after_delete, all_files)
    logger.info(
        f"[delete-cat] Catégorie « {cat_label} » ({docs_deleted} doc(s)) supprimée — "
        f"reconstruction index en arrière-plan ({len(all_files)} fichier(s) restant(s))."
    )

    return DeleteCategoryResponse(
        key          = key,
        label        = cat_label,
        docs_deleted = docs_deleted,
        message      = (
            f"Catégorie « {cat_label} » supprimée avec {docs_deleted} document(s). "
            "Reconstruction de l'index en cours en arrière-plan."
        ),
        background   = True,
    )


# ============================================================
# POST /api/documents/{categorie}/{filename}/reindex
# ============================================================

@router.post(
    "/documents/{categorie}/{filename}/reindex",
    response_model=ReindexFileResponse,
    summary="Ré-indexe un document spécifique (reconstruction complète de l'index)",
)
async def reindex_file(categorie: str, filename: str) -> ReindexFileResponse:
    from src.loader import load_file, SUPPORTED_EXTENSIONS as EXT
    from src.indexer import create_index, save_manifest, _file_hash
    from src.retriever import reset_vectorstore
    from pathlib import Path as P

    cats = _get_categories()
    if categorie not in cats:
        raise HTTPException(status_code=404, detail=f"Catégorie inconnue : '{categorie}'.")

    cat_dir = P(cats[categorie]["dir"])
    dest    = cat_dir / filename

    # ── Télécharger depuis R2 si absent localement ───────────
    if not dest.exists() and is_r2_enabled():
        try:
            from src.storage import download_file_r2, file_exists_r2
            if file_exists_r2(categorie, filename):
                cat_dir.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(download_file_r2(categorie, filename))
                logger.info(f"R2 → local : {categorie}/{filename} téléchargé pour ré-indexation")
        except Exception as e:
            logger.warning(f"R2 download {filename} ignoré : {e}")

    if not dest.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Document « {filename} » introuvable dans la catégorie « {cats[categorie]['label']} ».",
        )

    # ── Reconstruction complète de l'index ───────────────────
    all_files: list = []
    for cat_key, cat_cfg in cats.items():
        directory = P(cat_cfg["dir"])
        if not directory.exists():
            continue
        for f in directory.iterdir():
            if f.suffix.lower() in EXT:
                all_files.append((f, cat_key))

    all_docs = []
    file_chunks = 0
    for file_path, cat_key in all_files:
        try:
            docs = load_file(file_path, cat_key)
            all_docs.extend(docs)
            if file_path.name == filename and cat_key == categorie:
                file_chunks = len(docs)
        except Exception as e:
            logger.warning(f"Impossible de charger {file_path.name} : {e}")

    if not all_docs:
        raise HTTPException(status_code=500, detail="Aucun contenu extrait. Vérifiez le fichier.")

    try:
        create_index(all_docs)
        manifest = {str(f.resolve()): _file_hash(f) for f, _ in all_files}
        save_manifest(manifest)
        reset_vectorstore()
        logger.info(f"Ré-indexation de {filename} : {file_chunks} chunks, index total {len(all_docs)} chunks.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur d'indexation : {e}")

    return ReindexFileResponse(
        nom=filename,
        categorie=categorie,
        chunks=file_chunks,
        total_chunks=len(all_docs),
        total_files=len(all_files),
        message=(
            f"« {filename} » ré-indexé : {file_chunks} chunks. "
            f"Index total : {len(all_docs)} chunks depuis {len(all_files)} fichier(s)."
        ),
    )
