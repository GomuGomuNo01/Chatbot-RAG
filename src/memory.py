"""
Memory : gestion de l'historique conversationnel
"""

import logging
from typing import List, Tuple
from config import MEMORY_MAX_EXCHANGES

logger = logging.getLogger(__name__)


class ConversationMemory:
    """
    Gère l'historique de la conversation.
    Conserve les N derniers échanges (question + réponse).
    """

    def __init__(self, max_exchanges: int = MEMORY_MAX_EXCHANGES):
        self.max_exchanges = max_exchanges
        self._history: List[Tuple[str, str]] = []

    def add_exchange(self, question: str, answer: str):
        """Ajoute un échange question/réponse à l'historique."""
        self._history.append((question, answer))

        # Garder seulement les N derniers échanges
        if len(self._history) > self.max_exchanges:
            self._history = self._history[-self.max_exchanges:]

        logger.debug(
            f"Historique mis à jour : "
            f"{len(self._history)}/{self.max_exchanges} échanges"
        )

    def get_history(self) -> List[Tuple[str, str]]:
        """Retourne l'historique complet."""
        return self._history.copy()

    def format_for_prompt(self) -> str:
        """
        Formate l'historique pour l'injecter dans le prompt LLM.

        Returns:
            str avec les échanges précédents formatés
        """
        if not self._history:
            return ""

        lines = ["Historique de la conversation :"]
        for question, answer in self._history:
            lines.append(f"Utilisateur : {question}")
            lines.append(f"Assistant   : {answer}")
            lines.append("")

        return "\n".join(lines)

    def clear(self):
        """Efface l'historique (nouvelle conversation)."""
        self._history = []
        logger.info("Historique conversationnel effacé.")

    @property
    def is_empty(self) -> bool:
        return len(self._history) == 0

    @property
    def exchange_count(self) -> int:
        return len(self._history)