"""
cache.py — Cache sémantique des réponses (cost saver).

Quand l'utilisateur pose une question quasi-identique à une précédente (même
workspace), on retourne directement la réponse cachée sans appeler le LLM.

Sémantique : on cache (question, workspace) → (answer, sources, timestamp).
La similarité de question est mesurée via les embeddings déjà disponibles
(get_embeddings). Si la similarité ≥ seuil et que la réponse n'est pas
expirée, on sert depuis le cache.

Persistance : fichier JSON simple. Réinitialisable.
"""

import json
import logging
import math
import time

from config import (
    RESPONSE_CACHE_ENABLED,
    RESPONSE_CACHE_FILE,
    RESPONSE_CACHE_MAX_ENTRIES,
    RESPONSE_CACHE_SIM_THRESHOLD,
    RESPONSE_CACHE_TTL_SECONDS,
)

logger = logging.getLogger(__name__)


class ResponseCache:
    """Cache mémoire + disque, indexé par (workspace, question)."""

    def __init__(self) -> None:
        self.entries: list[dict] = []  # {ws, question, embedding, answer, sources, ts}
        self._load()

    def _load(self) -> None:
        if not RESPONSE_CACHE_FILE.exists():
            return
        try:
            data = json.loads(RESPONSE_CACHE_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                self.entries = data
                logger.info(f"[cache] Chargé : {len(self.entries)} entrée(s)")
        except Exception as e:
            logger.warning(f"[cache] Lecture échouée : {e}")
            self.entries = []

    def _save(self) -> None:
        try:
            RESPONSE_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            RESPONSE_CACHE_FILE.write_text(
                json.dumps(self.entries, ensure_ascii=False), encoding="utf-8"
            )
        except Exception as e:
            logger.warning(f"[cache] Sauvegarde échouée : {e}")

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b, strict=False))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(x * x for x in b))
        return dot / (na * nb) if na and nb else 0.0

    # Mots vides FR+EN : ignorés lors du calcul de chevauchement lexical.
    # On compare uniquement les mots porteurs de sens (noms, verbes, adjectifs).
    _STOP_WORDS: frozenset[str] = frozenset(
        {
            # Français
            "donne",
            "donnes",
            "dis",
            "moi",
            "me",
            "explique",
            "montre",
            "trouve",
            "liste",
            "fais",
            "quels",
            "quelles",
            "quel",
            "quelle",
            "comment",
            "pourquoi",
            "quand",
            "combien",
            "où",
            "qui",
            "que",
            "qu",
            "quoi",
            "de",
            "du",
            "des",
            "le",
            "la",
            "les",
            "un",
            "une",
            "au",
            "aux",
            "en",
            "et",
            "ou",
            "par",
            "pour",
            "sur",
            "dans",
            "avec",
            "sans",
            "est",
            "sont",
            "était",
            "être",
            "avoir",
            "fait",
            "peut",
            "doit",
            "faire",
            "je",
            "tu",
            "il",
            "nous",
            "vous",
            "ils",
            "elles",
            "te",
            "se",
            "ce",
            "cet",
            "cette",
            "ces",
            "son",
            "sa",
            "ses",
            "mon",
            "ma",
            "mes",
            "ton",
            "ta",
            "tes",
            "leur",
            "leurs",
            "y",
            "dont",
            "si",
            "car",
            "mais",
            "ni",
            "or",
            "donc",
            "puis",
            "aussi",
            "très",
            "plus",
            "moins",
            "bien",
            "peu",
            "trop",
            "assez",
            "tout",
            "tous",
            "toute",
            "toutes",
            "même",
            "autre",
            "autres",
            "on",
            "a",
            "façon",
            "façons",
            "manière",
            "manières",
            "moyen",
            "moyens",
            "exemple",
            "exemples",
            "cas",
            "type",
            "types",
            "sorte",
            "sortes",
            "plusieurs",
            "différent",
            "différente",
            "différents",
            "différentes",
            "alors",
            "ainsi",
            "voici",
            "voilà",
            "veut",
            # English
            "what",
            "how",
            "does",
            "can",
            "the",
            "are",
            "why",
            "when",
            "where",
            "which",
            "who",
            "give",
            "tell",
            "explain",
            "show",
            "find",
            "list",
            "do",
            "make",
            "is",
            "was",
            "were",
            "will",
            "would",
            "could",
            "should",
            "have",
            "has",
            "this",
            "that",
            "these",
            "with",
            "from",
            "about",
            "into",
            "their",
            "them",
            "my",
            "an",
            "of",
            "in",
            "at",
            "to",
            "for",
            "by",
            "and",
            "but",
            "not",
            "example",
            "examples",
            "way",
            "ways",
            "kind",
        }
    )

    @classmethod
    def _word_overlap(cls, q1: str, q2: str) -> float:
        """Jaccard sur les mots-clés uniquement (stop words exclus).
        Ex: 'Structures conditionnelles' vs 'Structures itératives' →
        {structures} / {structures, conditionnelles, itératives} = 1/3 = 0.33.
        Évite les faux positifs du cache sur des questions à structure identique
        mais thème différent."""
        import re

        def _keywords(s: str) -> set[str]:
            tokens = re.sub(r"[^\w]", " ", s.lower()).split()
            return {t for t in tokens if t not in cls._STOP_WORDS and len(t) > 2}

        k1, k2 = _keywords(q1), _keywords(q2)
        if not k1 or not k2:
            # Pas de mots-clés → fallback sur tous les tokens
            def _all_tokens(s: str) -> set[str]:
                return set(re.sub(r"[^\w]", " ", s.lower()).split())

            t1, t2 = _all_tokens(q1), _all_tokens(q2)
            return len(t1 & t2) / len(t1 | t2) if t1 | t2 else 0.0
        return len(k1 & k2) / len(k1 | k2)

    def _evict_expired(self) -> None:
        now = time.time()
        self.entries = [
            e for e in self.entries if (now - e.get("ts", 0)) < RESPONSE_CACHE_TTL_SECONDS
        ]

    def lookup(self, question: str, workspace: str | None, embedding: list[float]) -> dict | None:
        """
        Cherche une réponse cachée pour une question similaire.
        Retourne None si rien trouvé ou si le cache est désactivé.
        """
        if not RESPONSE_CACHE_ENABLED or not embedding:
            return None
        self._evict_expired()

        # Seuil Jaccard sur mots-clés (stop words exclus).
        # Sur mots-clés uniquement, 0.65 est strict mais juste :
        # questions identiques → 1.0, même thème reformulé → >0.65,
        # thèmes différents (conditionnelles vs itératives) → <0.50.
        _MIN_WORD_OVERLAP = 0.65

        best: tuple[float, dict] | None = None
        for entry in self.entries:
            if entry.get("ws") != workspace:
                continue
            sim = self._cosine(embedding, entry.get("embedding", []))
            if sim < RESPONSE_CACHE_SIM_THRESHOLD:
                continue
            overlap = self._word_overlap(question, entry.get("question", ""))
            if overlap < _MIN_WORD_OVERLAP:
                logger.debug(
                    f"[cache] SKIP (sim={sim:.3f} ✓ mais overlap={overlap:.2f} < {_MIN_WORD_OVERLAP}) : "
                    f"« {entry.get('question', '')[:60]} »"
                )
                continue
            if best is None or sim > best[0]:
                best = (sim, entry)
        if best:
            logger.info(
                f"[cache] HIT (workspace={workspace}, sim={best[0]:.3f}, "
                f"overlap={self._word_overlap(question, best[1].get('question', '')):.2f}) : "
                f"« {best[1].get('question', '')[:60]}… »"
            )
            return best[1]
        return None

    def store(
        self,
        question: str,
        workspace: str | None,
        embedding: list[float],
        answer: str,
        sources: list[dict],
    ) -> None:
        if not RESPONSE_CACHE_ENABLED or not embedding or not answer:
            return
        self.entries.append(
            {
                "ws": workspace,
                "question": question,
                "embedding": embedding,
                "answer": answer,
                "sources": sources,
                "ts": time.time(),
            }
        )
        # Garde les N plus récentes (LRU par timestamp)
        if len(self.entries) > RESPONSE_CACHE_MAX_ENTRIES:
            self.entries.sort(key=lambda e: e.get("ts", 0), reverse=True)
            self.entries = self.entries[:RESPONSE_CACHE_MAX_ENTRIES]
        self._save()

    def clear(self, workspace: str | None = None) -> int:
        """Vide le cache (entièrement ou pour un workspace). Retourne le nb d'entrées retirées."""
        before = len(self.entries)
        if workspace is None:
            self.entries = []
        else:
            self.entries = [e for e in self.entries if e.get("ws") != workspace]
        self._save()
        return before - len(self.entries)

    def invalidate_workspace(self, workspace: str) -> int:
        """Alias explicite — à appeler après un upload/delete dans un workspace."""
        return self.clear(workspace=workspace)


_cache_instance: ResponseCache | None = None


def get_cache() -> ResponseCache:
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = ResponseCache()
    return _cache_instance


def reset_cache() -> None:
    global _cache_instance
    _cache_instance = None
