"""
Embedder : génération des embeddings avec optimisations de performance.

Trois modes (ordre de priorité) :
  1. Production (HF_TOKEN valide) : huggingface_hub.InferenceClient
       → embed_documents() envoie les chunks en BATCH (N textes/appel API)
       → fallback threads parallèles si le batch API échoue
  2. Fallback local automatique (HF_TOKEN expiré/invalide) :
       → sentence-transformers CPU (déclenché sur erreur 401 à l'init)
       → aucune interruption de service
  3. Développement local (sans HF_TOKEN) : sentence-transformers local
       → batch_size=32, compatible sentence-transformers >= 3.x
"""

import logging
from concurrent.futures import ThreadPoolExecutor

from config import EMBEDDING_MODEL
from langchain_core.embeddings import Embeddings

logger = logging.getLogger(__name__)

_embeddings_instance = None
_HF_MODEL_ID = f"sentence-transformers/{EMBEDDING_MODEL}"


class _InferenceClientEmbeddings(Embeddings):
    """
    Embeddings via huggingface_hub.InferenceClient (0 RAM locale).

    Stratégie embed_documents :
      1. Batch API : envoie _BATCH_SIZE textes en un seul appel → optimal
      2. Fallback threads : _MAX_WORKERS appels parallèles si le batch échoue
    """

    _BATCH_SIZE = 32  # textes par appel API batch
    _MAX_WORKERS = 8  # threads parallèles (fallback)

    def __init__(self, token: str, model: str):
        from huggingface_hub import InferenceClient

        self._client = InferenceClient(model=model, token=token)

    # ── Embedding d'un seul texte (query + fallback interne) ────────────────

    def _embed(self, text: str) -> list[float]:
        """Embed un texte unique avec 3 tentatives et backoff exponentiel."""
        import time

        last_exc = None
        for attempt in range(3):
            try:
                result = self._client.feature_extraction(text)
                return self._postprocess_single(result)
            except Exception as exc:
                last_exc = exc
                wait = 2**attempt  # 1 s → 2 s → 4 s
                logger.warning(
                    f"HF API erreur (tentative {attempt + 1}/3) : {exc} — "
                    f"nouvelle tentative dans {wait}s…"
                )
                time.sleep(wait)
        raise RuntimeError(f"L'API HuggingFace a échoué 3 fois de suite : {last_exc}")

    # ── Embedding d'un lot de textes en 1 appel API ──────────────────────────

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Envoie N textes en un seul appel API.
        Beaucoup plus rapide que N appels séquentiels.

        Raises :
            RuntimeError si l'API échoue 3 fois de suite.
        """
        import time

        import numpy as np

        last_exc = None
        for attempt in range(3):
            try:
                result = self._client.feature_extraction(texts)
                break
            except Exception as exc:
                last_exc = exc
                wait = 2**attempt
                logger.warning(
                    f"HF API batch erreur (tentative {attempt + 1}/3) : {exc} — "
                    f"retente dans {wait}s…"
                )
                time.sleep(wait)
        else:
            raise RuntimeError(f"L'API HuggingFace batch a échoué 3 fois de suite : {last_exc}")

        # result : np.ndarray de forme [N, seq_len, dim] ou [N, dim]
        arr = np.array(result, dtype=np.float32)
        if arr.ndim == 3:
            arr = arr.mean(axis=1)  # mean pooling : [N, seq_len, dim] → [N, dim]
        # arr.ndim == 2 : [N, dim] (déjà poolé côté serveur)

        # L2-normalisation vectorisée
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1.0, norms)
        return (arr / norms).tolist()

    # ── Post-traitement résultat single-text ─────────────────────────────────

    @staticmethod
    def _postprocess_single(result) -> list[float]:
        """Normalise le résultat d'un appel single-text (pooling + L2 norm)."""
        import math

        vec = result.tolist() if hasattr(result, "tolist") else list(result)
        # L'API peut renvoyer [seq_len × dim] → mean pooling
        if vec and isinstance(vec[0], list):
            dim = len(vec[0])
            vec = [sum(row[j] for row in vec) / len(vec) for j in range(dim)]
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [x / norm for x in vec]
        return vec

    # ── Interface publique ────────────────────────────────────────────────────

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """
        Embed une liste de chunks avec la stratégie la plus rapide disponible :

          1. Batch API (1 appel / _BATCH_SIZE chunks) → idéal
          2. Fallback : _MAX_WORKERS appels en parallèle par lot
        """
        if not texts:
            return []

        n_batches = (len(texts) + self._BATCH_SIZE - 1) // self._BATCH_SIZE
        logger.info(
            f"  Embedding {len(texts)} chunks en {n_batches} batch(s) de {self._BATCH_SIZE}…"
        )

        results: list[list[float]] = []

        for i in range(0, len(texts), self._BATCH_SIZE):
            batch = texts[i : i + self._BATCH_SIZE]
            batch_num = i // self._BATCH_SIZE + 1
            try:
                embeddings = self._embed_batch(batch)
                results.extend(embeddings)
                logger.debug(
                    f"    Batch {batch_num}/{n_batches} ({len(batch)} chunks) → API batch ✓"
                )
            except Exception as e:
                # Fallback : threads parallèles pour ce lot
                workers = min(self._MAX_WORKERS, len(batch))
                logger.warning(
                    f"    Batch {batch_num}/{n_batches} : API batch indisponible "
                    f"({e}) — fallback {workers} threads parallèles…"
                )
                with ThreadPoolExecutor(max_workers=workers) as executor:
                    results.extend(executor.map(self._embed, batch))

        return results

    def embed_query(self, text: str) -> list[float]:
        """Embed une requête (appel single, toujours rapide)."""
        return self._embed(text)


# ============================================================
# FACTORY — retourne l'instance adaptée à l'environnement
# ============================================================


def _make_local_embeddings() -> Embeddings:
    """
    Charge le modèle sentence-transformers en local (CPU).

    Compatibilité sentence-transformers >= 3.x :
    - show_progress_bar retiré des encode_kwargs (géré par verbose= sur le modèle)
    - batch_size conservé pour l'efficacité
    """
    from langchain_huggingface import HuggingFaceEmbeddings

    logger.info(f"Embeddings locaux : {EMBEDDING_MODEL} (CPU, batch_size=32)")
    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={
            "normalize_embeddings": True,
            "batch_size": 32,  # compatible toutes versions
        },
    )


def get_embeddings() -> Embeddings:
    """
    Retourne l'instance d'embeddings (singleton).

    Ordre de priorité :
      1. HF_TOKEN valide  → InferenceClient API (0 RAM, batch optimisé)
      2. HF_TOKEN expiré  → fallback local sentence-transformers (CPU)
      3. Pas de HF_TOKEN  → local sentence-transformers (CPU)
    """
    global _embeddings_instance
    import os

    if _embeddings_instance is None:
        hf_token = os.getenv("HF_TOKEN", "")

        if hf_token:
            logger.info(
                f"Embeddings via HuggingFace InferenceClient : {_HF_MODEL_ID} "
                f"(batch={_InferenceClientEmbeddings._BATCH_SIZE}, "
                f"workers_fallback={_InferenceClientEmbeddings._MAX_WORKERS})"
            )
            # Valider le token avec un appel de test minimal
            try:
                candidate = _InferenceClientEmbeddings(token=hf_token, model=_HF_MODEL_ID)
                candidate._embed("test")  # appel de validation (~100ms)
                _embeddings_instance = candidate
                logger.info("  InferenceClient validé : OK")
            except Exception as e:
                # Token expiré / invalide / quota dépassé → fallback local
                logger.warning(
                    f"  InferenceClient indisponible ({type(e).__name__}: {e!s:.120}) "
                    "— fallback modele local sentence-transformers"
                )
                _embeddings_instance = _make_local_embeddings()
        else:
            _embeddings_instance = _make_local_embeddings()

        logger.info("  Embeddings initialises : OK")

    return _embeddings_instance


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Utilitaire pour les tests."""
    return get_embeddings().embed_documents(texts)
