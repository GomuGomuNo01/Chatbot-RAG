"""
Route GET /api/documents — Liste des documents indexés
"""

import logging
from pathlib import Path, PureWindowsPath, PurePosixPath
from fastapi import APIRouter, HTTPException
from api.schemas import DocumentsResponse, DocumentInfo
from config import CATEGORIES

router = APIRouter()
logger = logging.getLogger(__name__)


def _parse_manifest_path(path_str: str) -> tuple[str, str | None]:
    """
    Extrait (nom_fichier, categorie) depuis un chemin absolu Windows ou POSIX.
    Le manifest stocke les chemins absolus de la machine où l'index a été généré.
    """
    for P in (PureWindowsPath, PurePosixPath):
        try:
            p = P(path_str)
            cat = p.parent.name  # "technique", "rh", "juridique"
            return p.name, cat if cat in CATEGORIES else None
        except Exception:
            continue
    return Path(path_str).name, None


@router.get(
    "/documents",
    response_model=DocumentsResponse,
    summary="Liste des documents indexés",
    description="Retourne tous les documents disponibles par catégorie."
)
def get_documents() -> DocumentsResponse:
    documents = []

    # ── Priorité 1 : scanner le dossier docs/ (développement local) ──
    for cat_key, cat_config in CATEGORIES.items():
        directory = Path(cat_config["dir"])
        if not directory.exists():
            continue
        for f in directory.iterdir():
            if f.suffix.lower() in {".pdf", ".docx", ".txt"}:
                documents.append(DocumentInfo(
                    nom       = f.name,
                    categorie = cat_key,
                    label     = cat_config["label"],
                    emoji     = cat_config["emoji"]
                ))

    # ── Fallback : lire le manifeste FAISS (production / Render) ──
    if not documents:
        try:
            from src.indexer import load_manifest
            manifest = load_manifest()
            seen = set()
            for path_str in manifest:
                nom, cat = _parse_manifest_path(path_str)
                if nom and cat and nom not in seen:
                    seen.add(nom)
                    documents.append(DocumentInfo(
                        nom       = nom,
                        categorie = cat,
                        label     = CATEGORIES[cat]["label"],
                        emoji     = CATEGORIES[cat]["emoji"]
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
        categories = list(CATEGORIES.keys())
    )
