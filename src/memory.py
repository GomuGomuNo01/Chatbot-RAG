"""
memory.py — Gestion de l'historique conversationnel

Améliorations v2 :
- Résumé condensé des échanges anciens (économise du contexte LLM)
- format_compact() → version courte pour la réécriture de requête
- format_for_prompt() → version structurée pour la génération de réponse
- Extraction automatique de topics (entités clés) pour contextualiser le retrieval
- Troncature intelligente : les réponses longues sont résumées à ~250 chars
"""

import logging
import re

from config import MEMORY_MAX_EXCHANGES

logger = logging.getLogger(__name__)

# Nb max de caractères par réponse dans le prompt (évite les contextes trop longs)
_MAX_ANSWER_CHARS = 280
# Nb max d'échanges affichés en détail dans le prompt principal
_DETAIL_EXCHANGES = 3


class ConversationMemory:
    """
    Gère l'historique conversationnel avec formatage adaptatif.

    Stratégie :
    - Les N derniers échanges sont conservés intégralement en mémoire.
    - Dans le prompt LLM, seuls les _DETAIL_EXCHANGES plus récents sont
      affichés en détail ; les plus anciens sont condensés.
    - Les réponses très longues sont tronquées pour économiser des tokens.
    """

    def __init__(self, max_exchanges: int = MEMORY_MAX_EXCHANGES):
        self.max_exchanges = max_exchanges
        self._history: list[tuple[str, str]] = []
        # Topics extraits de l'historique (noms, acronymes, entités)
        self._topics: list[str] = []

    # ──────────────────────────────────────────────────────────
    # Ajout / suppression
    # ──────────────────────────────────────────────────────────

    def add_exchange(self, question: str, answer: str) -> None:
        """Ajoute un échange et met à jour les topics."""
        self._history.append((question, answer))
        if len(self._history) > self.max_exchanges:
            self._history = self._history[-self.max_exchanges :]
        self._update_topics(question, answer)
        logger.debug(
            f"Mémoire : {len(self._history)}/{self.max_exchanges} échanges | "
            f"topics : {self._topics}"
        )

    def clear(self) -> None:
        """Efface l'historique et les topics."""
        self._history = []
        self._topics = []
        logger.info("Historique conversationnel effacé.")

    # ──────────────────────────────────────────────────────────
    # Extraction de topics
    # ──────────────────────────────────────────────────────────

    def _update_topics(self, question: str, answer: str) -> None:
        """
        Extrait des entités clés (acronymes, noms propres, mots longs)
        depuis le dernier échange pour enrichir le contexte de recherche.
        """
        combined = f"{question} {answer}"
        # Acronymes (2-6 lettres MAJ)
        acronyms = re.findall(r"\b[A-Z]{2,6}\b", combined)
        # Mots techniques longs (> 7 chars, pas de stop-words)
        _STOP = {
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
            "cette",
            "votre",
            "aussi",
            "mais",
            "comme",
            "peut",
            "doit",
            "être",
            "avoir",
            "fait",
            "plus",
            "tout",
            "bien",
        }
        long_words = [
            w for w in re.findall(r"\b[a-zéèêëàâùûîïôœç]{8,}\b", combined.lower()) if w not in _STOP
        ]

        new_topics = list(dict.fromkeys(acronyms + long_words[:5]))[:8]
        # Fusionner avec les topics existants, garder les 12 plus récents
        all_topics = new_topics + [t for t in self._topics if t not in new_topics]
        self._topics = all_topics[:12]

    def get_topics(self) -> list[str]:
        """Retourne les entités clés de la conversation."""
        return self._topics.copy()

    # ──────────────────────────────────────────────────────────
    # Formatage pour la réécriture de requête (compact)
    # ──────────────────────────────────────────────────────────

    def format_compact(self) -> str:
        """
        Version très condensée de l'historique pour la réécriture de requête.
        Affiche uniquement les 2 derniers échanges, réponses tronquées à 120 chars.
        """
        if not self._history:
            return ""

        recent = self._history[-2:]
        lines = []
        for q, a in recent:
            lines.append(f"Q: {q.strip()}")
            short_a = a.strip()[:120]
            if len(a) > 120:
                short_a += "…"
            lines.append(f"R: {short_a}")
        return "\n".join(lines)

    # ──────────────────────────────────────────────────────────
    # Formatage pour le prompt de génération LLM
    # ──────────────────────────────────────────────────────────

    def format_for_prompt(self) -> str:
        """
        Formate l'historique pour l'injection dans le prompt principal.

        Stratégie :
        - Les échanges anciens (au-delà de _DETAIL_EXCHANGES) sont résumés
          en une ligne : « [Sujets abordés : X, Y, Z] »
        - Les _DETAIL_EXCHANGES plus récents sont affichés intégralement,
          avec les réponses tronquées à _MAX_ANSWER_CHARS.
        """
        if not self._history:
            return ""

        lines: list[str] = []

        # ── Résumé des échanges anciens ──────────────────────
        old = self._history[:-_DETAIL_EXCHANGES] if len(self._history) > _DETAIL_EXCHANGES else []
        if old:
            topics_in_old = []
            for q, _ in old:
                topics_in_old.append(q.strip()[:60])
            summary = " | ".join(topics_in_old)
            lines.append(f"[Échanges précédents — sujets abordés : {summary}]")
            lines.append("")

        # ── Échanges récents en détail ───────────────────────
        recent = (
            self._history[-_DETAIL_EXCHANGES:]
            if len(self._history) >= _DETAIL_EXCHANGES
            else self._history
        )
        if recent:
            lines.append("Historique récent :")
            for q, a in recent:
                lines.append(f"  Utilisateur : {q.strip()}")
                # Tronquer les réponses longues
                a_short = a.strip()
                if len(a_short) > _MAX_ANSWER_CHARS:
                    # Couper à la dernière phrase complète dans la limite
                    cut = a_short[:_MAX_ANSWER_CHARS]
                    last_period = max(cut.rfind(". "), cut.rfind(".\n"), cut.rfind(" : "))
                    if last_period > 80:
                        cut = cut[: last_period + 1]
                    a_short = cut + " […]"
                lines.append(f"  Assistant   : {a_short}")
                lines.append("")

        return "\n".join(lines).rstrip()

    # ──────────────────────────────────────────────────────────
    # Accesseurs
    # ──────────────────────────────────────────────────────────

    def get_history(self) -> list[tuple[str, str]]:
        return self._history.copy()

    @property
    def is_empty(self) -> bool:
        return len(self._history) == 0

    @property
    def exchange_count(self) -> int:
        return len(self._history)
