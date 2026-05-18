"""
memory.py — Historique conversationnel compressé.

Refonte v2 : extraction de topics agnostique du domaine (acronymes,
mots-clés longs, identifiants alphanumériques). Plus aucune logique
juridique/RH. Compression :
- Les échanges anciens sont résumés en une ligne.
- Les N plus récents sont gardés intégralement avec réponses tronquées.
"""

import logging
import re

from config import MEMORY_MAX_EXCHANGES

logger = logging.getLogger(__name__)

_MAX_ANSWER_CHARS = 150
_DETAIL_EXCHANGES = 2

_STOP_WORDS: frozenset[str] = frozenset(
    {
        "les",
        "des",
        "que",
        "qui",
        "dans",
        "pour",
        "avec",
        "sur",
        "par",
        "une",
        "est",
        "sont",
        "était",
        "être",
        "avoir",
        "fait",
        "peut",
        "doit",
        "votre",
        "notre",
        "leur",
        "leurs",
        "cette",
        "aussi",
        "mais",
        "comme",
        "plus",
        "tout",
        "bien",
        "même",
        "donc",
        "alors",
        "the",
        "and",
        "are",
        "was",
        "were",
        "that",
        "this",
        "with",
        "from",
        "have",
        "has",
        "had",
        "been",
        "their",
        "they",
        "these",
    }
)


class ConversationMemory:
    """Mémoire conversationnelle compactée."""

    def __init__(self, max_exchanges: int = MEMORY_MAX_EXCHANGES) -> None:
        self.max_exchanges = max_exchanges
        self._history: list[tuple[str, str]] = []
        self._topics: list[str] = []

    def add_exchange(self, question: str, answer: str) -> None:
        self._history.append((question, answer))
        if len(self._history) > self.max_exchanges:
            self._history = self._history[-self.max_exchanges :]
        self._update_topics(question, answer)

    def clear(self) -> None:
        self._history = []
        self._topics = []
        logger.info("Historique conversationnel effacé.")

    def _update_topics(self, question: str, answer: str) -> None:
        """Extraction générique : acronymes + identifiants + mots longs."""
        combined = f"{question} {answer}"

        acronyms = re.findall(r"\b[A-Z]{2,8}\b", combined)
        # Identifiants alphanumériques avec tirets/chiffres (codes, refs, etc.)
        ids = re.findall(r"\b[A-Z]?\d[\w\-\.]{1,15}\b", combined)
        long_words = [
            w
            for w in re.findall(r"\b[a-zéèêëàâùûîïôœç]{8,}\b", combined.lower())
            if w not in _STOP_WORDS
        ]

        new = list(dict.fromkeys(acronyms + ids[:5] + long_words[:5]))[:10]
        merged = new + [t for t in self._topics if t not in new]
        self._topics = merged[:15]

    def get_topics(self) -> list[str]:
        return self._topics.copy()

    def format_compact(self) -> str:
        """Version condensée pour la réécriture de requête."""
        if not self._history:
            return ""
        recent = self._history[-2:]
        lines: list[str] = []
        for q, a in recent:
            lines.append(f"Q: {q.strip()}")
            short = a.strip()[:120]
            if len(a) > 120:
                short += "…"
            lines.append(f"R: {short}")
        return "\n".join(lines)

    def format_for_prompt(self) -> str:
        """Historique structuré pour le prompt principal."""
        if not self._history:
            return ""
        lines: list[str] = []

        old = self._history[:-_DETAIL_EXCHANGES] if len(self._history) > _DETAIL_EXCHANGES else []
        if old:
            summary = " | ".join(q.strip()[:60] for q, _ in old)
            lines.append(f"[Échanges précédents : {summary}]")
            lines.append("")

        recent = (
            self._history[-_DETAIL_EXCHANGES:]
            if len(self._history) >= _DETAIL_EXCHANGES
            else self._history
        )
        if recent:
            lines.append("Historique récent :")
            for q, a in recent:
                lines.append(f"  Utilisateur : {q.strip()}")
                a_short = a.strip()
                if len(a_short) > _MAX_ANSWER_CHARS:
                    cut = a_short[:_MAX_ANSWER_CHARS]
                    last_period = max(cut.rfind(". "), cut.rfind(".\n"), cut.rfind(" : "))
                    if last_period > 80:
                        cut = cut[: last_period + 1]
                    a_short = cut + " […]"
                lines.append(f"  Assistant   : {a_short}")
                lines.append("")
        return "\n".join(lines).rstrip()

    def get_history(self) -> list[tuple[str, str]]:
        return self._history.copy()

    @property
    def is_empty(self) -> bool:
        return len(self._history) == 0

    @property
    def exchange_count(self) -> int:
        return len(self._history)
