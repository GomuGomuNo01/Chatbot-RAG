"""
Loader : chargement et découpage des documents en chunks
Formats supportés : PDF (.pdf), Word (.docx), Texte (.txt)
"""

import logging
from pathlib import Path

import pymupdf as fitz
from config import CATEGORIES, CHUNK_OVERLAP, CHUNK_SIZE
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from tqdm import tqdm

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}


# ============================================================
# EXTRACTEURS PAR FORMAT
# ============================================================


def _is_slide_pdf(pages_raw: list[str], sample: int = 10) -> bool:
    """
    Heuristique : détecte les PDFs de type présentation/cours.
    Critères : pages courtes (< 400 chars en moyenne) ET bruit récurrent
    (timestamps, footers identiques sur plusieurs pages).
    """
    import re

    if not pages_raw:
        return False
    sample_pages = pages_raw[: min(sample, len(pages_raw))]
    avg_len = sum(len(p) for p in sample_pages) / len(sample_pages)
    if avg_len > 600:
        return False  # Trop dense pour être des slides
    # Cherche un footer répété sur ≥ 30% des pages
    footer_re = re.compile(r"\b\d{2}:\d{2}:\d{2}\b|Programmation Web", re.I)
    hits = sum(1 for p in sample_pages if footer_re.search(p))
    return hits >= max(2, len(sample_pages) * 0.3)


def extract_text_from_pdf(pdf_path: Path) -> list[dict]:
    """
    Extrait le texte page par page depuis un PDF.
    Retourne une liste de dicts {text, page_num, file_path}.

    Pour les PDFs de type slides/cours (pages courtes, bruit répété),
    un nettoyage automatique supprime les timestamps et footers parasites
    avant indexation.
    """
    from src.query_processor import clean_slide_text

    pages = []
    try:
        size_kb = pdf_path.stat().st_size // 1024
        doc = fitz.open(str(pdf_path))
        total_pages = len(doc)

        # Pré-lecture pour détecter le format slides et les PDFs scannés
        raw_texts = [doc[i].get_text("text").strip() for i in range(min(15, total_pages))]
        sample_chars = sum(len(t) for t in raw_texts)
        is_slides = _is_slide_pdf(raw_texts)
        if is_slides:
            logger.info(f"  PDF slides détecté : {pdf_path.name} — nettoyage du bruit activé")

        for page_num in range(total_pages):
            text = doc[page_num].get_text("text").strip()
            if is_slides:
                text = clean_slide_text(text)
            if len(text) >= 50:
                pages.append(
                    {
                        "text": text,
                        "page_num": page_num + 1,
                        "file_path": str(pdf_path),
                    }
                )
        doc.close()
        if not pages:
            # Distingue les PDFs scannés (image uniquement) des PDFs protégés/vides
            if sample_chars == 0:
                logger.warning(
                    f"  PDF scanné (image uniquement) : {pdf_path.name} "
                    f"({size_kb} Ko, {total_pages} page(s)) — "
                    "0 caractère extractible sur les pages testées. "
                    "Ce document doit être converti en PDF texte avant indexation "
                    "(ex : Adobe Acrobat OCR, ocrmypdf, ou un outil en ligne)."
                )
            else:
                logger.warning(
                    f"  PDF : {pdf_path.name} ({size_kb} Ko, {total_pages} page(s)) — "
                    "aucune page avec suffisamment de texte (min 50 chars). "
                    "Le fichier est peut-être protégé ou contient principalement des images."
                )
        else:
            logger.info(f"  PDF : {pdf_path.name} — {len(pages)}/{total_pages} page(s) utile(s)")
    except Exception as e:
        size_kb = pdf_path.stat().st_size // 1024 if pdf_path.exists() else "?"
        logger.error(
            f"  Erreur lecture PDF {pdf_path.name} ({size_kb} Ko) : {e}",
            exc_info=True,
        )
    return pages


def extract_text_from_docx(docx_path: Path) -> list[dict]:
    """
    Extrait le texte depuis un fichier Word (.docx).
    Le contenu entier est traité comme une seule page.
    """
    pages = []
    try:
        from docx import Document as DocxDocument

        doc = DocxDocument(str(docx_path))
        paras = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        text = "\n\n".join(paras)
        if len(text) >= 50:
            pages.append(
                {
                    "text": text,
                    "page_num": 1,
                    "file_path": str(docx_path),
                }
            )
            logger.info(f"  DOCX : {docx_path.name} — {len(paras)} paragraphe(s)")
        else:
            logger.warning(
                f"  DOCX : {docx_path.name} — aucun texte suffisant ({len(paras)} paragraphe(s)). "
                "Le fichier est peut-être vide ou ne contient que des images."
            )
    except ImportError:
        logger.error(
            f"  Dépendance manquante pour lire {docx_path.name} : "
            "python-docx n'est pas installé. Exécutez : pip install python-docx"
        )
    except Exception as e:
        size_kb = docx_path.stat().st_size // 1024 if docx_path.exists() else "?"
        logger.error(
            f"  Erreur lecture DOCX {docx_path.name} ({size_kb} Ko) : {e}",
            exc_info=True,
        )
    return pages


def extract_text_from_txt(txt_path: Path) -> list[dict]:
    """
    Extrait le texte depuis un fichier texte brut (.txt).
    Découpe en blocs de 3 000 caractères pour simuler des pages.
    """
    pages = []
    try:
        raw = txt_path.read_text(encoding="utf-8", errors="ignore").strip()
        block_size = 3000
        blocks = [raw[i : i + block_size] for i in range(0, len(raw), block_size)]
        for idx, block in enumerate(blocks, 1):
            if len(block) >= 50:
                pages.append(
                    {
                        "text": block,
                        "page_num": idx,
                        "file_path": str(txt_path),
                    }
                )
        if not pages:
            logger.warning(
                f"  TXT : {txt_path.name} — fichier vide ou trop court pour être indexé "
                f"({len(raw)} caractère(s) au total, minimum requis : 50)."
            )
        else:
            logger.info(f"  TXT : {txt_path.name} — {len(pages)} bloc(s)")
    except Exception as e:
        size_kb = txt_path.stat().st_size // 1024 if txt_path.exists() else "?"
        logger.error(
            f"  Erreur lecture TXT {txt_path.name} ({size_kb} Ko) : {e}",
            exc_info=True,
        )
    return pages


# ============================================================
# DISPATCHER MULTI-FORMAT
# ============================================================

_EXTRACTORS = {
    ".pdf": extract_text_from_pdf,
    ".docx": extract_text_from_docx,
    ".txt": extract_text_from_txt,
}


def extract_text(file_path: Path) -> list[dict]:
    """Sélectionne automatiquement l'extracteur selon l'extension."""
    extractor = _EXTRACTORS.get(file_path.suffix.lower())
    if not extractor:
        raise ValueError(
            f"Format non supporté : {file_path.suffix} "
            f"(acceptés : {', '.join(SUPPORTED_EXTENSIONS)})"
        )
    return extractor(file_path)


# ============================================================
# DÉCOUPAGE EN CHUNKS LANGCHAIN
# ============================================================


def pages_to_documents(
    pages: list[dict],
    categorie: str,
    nom_fichier: str,
) -> list[Document]:
    """
    Convertit les pages/blocs extraits en Documents LangChain
    avec métadonnées complètes.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ".", "!", "?", " ", ""],
    )
    documents = []
    for page in pages:
        for chunk_idx, chunk in enumerate(splitter.split_text(page["text"])):
            if len(chunk.strip()) < 30:
                continue
            documents.append(
                Document(
                    page_content=chunk,
                    metadata={
                        "source": nom_fichier,
                        "page": page["page_num"],
                        "categorie": categorie,
                        "chunk_index": chunk_idx,
                        "file_path": page["file_path"],
                    },
                )
            )
    return documents


# ============================================================
# CHARGEMENT D'UN FICHIER UNIQUE
# ============================================================


def load_file(file_path: Path, categorie: str) -> list[Document]:
    """
    Charge et découpe un seul fichier (PDF, DOCX ou TXT).
    Utilisé par ingest.py --file et par les tests.
    """
    pages = extract_text(file_path)
    docs = pages_to_documents(pages, categorie, file_path.name)
    logger.info(f"  {file_path.name} → {len(docs)} chunk(s)")
    return docs


# ============================================================
# CHARGEMENT D'UNE CATÉGORIE COMPLÈTE
# ============================================================


def load_category(categorie: str) -> list[Document]:
    """Charge tous les fichiers supportés d'une catégorie."""
    config = CATEGORIES.get(categorie)
    if not config:
        raise ValueError(f"Catégorie inconnue : {categorie}")

    directory = Path(config["dir"])
    files = [f for ext in SUPPORTED_EXTENSIONS for f in sorted(directory.glob(f"*{ext}"))]

    if not files:
        logger.warning(
            f"Aucun document dans {directory} (formats : {', '.join(SUPPORTED_EXTENSIONS)})"
        )
        return []

    logger.info(f"Catégorie '{categorie}' : {len(files)} fichier(s)")
    all_documents = []
    for file_path in tqdm(files, desc=f"  {categorie}"):
        all_documents.extend(load_file(file_path, categorie))
    return all_documents


# ============================================================
# CHARGEMENT GLOBAL — TOUTES CATÉGORIES
# ============================================================


def load_all_documents() -> list[Document]:
    """Charge et découpe tous les documents de toutes les catégories."""
    logger.info("=== CHARGEMENT DES DOCUMENTS ===")
    all_docs = []
    for categorie in CATEGORIES:
        docs = load_category(categorie)
        all_docs.extend(docs)
        logger.info(f"  '{categorie}' : {len(docs)} chunks")
    logger.info(f"Total : {len(all_docs)} chunks depuis {len(CATEGORIES)} catégorie(s)")
    return all_docs
