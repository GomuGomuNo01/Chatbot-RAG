"""
Tests unitaires — src/chain.py et src/memory.py (refonte v2)
Les tests du RAGChain mockent le LLM et le retriever hybride pour éviter
tout appel réseau pendant la CI.
"""

from unittest.mock import MagicMock, patch

import src.chain  # noqa: F401 — requis pour que @patch("src.chain.*") fonctionne en Python 3.12
from src.memory import ConversationMemory

# ──────────────────────────────────────────────────────────────
# ConversationMemory
# ──────────────────────────────────────────────────────────────


class TestConversationMemory:
    def test_initial_state_is_empty(self):
        mem = ConversationMemory()
        assert mem.is_empty
        assert mem.exchange_count == 0

    def test_add_exchange_increments_count(self):
        mem = ConversationMemory()
        mem.add_exchange("Question", "Réponse")
        assert mem.exchange_count == 1
        assert not mem.is_empty

    def test_max_exchanges_respected(self):
        mem = ConversationMemory(max_exchanges=3)
        for i in range(10):
            mem.add_exchange(f"Q{i}", f"R{i}")
        assert mem.exchange_count == 3

    def test_oldest_exchanges_evicted(self):
        mem = ConversationMemory(max_exchanges=2)
        mem.add_exchange("Q0", "R0")
        mem.add_exchange("Q1", "R1")
        mem.add_exchange("Q2", "R2")
        history = mem.get_history()
        assert history[0][0] == "Q1"
        assert history[1][0] == "Q2"

    def test_clear_resets_memory(self):
        mem = ConversationMemory()
        mem.add_exchange("Q", "R")
        mem.clear()
        assert mem.is_empty
        assert mem.exchange_count == 0

    def test_format_for_prompt_empty(self):
        mem = ConversationMemory()
        assert mem.format_for_prompt() == ""

    def test_format_for_prompt_contains_exchanges(self):
        mem = ConversationMemory()
        mem.add_exchange("Bonjour", "Bonjour ! Comment puis-je vous aider ?")
        result = mem.format_for_prompt()
        assert "Bonjour" in result
        assert "Utilisateur" in result
        assert "Assistant" in result

    def test_get_history_returns_copy(self):
        mem = ConversationMemory()
        mem.add_exchange("Q", "R")
        history = mem.get_history()
        history.clear()
        assert mem.exchange_count == 1


# ──────────────────────────────────────────────────────────────
# RAGChain — fallback "je ne sais pas"
# ──────────────────────────────────────────────────────────────


class TestRAGChainFallback:
    """Tests du chemin « aucun document trouvé » sans appel réseau."""

    @patch("src.chain._safe_embed_query", return_value=[])
    @patch("src.chain.get_llm")
    @patch("src.chain.hybrid_search", return_value=[])
    def test_no_docs_returns_fallback_message(self, mock_search, mock_get_llm, mock_embed):
        from src.chain import RAGChain

        mock_get_llm.return_value = MagicMock()
        chain = RAGChain()
        mem = ConversationMemory()
        result = chain.ask("Question sans résultat", mem)

        assert isinstance(result["answer"], str)
        assert len(result["answer"]) > 0
        assert result["sources"] == []
        assert result["question"] == "Question sans résultat"

    @patch("src.chain._safe_embed_query", return_value=[])
    @patch("src.chain.get_llm")
    @patch("src.chain.hybrid_search", return_value=[])
    def test_fallback_mentions_workspace_when_filtered(self, mock_search, mock_get_llm, mock_embed):
        from src.chain import RAGChain

        mock_get_llm.return_value = MagicMock()
        chain = RAGChain()
        mem = ConversationMemory()
        result = chain.ask("Question filtrée", mem, workspace="marketing")

        assert "marketing" in result["answer"]

    @patch("src.chain._safe_embed_query", return_value=[])
    @patch("src.chain.get_llm")
    @patch("src.chain.hybrid_search", return_value=[])
    def test_fallback_adds_to_memory(self, mock_search, mock_get_llm, mock_embed):
        from src.chain import RAGChain

        mock_get_llm.return_value = MagicMock()
        chain = RAGChain()
        mem = ConversationMemory()
        chain.ask("Question", mem)
        assert mem.exchange_count == 1


# ──────────────────────────────────────────────────────────────
# RAGChain — chemin nominal
# ──────────────────────────────────────────────────────────────


class TestRAGChainWithDocuments:
    def _make_mock_doc(self, content="Contenu de test", fichier="doc.pdf", page=1):
        from langchain_core.documents import Document

        return Document(
            page_content=content,
            metadata={
                "source": fichier,
                "page": page,
                "workspace": "test",
                "similarity_score": 0.85,
            },
        )

    @patch("src.chain._safe_embed_query", return_value=[])
    @patch("src.chain.get_llm")
    @patch("src.chain.hybrid_search")
    def test_returns_answer_and_sources(self, mock_search, mock_get_llm, mock_embed):
        from src.chain import RAGChain

        mock_search.return_value = [self._make_mock_doc()]
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = "Voici la réponse de test."
        mock_get_llm.return_value = MagicMock()

        chain = RAGChain()
        chain.chain = mock_chain

        mem = ConversationMemory()
        result = chain.ask("Question de test", mem)

        assert result["answer"] == "Voici la réponse de test."
        assert len(result["sources"]) >= 1
        assert result["question"] == "Question de test"

    @patch("src.chain._safe_embed_query", return_value=[])
    @patch("src.chain.get_llm")
    @patch("src.chain.hybrid_search")
    def test_memory_updated_after_answer(self, mock_search, mock_get_llm, mock_embed):
        from src.chain import RAGChain

        mock_search.return_value = [self._make_mock_doc()]
        mock_chain = MagicMock()
        mock_chain.invoke.return_value = "Réponse."
        mock_get_llm.return_value = MagicMock()

        chain = RAGChain()
        chain.chain = mock_chain

        mem = ConversationMemory()
        chain.ask("Question", mem)
        assert mem.exchange_count == 1
        assert mem.get_history()[0][1] == "Réponse."


# ──────────────────────────────────────────────────────────────
# Workspaces (config)
# ──────────────────────────────────────────────────────────────


class TestWorkspacesConfig:
    def test_valid_keys(self):
        from config import is_valid_workspace_key

        assert is_valid_workspace_key("marketing")
        assert is_valid_workspace_key("project-x")
        assert is_valid_workspace_key("a1")
        assert is_valid_workspace_key("under_score")

    def test_invalid_keys(self):
        from config import is_valid_workspace_key

        assert not is_valid_workspace_key("API")  # majuscule
        assert not is_valid_workspace_key("a")  # trop court
        assert not is_valid_workspace_key("ab cd")  # espace
        assert not is_valid_workspace_key("api")  # réservé
        assert not is_valid_workspace_key("-prefix")  # commence par tiret
