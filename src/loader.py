"""
Loader : chargement et découpage des PDFs en chunks
"""

import logging
from pathlib import Path
from typing import List, Dict

import pymupdf as fitz  # PyMuPDF
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from tqdm import tqdm

from config import (
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    CATEGORIES
)

logger = logging.getLogger(__name__)


# ============================================================
# EXTRACTION TEXTE DEPUIS UN PDF
# ============================================================

def extract_text_from_pdf(pdf_path: Path) -> List[Dict]:
    """
    Extrait le texte page par page depuis un PDF.

    Returns:
        List[Dict] avec pour chaque page :
            - text      : contenu textuel
            - page_num  : numéro de page (commence à 1)
            - pdf_path  : chemin du fichier source
    """
    pages = []

    try:
        doc = fitz.open(str(pdf_path))

        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text").strip()

            # Ignorer les pages vides ou trop courtes
            if len(text) < 50:
                continue

            pages.append({
                "text":     text,
                "page_num": page_num + 1,
                "pdf_path": str(pdf_path)
            })

        doc.close()
        logger.info(f"  PDF lu : {pdf_path.name} — {len(pages)} pages utiles")

    except Exception as e:
        logger.error(f"  Erreur lecture {pdf_path.name} : {e}")

    return pages


# ============================================================
# DÉCOUPAGE EN CHUNKS
# ============================================================

def pages_to_documents(
    pages: List[Dict],
    categorie: str,
    nom_fichier: str
) -> List[Document]:
    """
    Convertit les pages extraites en Documents LangChain
    avec métadonnées complètes.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ".", "!", "?", " ", ""]
    )

    documents = []

    for page in pages:
        chunks = splitter.split_text(page["text"])

        for chunk_idx, chunk in enumerate(chunks):
            if len(chunk.strip()) < 30:
                continue

            doc = Document(
                page_content=chunk,
                metadata={
                    "source":      nom_fichier,
                    "page":        page["page_num"],
                    "categorie":   categorie,
                    "chunk_index": chunk_idx,
                    "pdf_path":    page["pdf_path"]
                }
            )
            documents.append(doc)

    return documents


# ============================================================
# CHARGEMENT D'UN DOSSIER COMPLET
# ============================================================

def load_category(categorie: str) -> List[Document]:
    """
    Charge tous les PDFs d'une catégorie.

    Args:
        categorie : "technique", "rh" ou "juridique"

    Returns:
        Liste de Documents LangChain avec métadonnées
    """
    config = CATEGORIES.get(categorie)
    if not config:
        raise ValueError(f"Catégorie inconnue : {categorie}")

    directory = Path(config["dir"])
    pdf_files  = list(directory.glob("*.pdf"))

    if not pdf_files:
        logger.warning(
            f"Aucun PDF trouvé dans {directory} "
            f"pour la catégorie '{categorie}'"
        )
        return []

    logger.info(
        f"Catégorie '{categorie}' : "
        f"{len(pdf_files)} PDF(s) détecté(s)"
    )

    all_documents = []

    for pdf_path in tqdm(pdf_files, desc=f"  {categorie}"):
        pages = extract_text_from_pdf(pdf_path)
        docs  = pages_to_documents(
            pages=pages,
            categorie=categorie,
            nom_fichier=pdf_path.name
        )
        all_documents.extend(docs)
        logger.info(
            f"    {pdf_path.name} → "
            f"{len(docs)} chunks créés"
        )

    return all_documents


# ============================================================
# CHARGEMENT GLOBAL — TOUTES CATÉGORIES
# ============================================================

def load_all_documents() -> List[Document]:
    """
    Charge et découpe tous les PDFs de toutes les catégories.

    Returns:
        Liste complète de Documents LangChain
    """
    logger.info("=== CHARGEMENT DES DOCUMENTS ===")
    all_docs = []

    for categorie in CATEGORIES.keys():
        docs = load_category(categorie)
        all_docs.extend(docs)
        logger.info(
            f"  '{categorie}' : {len(docs)} chunks"
        )

    logger.info(
        f"Total : {len(all_docs)} chunks "
        f"depuis {len(CATEGORIES)} catégories"
    )
    return all_docs