"""
Tests unitaires — src/retriever.py + src/bm25_store.py (refonte v2)
"""

from langchain_core.documents import Document

from src.bm25_store import BM25Index
from src.retriever import _rrf_fuse, format_sources

# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────


def make_doc(
    content: str,
    fichier: str = "guide.pdf",
    page: int = 1,
    workspace: str = "test",
    score: float = 0.85,
) -> Document:
    return Document(
        page_content=content,
        metadata={
            "source": fichier,
            "page": page,
            "workspace": workspace,
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
        docs = [make_doc("Contenu test", "guide.pdf", 3, "tech", 0.87)]
        sources = format_sources(docs)
        assert len(sources) == 1
        s = sources[0]
        assert s["fichier"] == "guide.pdf"
        assert s["page"] == 3
        assert s["workspace"] == "tech"
        # Un seul document → normalisé à 1.0 (max de l'ensemble)
        assert s["score"] == 1.0

    def test_extrait_is_truncated(self):
        long_text = "A" * 300
        docs = [make_doc(long_text)]
        sources = format_sources(docs)
        assert len(sources[0]["extrait"]) <= 210  # 200 + ellipsis

    def test_deduplication_same_page(self):
        docs = [
            make_doc("Premier chunk de la page 1", "doc.pdf", 1, "ws", 0.9),
            make_doc("Deuxième chunk de la page 1", "doc.pdf", 1, "ws", 0.8),
        ]
        sources = format_sources(docs)
        assert len(sources) == 1

    def test_deduplication_different_pages(self):
        docs = [
            make_doc("Contenu page 1", "doc.pdf", 1, "ws", 0.9),
            make_doc("Contenu page 2", "doc.pdf", 2, "ws", 0.8),
        ]
        assert len(format_sources(docs)) == 2

    def test_deduplication_different_files(self):
        docs = [
            make_doc("Contenu A", "fichier_a.pdf", 1, "ws", 0.9),
            make_doc("Contenu B", "fichier_b.pdf", 1, "ws", 0.8),
        ]
        assert len(format_sources(docs)) == 2

    def test_multiple_workspaces(self):
        docs = [
            make_doc("Tech content", "guide.pdf", 1, "tech", 0.9),
            make_doc("Ops content", "ops.pdf", 1, "ops", 0.8),
            make_doc("Marketing content", "mkt.pdf", 1, "mkt", 0.7),
        ]
        sources = format_sources(docs)
        workspaces = {s["workspace"] for s in sources}
        assert workspaces == {"tech", "ops", "mkt"}

    def test_missing_score_defaults_to_floor(self):
        # Quand aucun score n'est disponible, le plancher _FLOOR=0.35 est appliqué
        doc = Document(
            page_content="Contenu",
            metadata={"source": "doc.pdf", "page": 1, "workspace": "ws"},
        )
        assert format_sources([doc])[0]["score"] == 0.35

    def test_unknown_source_falls_back(self):
        doc = Document(page_content="Contenu", metadata={})
        assert format_sources([doc])[0]["fichier"] == "Inconnu"

    def test_rerank_score_preferred_over_similarity(self):
        doc = Document(
            page_content="x",
            metadata={
                "source": "a.pdf",
                "page": 1,
                "workspace": "ws",
                "similarity_score": 0.5,
                "rerank_score": 0.9,
            },
        )
        # rerank_score est préféré ; doc unique → normalisé à 1.0
        assert format_sources([doc])[0]["score"] == 1.0


# ──────────────────────────────────────────────────────────────
# BM25Index
# ──────────────────────────────────────────────────────────────


class TestBM25:
    def test_empty_search_returns_empty(self):
        idx = BM25Index()
        assert idx.search("query", k=5) == []

    def test_fit_then_search_finds_relevant(self):
        docs = [
            Document(
                page_content="Spring Boot framework Java",
                metadata={"workspace": "tech", "source": "a"},
            ),
            Document(
                page_content="Recette de la tarte aux pommes",
                metadata={"workspace": "cuisine", "source": "b"},
            ),
            Document(
                page_content="Configuration Spring Boot avec annotations",
                metadata={"workspace": "tech", "source": "c"},
            ),
        ]
        idx = BM25Index()
        idx.fit(docs)
        results = idx.search("Spring Boot", k=5)
        assert len(results) >= 1
        contents = [r[0].page_content for r in results]
        assert any("Spring Boot" in c for c in contents)

    def test_workspace_filter(self):
        docs = [
            Document(
                page_content="Java code example", metadata={"workspace": "tech", "source": "a"}
            ),
            Document(
                page_content="Java the book review", metadata={"workspace": "books", "source": "b"}
            ),
        ]
        idx = BM25Index()
        idx.fit(docs)
        results = idx.search("Java", k=5, workspace="tech")
        assert all(r[0].metadata["workspace"] == "tech" for r in results)


# ──────────────────────────────────────────────────────────────
# RRF fusion
# ──────────────────────────────────────────────────────────────


class TestRRF:
    def test_empty_returns_empty(self):
        assert _rrf_fuse([]) == []

    def test_single_list_preserves_order(self):
        docs = [
            make_doc("A", "f.pdf", 1),
            make_doc("B", "f.pdf", 2),
            make_doc("C", "f.pdf", 3),
        ]
        out = _rrf_fuse([(docs, 1.0)])
        assert [d.page_content for d in out] == ["A", "B", "C"]

    def test_fusion_boosts_documents_in_multiple_lists(self):
        d1 = make_doc("shared", "f.pdf", 1)
        d2 = make_doc("only1", "f.pdf", 2)
        d3 = make_doc("shared", "f.pdf", 1)  # same key
        d4 = make_doc("only2", "f.pdf", 3)
        out = _rrf_fuse([([d1, d2], 1.0), ([d3, d4], 1.0)])
        # "shared" doit être en tête
        assert out[0].page_content == "shared"
