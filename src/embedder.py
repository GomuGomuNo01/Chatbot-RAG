"""
Embedder : génération des embeddings.
- Production (HF_TOKEN défini) : HuggingFace Inference API — aucun modèle en RAM.
- Développement local (pas de HF_TOKEN) : sentence-transformers local (~400 MB RAM).
"""

import logging
import os
from typing import List
from config import EMBEDDING_MODEL

logger = logging.getLogger(__name__)

_embeddings_instance = None

# Nom complet pour l'API HF (prefix requis)
_HF_MODEL_ID = f"sentence-transformers/{EMBEDDING_MODEL}"


def get_embeddings():
    """
    Retourne l'instance d'embeddings adaptée à l'environnement.
    HF_TOKEN présent → API (0 RAM locale). Absent → modèle local.
    """
    global _embeddings_instance

    if _embeddings_instance is None:
        hf_token = os.getenv("HF_TOKEN", "")

        if hf_token:
            logger.info("Embeddings via HuggingFace Inference API (production)")
            from langchain_community.embeddings import HuggingFaceInferenceAPIEmbeddings
            _embeddings_instance = HuggingFaceInferenceAPIEmbeddings(
                api_key=hf_token,
                model_name=_HF_MODEL_ID,
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
    """
    Génère les embeddings pour une liste de textes.
    Utilitaire pour les tests unitaires.
    """
    model = get_embeddings()
    return model.embed_documents(texts)