"""
loader.py — Extraction + chunking sémantique des documents.

Refonte v2 :
- Métadonnée `workspace` au lieu de `categorie`.
- Chunking sémantique générique (titres > paragraphes > phrases), sans biais
  juridique. Le splitter détecte la structure (Markdown, slides, prose) et
  adapte les frontières de découpe.
- Plus de logique de nettoyage de format spécifique aux PDFs juridiques.
"""

import html as _html
import logging
import re
from pathlib import Path

import pymupdf as fitz
from config import (
    CHUNK_MIN_LENGTH,
    CHUNK_OVERLAP,
    CHUNK_SEPARATORS,
    CHUNK_SIZE,
    get_workspaces,
)
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from tqdm import tqdm

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}

# ============================================================
# NETTOYAGE GÉNÉRIQUE (slides, footers répétés)
# ============================================================

# Footers/headers récurrents communs (timestamps, années académiques, "page X")
_NOISE_PATTERNS = [
    re.compile(r"\b\d{1,2}:\d{2}(:\d{2})?\b"),
    re.compile(r"\b\d{4}\s*[-–]\s*\d{4}\b"),
    re.compile(r"\bpage\s+\d+\s*(?:/|sur|of)\s*\d+\b", re.IGNORECASE),
    re.compile(r"\bp\.\s*\d+\s*(?:/|sur|of)\s*\d+\b", re.IGNORECASE),
]


def _clean_text(text: str) -> str:
    """Nettoyage léger et générique : footers de pagination, timestamps."""
    for pat in _NOISE_PATTERNS:
        text = pat.sub("", text)
    # Compacte les sauts de lignes multiples
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _is_slide_like(pages_raw: list[str], sample: int = 12) -> bool:
    """Détecte un PDF de type slides : pages courtes + bruit récurrent."""
    if not pages_raw:
        return False
    sample_pages = pages_raw[: min(sample, len(pages_raw))]
    avg_len = sum(len(p) for p in sample_pages) / len(sample_pages)
    if avg_len > 600:
        return False
    hits = 0
    for p in sample_pages:
        if any(pat.search(p) for pat in _NOISE_PATTERNS):
            hits += 1
    return hits >= max(2, len(sample_pages) * 0.3)


# ============================================================
# EXTRACTEURS PAR FORMAT
# ============================================================


def _extract_page_text(page) -> str:
    """
    Extraction robuste du texte d'une page PDF.

    Certains PDFs (exports PowerPoint, polices custom) encodent les caractères
    accentués en entités HTML dans le flux XHTML (&#xe9; → é) plutôt qu'en
    Unicode direct. La méthode "text" retourne alors � (caractère de
    remplacement). On utilise donc "xhtml" + html.unescape() en priorité.
    """
    try:
        xhtml = page.get_text("xhtml") or ""
        if xhtml:
            text = _html.unescape(xhtml)          # &#xe9; → é
            text = re.sub(r"<[^>]+>", " ", text)  # strip tags
            text = re.sub(r"[ \t]+", " ", text)
            text = re.sub(r"\n{3,}", "\n\n", text).strip()

            # Préférer XHTML si moins de caractères de remplacement
            plain = page.get_text("text") or ""
            plain_bad = plain.count("�")
            xhtml_bad = text.count("�")
            if xhtml_bad <= plain_bad:
                return text
    except Exception:
        pass
    return (page.get_text("text") or "").strip()


def extract_text_from_pdf(pdf_path: Path) -> list[dict]:
    pages: list[dict] = []
    try:
        size_kb = pdf_path.stat().st_size // 1024
        doc = fitz.open(str(pdf_path))
        total_pages = len(doc)

        raw_texts = [_extract_page_text(doc[i]) for i in range(min(15, total_pages))]
        sample_chars = sum(len(t) for t in raw_texts)
        slide_mode = _is_slide_like(raw_texts)
        if slide_mode:
            logger.info(f"  PDF slides détecté : {pdf_path.name} — nettoyage automatique activé")

        for page_num in range(total_pages):
            text = _extract_page_text(doc[page_num])
            if slide_mode:
                text = _clean_text(text)
            if len(text) >= 50:
                pages.append({"text": text, "page_num": page_num + 1, "file_path": str(pdf_path)})
        doc.close()

        if not pages:
            if sample_chars == 0:
                logger.warning(
                    f"  PDF scanné (sans couche texte) : {pdf_path.name} "
                    f"({size_kb} Ko, {total_pages} page(s)). Une étape d'OCR est nécessaire."
                )
            else:
                logger.warning(
                    f"  PDF : {pdf_path.name} — aucune page exploitable (protégé ? images ?)"
                )
        else:
            logger.info(f"  PDF : {pdf_path.name} — {len(pages)}/{total_pages} page(s) utile(s)")

    except Exception as e:
        size_kb = pdf_path.stat().st_size // 1024 if pdf_path.exists() else "?"
        logger.error(f"  Erreur lecture PDF {pdf_path.name} ({size_kb} Ko) : {e}", exc_info=True)
    return pages


def extract_text_from_docx(docx_path: Path) -> list[dict]:
    try:
        from docx import Document as DocxDocument

        doc = DocxDocument(str(docx_path))
        paras = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        text = "\n\n".join(paras)
        if len(text) < 50:
            logger.warning(f"  DOCX : {docx_path.name} — peu de texte exploitable.")
            return []
        logger.info(f"  DOCX : {docx_path.name} — {len(paras)} paragraphe(s)")
        return [{"text": text, "page_num": 1, "file_path": str(docx_path)}]
    except ImportError:
        logger.error("  python-docx absent — `pip install python-docx`.")
    except Exception as e:
        logger.error(f"  Erreur lecture DOCX {docx_path.name} : {e}", exc_info=True)
    return []


def extract_text_from_txt(txt_path: Path) -> list[dict]:
    try:
        raw = txt_path.read_text(encoding="utf-8", errors="ignore").strip()
        if len(raw) < 50:
            logger.warning(f"  TXT : {txt_path.name} — trop court.")
            return []
        # Découpe par blocs ~3000 chars pour simuler des pages
        block_size = 3000
        blocks = [raw[i : i + block_size] for i in range(0, len(raw), block_size)]
        pages = [
            {"text": b, "page_num": idx, "file_path": str(txt_path)}
            for idx, b in enumerate(blocks, 1)
            if len(b) >= 50
        ]
        if pages:
            logger.info(f"  TXT : {txt_path.name} — {len(pages)} bloc(s)")
        return pages
    except Exception as e:
        logger.error(f"  Erreur lecture TXT {txt_path.name} : {e}", exc_info=True)
        return []


def extract_text_from_md(md_path: Path) -> list[dict]:
    """Markdown : un seul bloc, le splitter récupère les headings."""
    try:
        raw = md_path.read_text(encoding="utf-8", errors="ignore").strip()
        if len(raw) < 50:
            logger.warning(f"  MD : {md_path.name} — trop court.")
            return []
        logger.info(f"  MD : {md_path.name} — {len(raw)} caractère(s)")
        return [{"text": raw, "page_num": 1, "file_path": str(md_path)}]
    except Exception as e:
        logger.error(f"  Erreur lecture MD {md_path.name} : {e}", exc_info=True)
        return []


_EXTRACTORS = {
    ".pdf": extract_text_from_pdf,
    ".docx": extract_text_from_docx,
    ".txt": extract_text_from_txt,
    ".md": extract_text_from_md,
}


def extract_text(file_path: Path) -> list[dict]:
    extractor = _EXTRACTORS.get(file_path.suffix.lower())
    if not extractor:
        raise ValueError(
            f"Format non supporté : {file_path.suffix} "
            f"(acceptés : {', '.join(SUPPORTED_EXTENSIONS)})"
        )
    return extractor(file_path)


# ============================================================
# CHUNKING SÉMANTIQUE
# ============================================================


def _make_splitter() -> RecursiveCharacterTextSplitter:
    """Splitter sémantique générique : titres > paragraphes > phrases > mots."""
    return RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=CHUNK_SEPARATORS,
        length_function=len,
        keep_separator=True,
    )


def pages_to_documents(
    pages: list[dict],
    workspace: str,
    nom_fichier: str,
) -> list[Document]:
    """Convertit les pages extraites en chunks LangChain enrichis."""
    splitter = _make_splitter()
    documents: list[Document] = []
    for page in pages:
        for chunk_idx, chunk in enumerate(splitter.split_text(page["text"])):
            cleaned = chunk.strip()
            if len(cleaned) < CHUNK_MIN_LENGTH:
                continue
            documents.append(
                Document(
                    page_content=cleaned,
                    metadata={
                        "source": nom_fichier,
                        "page": page["page_num"],
                        "workspace": workspace,
                        "chunk_index": chunk_idx,
                        "file_path": page["file_path"],
                    },
                )
            )
    return documents


def load_file(file_path: Path, workspace: str) -> list[Document]:
    pages = extract_text(file_path)
    docs = pages_to_documents(pages, workspace, file_path.name)
    logger.info(f"  {file_path.name} → {len(docs)} chunk(s)")
    return docs


def load_workspace(workspace_key: str) -> list[Document]:
    """Charge tous les fichiers d'un workspace."""
    ws = get_workspaces().get(workspace_key)
    if not ws:
        raise ValueError(f"Workspace inconnu : {workspace_key}")

    directory = Path(ws["dir"])
    files = [f for ext in SUPPORTED_EXTENSIONS for f in sorted(directory.glob(f"*{ext}"))]
    if not files:
        logger.warning(f"Aucun document dans {directory}")
        return []

    logger.info(f"Workspace '{workspace_key}' : {len(files)} fichier(s)")
    all_docs: list[Document] = []
    for file_path in tqdm(files, desc=f"  {workspace_key}"):
        all_docs.extend(load_file(file_path, workspace_key))
    return all_docs


def load_all_documents() -> list[Document]:
    """Charge tous les documents de tous les workspaces enregistrés."""
    logger.info("=== CHARGEMENT DES DOCUMENTS ===")
    all_docs: list[Document] = []
    workspaces = get_workspaces()
    for key in workspaces:
        docs = load_workspace(key)
        all_docs.extend(docs)
        logger.info(f"  '{key}' : {len(docs)} chunks")
    logger.info(f"Total : {len(all_docs)} chunks depuis {len(workspaces)} workspace(s)")
    return all_docs
