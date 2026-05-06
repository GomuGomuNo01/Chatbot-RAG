"""
Route GET /api/documents — Liste des documents indexés
"""

from pathlib import Path
from fastapi import APIRouter, HTTPException
from api.schemas import DocumentsResponse, DocumentInfo
from config import CATEGORIES

router = APIRouter()


@router.get(
    "/documents",
    response_model=DocumentsResponse,
    summary="Liste des documents indexés",
    description="Retourne tous les PDFs disponibles par catégorie."
)
def get_documents() -> DocumentsResponse:
    documents = []

    for cat_key, cat_config in CATEGORIES.items():
        directory = Path(cat_config["dir"])

        if not directory.exists():
            continue

        pdf_files = list(directory.glob("*.pdf"))

        for pdf in pdf_files:
            documents.append(DocumentInfo(
                nom       = pdf.name,
                categorie = cat_key,
                label     = cat_config["label"],
                emoji     = cat_config["emoji"]
            ))

    if not documents:
        raise HTTPException(
            status_code=404,
            detail=(
                "Aucun document indexé. "
                "Lance python ingest.py d'abord."
            )
        )

    return DocumentsResponse(
        documents  = documents,
        total      = len(documents),
        categories = list(CATEGORIES.keys())
    )