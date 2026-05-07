"""
Embedder : génération des embeddings.
- Production (HF_TOKEN défini) : huggingface_hub.InferenceClient — 0 RAM locale.
- Développement local (pas de HF_TOKEN) : sentence-transformers local.
"""

import logging
import os
from typing import List
from langchain_core.embeddings import Embeddings
from config import EMBEDDING_MODEL

logger = logging.getLogger(__name__)

_embeddings_instance = None
_HF_MODEL_ID = f"sentence-transformers/{EMBEDDING_MODEL}"


class _InferenceClientEmbeddings(Embeddings):
    """Embeddings via huggingface_hub.InferenceClient (aucun modèle en RAM)."""

    def __init__(self, token: str, model: str):
        from huggingface_hub import InferenceClient
        self._client = InferenceClient(model=model, token=token)

    def _embed(self, text: str) -> List[float]:
        result = self._client.feature_extraction(text)
        if hasattr(result, "tolist"):
            vec = result.tolist()
        else:
            vec = list(result)
        # Aplatir si le modèle renvoie [[vec]] au lieu de [vec]
        if vec and isinstance(vec[0], list):
            vec = vec[0]
        return vec

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> List[float]:
        return self._embed(text)


def get_embeddings() -> Embeddings:
    """
    Retourne l'instance d'embeddings adaptée à l'environnement.
    HF_TOKEN présent → InferenceClient API (0 RAM). Absent → modèle local.
    """
    global _embeddings_instance

    if _embeddings_instance is None:
        hf_token = os.getenv("HF_TOKEN", "")

        if hf_token:
            logger.info("Embeddings via HuggingFace InferenceClient (production)")
            _embeddings_instance = _InferenceClientEmbeddings(
                token=hf_token,
                model=_HF_MODEL_ID,
            )
        else:
            logger.info(f"Embeddings locaux : {EMBEDDING_MODEL}")
            from langchain_huggingface import HuggingFaceEmbeddings
            _embeddings_instance = HuggingFaceEmbeddings(
                model_name=EMBEDDING_MODEL,
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True, "batch_size": 32},
            )
        logger.info("  Embeddings initialisés : OK")

    return _embeddings_instance


def embed_texts(texts: List[str]) -> List[List[float]]:
    """Utilitaire pour les tests."""
    return get_embeddings().embed_documents(texts)
