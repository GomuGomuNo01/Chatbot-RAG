"""
Embedder : génération des embeddings avec sentence-transformers (local)
Aucun appel API, aucun coût.
"""

import logging
from typing import List
from langchain_huggingface import HuggingFaceEmbeddings
from config import EMBEDDING_MODEL

logger = logging.getLogger(__name__)

# Instance globale — chargée une seule fois en mémoire
_embeddings_instance = None


def get_embeddings() -> HuggingFaceEmbeddings:
    """
    Retourne l'instance du modèle d'embeddings.
    Télécharge le modèle automatiquement au premier appel (~120 MB).
    Les appels suivants réutilisent l'instance en mémoire.
    """
    global _embeddings_instance

    if _embeddings_instance is None:
        logger.info(
            f"Chargement du modèle d'embeddings : {EMBEDDING_MODEL}"
        )
        logger.info(
            "  (premier lancement : téléchargement ~120 MB)"
        )

        _embeddings_instance = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL,
            model_kwargs={"device": "cpu"},
            encode_kwargs={
                "normalize_embeddings": True,
                "batch_size": 32
            }
        )
        logger.info("  Modèle d'embeddings chargé : OK")

    return _embeddings_instance


def embed_texts(texts: List[str]) -> List[List[float]]:
    """
    Génère les embeddings pour une liste de textes.
    Utilitaire pour les tests unitaires.
    """
    model = get_embeddings()
    return model.embed_documents(texts)