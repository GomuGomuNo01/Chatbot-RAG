"""
Tests unitaires — src/retriever.py
"""

from langchain_core.documents import Document

from src.retriever import format_sources

# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────


def make_doc(
    content: str,
    fichier: str = "guide.pdf",
    page: int = 1,
    categorie: str = "technique",
    score: float = 0.85,
) -> Document:
    return Document(
        page_content=content,
        metadata={
            "source": fichier,
            "page": page,
            "categorie": categorie,
            "similarity_score": score,
        },
    )


# ──────────────────────────────────────────────────────────────
# format_sources
# ──────────────────────────────────────────────────────────────


class TestFormatSources:
    def test_empty_input_returns_empty_list(self):
        assert format_sources([]) == []

    def test_single_document_structure(self):
        docs = [make_doc("Contenu test", "guide.pdf", 3, "technique", 0.87)]
        sources = format_sources(docs)
        assert len(sources) == 1
        s = sources[0]
        assert s["fichier"] == "guide.pdf"
        assert s["page"] == 3
        assert s["categorie"] == "technique"
        assert s["score"] == 0.87

    def test_extrait_is_truncated(self):
        long_text = "A" * 300
        docs = [make_doc(long_text)]
        sources = format_sources(docs)
        # L'extrait doit faire ≤ 153 caractères (150 + "...")
        assert len(sources[0]["extrait"]) <= 154

    def test_deduplication_same_page(self):
        """Deux chunks de la même page ne doivent produire qu'une source."""
        docs = [
            make_doc("Premier chunk de la page 1", "doc.pdf", 1, "rh", 0.9),
            make_doc("Deuxième chunk de la page 1", "doc.pdf", 1, "rh", 0.8),
        ]
        sources = format_sources(docs)
        assert len(sources) == 1

    def test_deduplication_different_pages(self):
        """Deux chunks de pages différentes doivent produire deux sources."""
        docs = [
            make_doc("Contenu page 1", "doc.pdf", 1, "juridique", 0.9),
            make_doc("Contenu page 2", "doc.pdf", 2, "juridique", 0.8),
        ]
        sources = format_sources(docs)
        assert len(sources) == 2

    def test_deduplication_different_files(self):
        """Même page dans deux fichiers différents = deux sources."""
        docs = [
            make_doc("Contenu A", "fichier_a.pdf", 1, "technique", 0.9),
            make_doc("Contenu B", "fichier_b.pdf", 1, "technique", 0.8),
        ]
        sources = format_sources(docs)
        assert len(sources) == 2

    def test_multiple_categories(self):
        docs = [
            make_doc("Tech content", "guide.pdf", 1, "technique", 0.9),
            make_doc("RH content", "rh.pdf", 1, "rh", 0.8),
            make_doc("Juridique content", "contrat.pdf", 1, "juridique", 0.7),
        ]
        sources = format_sources(docs)
        categories = {s["categorie"] for s in sources}
        assert categories == {"technique", "rh", "juridique"}

    def test_extrait_content_matches_doc(self):
        docs = [make_doc("Contenu de test spécifique")]
        sources = format_sources(docs)
        assert "Contenu de test spécifique" in sources[0]["extrait"]

    def test_missing_score_defaults_to_zero(self):
        doc = Document(
            page_content="Contenu",
            metadata={"source": "doc.pdf", "page": 1, "categorie": "technique"},
        )
        sources = format_sources([doc])
        assert sources[0]["score"] == 0

    def test_unknown_source_falls_back(self):
        doc = Document(page_content="Contenu", metadata={})
        sources = format_sources([doc])
        assert sources[0]["fichier"] == "Inconnu"
