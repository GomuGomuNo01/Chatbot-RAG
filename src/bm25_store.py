"""
bm25_store.py — Index BM25 léger pour la recherche lexicale.

Tient à jour un index BM25 (algorithme Okapi BM25 réimplémenté en pur Python,
pas de dépendance externe) en parallèle de FAISS. Permet une recherche hybride
sémantique + lexicale fusionnée par RRF (cf. retriever.py).

Persisté dans `data/bm25_index.pkl` — reconstruit en même temps que l'index FAISS.
"""

import logging
import math
import pickle
import re
from collections import Counter
from pathlib import Path

# Stemming optionnel (nltk). Si absent, BM25 reste fonctionnel sans stemming.
try:
    from nltk.stem import SnowballStemmer as _SnowballStemmer
    _stemmer_fr = _SnowballStemmer("french")
    _stemmer_en = _SnowballStemmer("english")
    _HAS_STEMMER = True
except ImportError:
    _stemmer_fr = _stemmer_en = None
    _HAS_STEMMER = False

from config import BM25_INDEX_FILE
from langchain_core.documents import Document

logger = logging.getLogger(__name__)

# Tokenisation simple : minuscules, accents conservés, mots de 2+ caractères.
# Découpe sur ponctuation et espaces. Conserve les motifs alphanumériques
# (utile pour codes, références, mots techniques) sans logique de domaine.
_TOKEN_RE = re.compile(r"[a-z0-9àâäéèêëîïôöùûüç_-]{2,}", re.IGNORECASE)

# Stop-words multilingues FR/EN basiques (volontairement courts — BM25 fait le reste)
_STOP_WORDS: frozenset[str] = frozenset(
    {
        "le", "la", "les", "un", "une", "des", "du", "de", "et", "ou", "que",
        "qui", "quoi", "ce", "cette", "ces", "se", "sa", "son", "ses", "leur",
        "pour", "par", "avec", "sur", "dans", "en", "au", "aux", "est", "sont",
        "the", "a", "an", "of", "and", "or", "to", "in", "on", "at", "for",
        "with", "as", "is", "are", "was", "were", "by", "this", "that", "these",
    }
)


def _stem(token: str) -> str:
    """Applique le stemming Snowball FR puis EN (gracieux si nltk absent)."""
    if not _HAS_STEMMER:
        return token
    try:
        return _stemmer_fr.stem(token)
    except Exception:
        return token


def _tokenize(text: str) -> list[str]:
    raw = [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOP_WORDS]
    # Stemming : "indexation" et "indexer" → même racine
    stemmed = [_stem(t) for t in raw]
    # Bigrammes : "code_travail", "droit_travail" — forte valeur discriminante
    # pour les noms propres composés et références (ex. "Code du Travail")
    bigrams = [f"{stemmed[i]}_{stemmed[i+1]}" for i in range(len(stemmed) - 1)]
    return stemmed + bigrams


class BM25Index:
    """
    Implémentation Okapi BM25 minimaliste, persistable.
    Stocke la liste des chunks et leurs métadonnées pour ressortir des
    `Document` LangChain lors de la recherche.
    """

    K1 = 1.8   # plus élevé que le défaut (1.5) : favorise les docs avec répétitions du terme
    B  = 0.75

    def __init__(self) -> None:
        self.docs: list[dict] = []           # {"text": str, "metadata": dict}
        self.tokens_per_doc: list[list[str]] = []
        self.freqs: list[Counter] = []       # term frequencies par doc
        self.doc_len: list[int] = []
        self.avg_dl: float = 0.0
        self.df: Counter = Counter()         # document frequency par terme
        self.idf: dict[str, float] = {}

    def fit(self, documents: list[Document]) -> None:
        """(Re)construit l'index depuis zéro."""
        self.docs = []
        self.tokens_per_doc = []
        self.freqs = []
        self.doc_len = []
        self.df = Counter()

        for d in documents:
            tokens = _tokenize(d.page_content)
            if not tokens:
                continue
            self.docs.append({"text": d.page_content, "metadata": dict(d.metadata)})
            self.tokens_per_doc.append(tokens)
            self.freqs.append(Counter(tokens))
            self.doc_len.append(len(tokens))
            for term in set(tokens):
                self.df[term] += 1

        n = len(self.docs)
        self.avg_dl = (sum(self.doc_len) / n) if n else 0.0

        # IDF avec lissage Robertson (« BM25+ »)
        self.idf = {}
        for term, df in self.df.items():
            self.idf[term] = math.log(1 + (n - df + 0.5) / (df + 0.5))

        logger.info(f"[BM25] Index construit : {n} chunks, |vocab|={len(self.df)}")

    def search(
        self,
        query: str,
        k: int = 30,
        workspace: str | None = None,
    ) -> list[tuple[Document, float]]:
        """
        Recherche les k chunks les plus pertinents pour `query`.
        Filtrage workspace appliqué après le scoring (peu coûteux à cette échelle).
        """
        if not self.docs:
            return []
        q_tokens = _tokenize(query)
        if not q_tokens:
            return []

        scores: list[tuple[int, float]] = []
        for i, freqs in enumerate(self.freqs):
            if workspace and self.docs[i]["metadata"].get("workspace") != workspace:
                continue
            score = 0.0
            dl = self.doc_len[i]
            for term in q_tokens:
                if term not in freqs:
                    continue
                f = freqs[term]
                idf = self.idf.get(term, 0.0)
                denom = f + self.K1 * (1 - self.B + self.B * dl / max(self.avg_dl, 1.0))
                score += idf * (f * (self.K1 + 1)) / denom
            if score > 0:
                scores.append((i, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        results: list[tuple[Document, float]] = []
        for idx, sc in scores[:k]:
            entry = self.docs[idx]
            results.append((Document(page_content=entry["text"], metadata=dict(entry["metadata"])), sc))
        return results

    def save(self, path: Path = BM25_INDEX_FILE) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(
            pickle.dumps(
                {
                    "docs": self.docs,
                    "freqs": self.freqs,
                    "doc_len": self.doc_len,
                    "avg_dl": self.avg_dl,
                    "df": dict(self.df),
                    "idf": self.idf,
                }
            )
        )
        logger.info(f"[BM25] Sauvegardé : {path}")

    @classmethod
    def load(cls, path: Path = BM25_INDEX_FILE) -> "BM25Index | None":
        if not path.exists():
            return None
        try:
            data = pickle.loads(path.read_bytes())
            obj = cls()
            obj.docs = data["docs"]
            obj.freqs = data["freqs"]
            obj.doc_len = data["doc_len"]
            obj.avg_dl = data["avg_dl"]
            obj.df = Counter(data["df"])
            obj.idf = data["idf"]
            logger.info(f"[BM25] Chargé : {len(obj.docs)} chunks")
            return obj
        except Exception as e:
            logger.warning(f"[BM25] Chargement échoué : {e}")
            return None


# ──────────────────────────────────────────────────────────────
# Singleton
# ──────────────────────────────────────────────────────────────

_instance: BM25Index | None = None


def get_bm25_index() -> BM25Index | None:
    """Retourne l'index BM25 (lazy load). None si pas encore construit."""
    global _instance
    if _instance is None:
        _instance = BM25Index.load()
    return _instance


def reset_bm25_index() -> None:
    """Invalide le singleton (à appeler après une ré-indexation)."""
    global _instance
    _instance = None


def rebuild_bm25(documents: list[Document]) -> BM25Index:
    """(Re)construit puis persiste l'index BM25 depuis une liste de documents."""
    idx = BM25Index()
    idx.fit(documents)
    idx.save()
    global _instance
    _instance = idx
    return idx
