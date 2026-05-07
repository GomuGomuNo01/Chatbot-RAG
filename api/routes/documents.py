"""
Routes Documents :
  GET  /api/documents          — liste des documents indexés
  GET  /api/categories         — liste toutes les catégories
  POST /api/categories         — crée une catégorie personnalisée
  POST /api/documents/upload   — upload + indexation de fichiers
"""

import logging
from pathlib import Path, PureWindowsPath, PurePosixPath
from typing import List

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from api.schemas import (
    DocumentsResponse,
    DocumentInfo,
    CategoryInfo,
    CategoriesResponse,
    CreateCategoryRequest,
    UploadResponse,
    UploadedFile,
    ReindexResponse,
)
from config import get_all_categories, register_custom_category, DOCS_DIR, is_r2_enabled

router = APIRouter()
logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 Mo


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
    # Clé de dédup : "categorie/nom_de_fichier"
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
    # Source autoritaire sur Render : R2 contient tous les fichiers uploadés,
    # même ceux perdus lors d'un redémarrage de l'instance.
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
    # Fallback : fichiers présents dans l'index mais absents du disque et de R2
    # (documents pré-commités dans git avant le déploiement).
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

    # Vérifier doublon sur la clé
    if body.key in cats:
        raise HTTPException(
            status_code=409,
            detail=f"Une catégorie existe déjà avec l'identifiant « {body.key} »."
        )

    # Vérifier doublon sur le label (insensible à la casse)
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
# POST /api/documents/upload
# ============================================================

@router.post(
    "/documents/upload",
    response_model=UploadResponse,
    summary="Upload et indexation de documents",
    description=(
        "Envoie un ou plusieurs fichiers (PDF, DOCX, TXT) dans une catégorie "
        "existante et les indexe immédiatement dans FAISS."
    ),
)
async def upload_documents(
    categorie: str = Form(..., description="Clé de catégorie cible"),
    files:     List[UploadFile] = File(..., description="Fichiers à uploader"),
) -> UploadResponse:

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

    from src.loader import load_file
    from src.indexer import (
        add_documents_to_index,
        create_index,
        index_exists,
        load_manifest,
        save_manifest,
        _file_hash,
    )
    from src.retriever import reset_vectorstore

    results:      List[UploadedFile] = []
    all_docs:     list               = []
    manifest      = load_manifest()

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

        # Vérifier si le document existe déjà (disque local ou R2)
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

        # Sauvegarder sur disque (pour l'indexation immédiate)
        dest.write_bytes(content)
        logger.info(f"Fichier sauvegardé localement : {dest}")

        # Upload vers Cloudflare R2 (persistance permanente)
        if is_r2_enabled():
            try:
                from src.storage import upload_file_r2
                upload_file_r2(content, categorie, filename)
            except Exception as e:
                logger.warning(f"R2 upload {filename} échoué (non bloquant) : {e}")

        # Charger et découper
        try:
            docs = load_file(dest, categorie)
        except Exception as e:
            results.append(UploadedFile(
                nom    = filename,
                chunks = 0,
                statut = "erreur",
                detail = f"Erreur d'extraction : {e}",
            ))
            continue

        if not docs:
            results.append(UploadedFile(
                nom    = filename,
                chunks = 0,
                statut = "erreur",
                detail = "Aucun contenu extrait (fichier vide ou illisible).",
            ))
            continue

        all_docs.extend(docs)
        manifest[str(dest.resolve())] = _file_hash(dest)
        results.append(UploadedFile(
            nom    = filename,
            chunks = len(docs),
            statut = "ok",
        ))
        logger.info(f"{filename} → {len(docs)} chunks")

    # Indexation des nouveaux chunks
    total_chunks = sum(r.chunks for r in results if r.statut == "ok")
    if all_docs:
        try:
            if index_exists():
                add_documents_to_index(all_docs, manifest)
            else:
                create_index(all_docs)
                save_manifest(manifest)
            reset_vectorstore()
            logger.info(f"Indexation terminée : {total_chunks} chunks ajoutés.")
        except Exception as e:
            logger.error(f"Erreur d'indexation : {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Fichiers sauvegardés mais indexation échouée : {e}"
            )

    nb_ok  = sum(1 for r in results if r.statut == "ok")
    nb_err = len(results) - nb_ok
    msg    = f"{nb_ok} fichier(s) indexé(s) avec succès"
    if nb_err:
        msg += f", {nb_err} erreur(s)."

    return UploadResponse(
        categorie    = categorie,
        fichiers     = results,
        total_chunks = total_chunks,
        message      = msg,
    )


# ============================================================
# POST /api/documents/reindex
# ============================================================

@router.post(
    "/documents/reindex",
    response_model=ReindexResponse,
    summary="Relance l'indexation complète de tous les documents",
    description=(
        "Recrée l'index FAISS depuis zéro en parcourant tous les dossiers docs/. "
        "À utiliser si l'index semble incohérent ou après un ajout manuel de fichiers."
    ),
)
async def reindex_all() -> ReindexResponse:
    from src.loader import load_all_documents, SUPPORTED_EXTENSIONS as EXT
    from src.indexer import (
        create_index,
        save_manifest,
        _file_hash,
    )
    from src.retriever import reset_vectorstore
    from pathlib import Path as P

    cats = _get_categories()

    # ── Synchroniser R2 → local avant de ré-indexer ──────────────────────────
    # Sur Render, le filesystem est éphémère : les fichiers uploadés dans une
    # instance précédente ont disparu. On les récupère depuis R2.
    if is_r2_enabled():
        try:
            from src.storage import sync_r2_to_local
            downloaded = sync_r2_to_local(DOCS_DIR)
            if downloaded:
                logger.info(f"R2 → local : {downloaded} fichier(s) synchronisé(s) avant ré-indexation.")
        except Exception as e:
            logger.warning(f"Sync R2 → local ignorée : {e}")

    # Collecter tous les fichiers physiquement présents
    all_files: list = []
    for cat_key, cat_cfg in cats.items():
        directory = P(cat_cfg["dir"])
        if not directory.exists():
            continue
        for f in directory.iterdir():
            if f.suffix.lower() in EXT:
                all_files.append((f, cat_key))

    if not all_files:
        raise HTTPException(
            status_code=404,
            detail=(
                "Aucun document trouvé dans docs/. "
                "Uploadez des fichiers d'abord via l'interface."
            )
        )

    # Charger et découper tous les documents
    from src.loader import load_file
    all_docs = []
    for file_path, cat_key in all_files:
        try:
            docs = load_file(file_path, cat_key)
            all_docs.extend(docs)
        except Exception as e:
            logger.warning(f"Impossible de charger {file_path.name} : {e}")

    if not all_docs:
        raise HTTPException(
            status_code=500,
            detail="Aucun contenu extrait des documents. Vérifiez qu'ils ne sont pas vides."
        )

    try:
        create_index(all_docs)
        manifest = {str(f.resolve()): _file_hash(f) for f, _ in all_files}
        save_manifest(manifest)
        reset_vectorstore()
        logger.info(f"Re-indexation complète : {len(all_docs)} chunks, {len(all_files)} fichiers.")
    except Exception as e:
        logger.error(f"Erreur re-indexation : {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'indexation : {e}")

    return ReindexResponse(
        total_chunks = len(all_docs),
        total_files  = len(all_files),
        message      = (
            f"Index recréé avec succès : {len(all_docs)} chunks "
            f"depuis {len(all_files)} fichier(s)."
        ),
    )
