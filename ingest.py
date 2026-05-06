"""
ingest.py — Script d'indexation des PDFs
Usage : python ingest.py
        python ingest.py --categorie technique
        python ingest.py --reset
"""

import argparse
import logging
import sys
from src.loader  import load_all_documents, load_category
from src.indexer import (
    create_index,
    add_documents_to_index,
    index_exists
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Indexation des PDFs pour le chatbot RAG"
    )
    parser.add_argument(
        "--categorie",
        type=str,
        choices=["technique", "rh", "juridique"],
        default=None,
        help="Indexer une seule catégorie (défaut : toutes)"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Recrée l'index depuis zéro"
    )
    args = parser.parse_args()

    logger.info("=" * 50)
    logger.info("  INDEXATION DES DOCUMENTS")
    logger.info("=" * 50)

    # Chargement des documents
    if args.categorie:
        documents = load_category(args.categorie)
    else:
        documents = load_all_documents()

    if not documents:
        logger.error(
            "Aucun document trouvé. "
            "Ajoutez des PDFs dans docs/technique/, "
            "docs/rh/, docs/juridique/"
        )
        sys.exit(1)

    # Création ou mise à jour de l'index
    if not index_exists() or args.reset:
        logger.info("Création d'un nouvel index FAISS...")
        create_index(documents)
    else:
        logger.info("Mise à jour de l'index existant...")
        add_documents_to_index(documents)

    logger.info("=" * 50)
    logger.info(
        f"  Indexation terminée : {len(documents)} chunks"
    )
    logger.info("=" * 50)


if __name__ == "__main__":
    main()