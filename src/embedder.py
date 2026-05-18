"""
Embedder : génération des embeddings via fastembed (ONNX, sans PyTorch).

Deux modes :
  1. Production / Local (défaut) : fastembed.TextEmbedding
       → ONNX runtime, ~37 MB pour BAAI/bge-small-en-v1.5, 0 PyTorch
       → Idéal pour Render free (512 MB RAM)
  2. Fallback : HuggingFaceEmbeddings (sentence-transformers)
       → déclenché si fastembed n'est pas installé
       → nécessite sentence-transformers + PyTorch (dev local uniquement)
"""

import logging

from config import EMBEDDING_MODEL
from langchain_core.embeddings import Embeddings

logger = logging.getLogger(__name__)

_embeddings_instance = None

# Les modèles intfloat/e5 exigent des préfixes "query:" / "passage:" pour de meilleures perfs.
_IS_E5_MODEL = "e5" in EMBEDDING_MODEL.lower()


# ============================================================
# fastembed — ONNX, 0 PyTorch, recommandé en production
# ============================================================


class _FastEmbedEmbeddings(Embeddings):
    """
    Embeddings via fastembed.TextEmbedding (ONNX runtime).
    Compatible Render free plan (512 MB RAM) — pas de PyTorch.
    """

    def __init__(self, model_name: str) -> None:
        from fastembed import TextEmbedding

        self._model = TextEmbedding(model_name=model_name)
        logger.info(f"fastembed initialisé : {model_name}")

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        prefixed = [f"passage: {t}" for t in texts] if _IS_E5_MODEL else texts
        return [list(map(float, v)) for v in self._model.embed(prefixed, batch_size=32)]

    def embed_query(self, text: str) -> list[float]:
        prefixed = f"query: {text}" if _IS_E5_MODEL else text
        return list(map(float, list(self._model.embed([prefixed]))[0]))


# ============================================================
# Fallback local — sentence-transformers (dev uniquement)
# ============================================================


def _is_model_cached(model_name: str) -> bool:
    import os

    cache_dir = os.path.join(
        os.path.expanduser("~"),
        ".cache",
        "huggingface",
        "hub",
        f"models--{model_name.replace('/', '--')}",
    )
    return os.path.isdir(cache_dir)


def _make_local_embeddings() -> Embeddings:
    from langchain_huggingface import HuggingFaceEmbeddings

    cached = _is_model_cached(EMBEDDING_MODEL)
    model_kwargs: dict = {"device": "cpu"}
    if cached:
        model_kwargs["local_files_only"] = True
        logger.info(f"Embeddings locaux : {EMBEDDING_MODEL} (CPU, cache local, hors-ligne)")
    else:
        logger.info(f"Embeddings locaux : {EMBEDDING_MODEL} (CPU, téléchargement…)")

    base = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs=model_kwargs,
        encode_kwargs={"normalize_embeddings": True, "batch_size": 32},
    )

    if not _IS_E5_MODEL:
        return base

    class _Prefixed(Embeddings):
        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            return base.embed_documents([f"passage: {t}" for t in texts])

        def embed_query(self, text: str) -> list[float]:
            return base.embed_query(f"query: {text}")

    return _Prefixed()


# ============================================================
# FACTORY — singleton
# ============================================================


def get_embeddings() -> Embeddings:
    """
    Retourne l'instance d'embeddings (singleton).

    Ordre de priorité :
      1. fastembed (ONNX, 0 PyTorch) — production et dev si installé
      2. HuggingFaceEmbeddings (sentence-transformers) — fallback dev local
    """
    global _embeddings_instance

    if _embeddings_instance is None:
        try:
            _embeddings_instance = _FastEmbedEmbeddings(EMBEDDING_MODEL)
            logger.info("Embeddings initialisés via fastembed (ONNX) : OK")
        except ImportError:
            logger.warning(
                "fastembed non installé — fallback sentence-transformers (dev local uniquement). "
                "Installez fastembed pour la production."
            )
            _embeddings_instance = _make_local_embeddings()
            logger.info("Embeddings initialisés via sentence-transformers : OK")

    return _embeddings_instance


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Utilitaire pour les tests."""
    return get_embeddings().embed_documents(texts)
