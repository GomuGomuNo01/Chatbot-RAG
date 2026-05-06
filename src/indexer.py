"""
Indexer : création et gestion de l'index FAISS
"""

import logging
from pathlib import Path
from typing import List
from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS
from src.embedder import get_embeddings
from config import FAISS_INDEX_DIR

logger = logging.getLogger(__name__)

INDEX_PATH = Path(FAISS_INDEX_DIR)


def create_index(documents: List[Document]) -> FAISS:
    """
    Crée un nouvel index FAISS depuis une liste de Documents.
    L'index est sauvegardé sur disque automatiquement.

    Args:
        documents : liste de Documents LangChain avec métadonnées

    Returns:
        Instance FAISS prête pour la recherche
    """
    if not documents:
        raise ValueError(
            "Impossible de créer un index : aucun document fourni."
        )

    logger.info(
        f"Création de l'index FAISS "
        f"({len(documents)} chunks)..."
    )

    embeddings = get_embeddings()

    vectorstore = FAISS.from_documents(
        documents=documents,
        embedding=embeddings
    )

    # Sauvegarde sur disque
    vectorstore.save_local(str(INDEX_PATH))
    logger.info(f"Index FAISS sauvegardé : {INDEX_PATH}")

    return vectorstore


def load_index() -> FAISS:
    """
    Charge l'index FAISS depuis le disque.

    Raises:
        FileNotFoundError : si l'index n'existe pas encore
                            (lancer ingest.py d'abord)
    """
    index_file = INDEX_PATH / "index.faiss"

    if not index_file.exists():
        raise FileNotFoundError(
            f"Index FAISS introuvable dans {INDEX_PATH}.\n"
            f"Lance d'abord : python ingest.py"
        )

    logger.info(f"Chargement de l'index FAISS : {INDEX_PATH}")
    embeddings   = get_embeddings()
    vectorstore  = FAISS.load_local(
        str(INDEX_PATH),
        embeddings,
        allow_dangerous_deserialization=True
    )
    logger.info("Index FAISS chargé : OK")
    return vectorstore


def add_documents_to_index(
    new_documents: List[Document]
) -> FAISS:
    """
    Ajoute des documents à un index existant
    sans tout recalculer (ré-indexation incrémentale).
    """
    logger.info(
        f"Ajout de {len(new_documents)} chunks "
        f"à l'index existant..."
    )

    vectorstore = load_index()
    vectorstore.add_documents(new_documents)
    vectorstore.save_local(str(INDEX_PATH))

    logger.info("Index mis à jour et sauvegardé : OK")
    return vectorstore


def index_exists() -> bool:
    """Vérifie si un index FAISS existe déjà sur disque."""
    return (INDEX_PATH / "index.faiss").exists()