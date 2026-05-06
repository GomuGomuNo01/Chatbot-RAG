"""
Tests unitaires — src/loader.py
"""

import pytest
from pathlib import Path
from langchain_core.documents import Document

from src.loader import (
    extract_text_from_pdf,
    extract_text_from_txt,
    pages_to_documents,
    load_file,
    extract_text,
    SUPPORTED_EXTENSIONS,
)


# ──────────────────────────────────────────────────────────────
# extract_text_from_pdf
# ──────────────────────────────────────────────────────────────

class TestExtractPdf:
    def test_returns_list_of_pages(self, test_pdf_path):
        pages = extract_text_from_pdf(test_pdf_path)
        assert isinstance(pages, list)
        assert len(pages) >= 1

    def test_page_structure(self, test_pdf_path):
        pages = extract_text_from_pdf(test_pdf_path)
        for page in pages:
            assert "text" in page
            assert "page_num" in page
            assert "file_path" in page
            assert isinstance(page["text"], str)
            assert isinstance(page["page_num"], int)

    def test_page_numbering_starts_at_one(self, test_pdf_path):
        pages = extract_text_from_pdf(test_pdf_path)
        assert pages[0]["page_num"] == 1

    def test_content_is_meaningful(self, test_pdf_path):
        pages = extract_text_from_pdf(test_pdf_path)
        full_text = " ".join(p["text"] for p in pages)
        assert "Spring Boot" in full_text or "Introduction" in full_text

    def test_nonexistent_file_returns_empty(self):
        pages = extract_text_from_pdf(Path("nonexistent_file.pdf"))
        assert pages == []

    def test_file_path_stored_in_metadata(self, test_pdf_path):
        pages = extract_text_from_pdf(test_pdf_path)
        assert pages[0]["file_path"] == str(test_pdf_path)


# ──────────────────────────────────────────────────────────────
# extract_text_from_txt
# ──────────────────────────────────────────────────────────────

class TestExtractTxt:
    def test_returns_list_of_blocks(self, test_txt_path):
        pages = extract_text_from_txt(test_txt_path)
        assert isinstance(pages, list)
        assert len(pages) >= 1

    def test_block_structure(self, test_txt_path):
        pages = extract_text_from_txt(test_txt_path)
        for page in pages:
            assert "text" in page
            assert "page_num" in page
            assert "file_path" in page

    def test_content_correct(self, test_txt_path):
        pages = extract_text_from_txt(test_txt_path)
        full_text = " ".join(p["text"] for p in pages)
        assert "congés payés" in full_text.lower() or "règlement" in full_text.lower()

    def test_nonexistent_file_returns_empty(self):
        pages = extract_text_from_txt(Path("nonexistent.txt"))
        assert pages == []


# ──────────────────────────────────────────────────────────────
# pages_to_documents
# ──────────────────────────────────────────────────────────────

class TestPagesToDocuments:
    def test_returns_langchain_documents(self, test_pdf_path):
        pages = extract_text_from_pdf(test_pdf_path)
        docs  = pages_to_documents(pages, "technique", "guide.pdf")
        assert len(docs) >= 1
        assert all(isinstance(d, Document) for d in docs)

    def test_metadata_complete(self, test_pdf_path):
        pages = extract_text_from_pdf(test_pdf_path)
        docs  = pages_to_documents(pages, "rh", "reglement.pdf")
        for doc in docs:
            assert doc.metadata["categorie"] == "rh"
            assert doc.metadata["source"]    == "reglement.pdf"
            assert "page"        in doc.metadata
            assert "chunk_index" in doc.metadata

    def test_empty_pages_returns_empty(self):
        docs = pages_to_documents([], "technique", "empty.pdf")
        assert docs == []

    def test_chunks_respect_size_limit(self, test_pdf_path):
        from config import CHUNK_SIZE
        pages = extract_text_from_pdf(test_pdf_path)
        docs  = pages_to_documents(pages, "technique", "guide.pdf")
        # Les chunks peuvent légèrement dépasser CHUNK_SIZE à cause du chevauchement
        assert all(len(d.page_content) <= CHUNK_SIZE * 1.5 for d in docs)


# ──────────────────────────────────────────────────────────────
# extract_text (dispatcher)
# ──────────────────────────────────────────────────────────────

class TestExtractDispatcher:
    def test_pdf_dispatched_correctly(self, test_pdf_path):
        pages = extract_text(test_pdf_path)
        assert len(pages) >= 1

    def test_txt_dispatched_correctly(self, test_txt_path):
        pages = extract_text(test_txt_path)
        assert len(pages) >= 1

    def test_unsupported_extension_raises(self, tmp_path):
        bad_file = tmp_path / "file.xyz"
        bad_file.write_text("contenu")
        with pytest.raises(ValueError, match="Format non supporté"):
            extract_text(bad_file)


# ──────────────────────────────────────────────────────────────
# load_file
# ──────────────────────────────────────────────────────────────

class TestLoadFile:
    def test_returns_documents(self, test_pdf_path):
        docs = load_file(test_pdf_path, "technique")
        assert len(docs) >= 1
        assert all(isinstance(d, Document) for d in docs)

    def test_categorie_assigned(self, test_txt_path):
        docs = load_file(test_txt_path, "rh")
        assert all(d.metadata["categorie"] == "rh" for d in docs)


# ──────────────────────────────────────────────────────────────
# SUPPORTED_EXTENSIONS
# ──────────────────────────────────────────────────────────────

def test_supported_extensions_contains_pdf():
    assert ".pdf" in SUPPORTED_EXTENSIONS

def test_supported_extensions_contains_docx():
    assert ".docx" in SUPPORTED_EXTENSIONS

def test_supported_extensions_contains_txt():
    assert ".txt" in SUPPORTED_EXTENSIONS
