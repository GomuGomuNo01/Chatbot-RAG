"""
ingest.py — Script CLI d'indexation des documents
─────────────────────────────────────────────────
Usage :
  python ingest.py                          # Indexe tout (incrémental)
  python ingest.py --reset                  # Recrée l'index depuis zéro
  python ingest.py --categorie technique    # Une seule catégorie
  python ingest.py --file docs/rh/note.pdf  # Un seul fichier
"""

import argparse
import logging
import sys
from pathlib import Path

from config import get_all_categories

from src.indexer import (
    _file_hash,
    add_documents_to_index,
    create_index,
    filter_new_files,
    index_exists,
    load_manifest,
    save_manifest,
)
from src.loader import (
    SUPPORTED_EXTENSIONS,
    load_all_documents,
    load_category,
    load_file,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────


def _collect_files(categorie: str | None = None) -> list:
    """Collecte tous les fichiers supportés d'une ou plusieurs catégories (natives + custom)."""
    all_cats = get_all_categories()
    cat_keys = [categorie] if categorie else list(all_cats.keys())
    files = []
    for cat in cat_keys:
        directory = Path(all_cats[cat]["dir"])
        for ext in SUPPORTED_EXTENSIONS:
            files.extend(sorted(directory.glob(f"*{ext}")))
    return files


def _infer_categorie(file_path: Path) -> str:
    """Déduit la catégorie depuis le dossier parent du fichier (natives + custom)."""
    parent = file_path.parent.name
    all_cats = get_all_categories()
    if parent in all_cats:
        return parent
    logger.warning(f"Catégorie non reconnue pour '{parent}' — fallback sur 'technique'.")
    return "technique"


# ──────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Indexation des documents pour le chatbot RAG",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--categorie",
        choices=list(get_all_categories().keys()),
        default=None,
        metavar="CAT",
        help="Indexer seulement cette catégorie (technique | rh | juridique)",
    )
    parser.add_argument(
        "--file",
        type=str,
        default=None,
        metavar="CHEMIN",
        help=f"Indexer un seul fichier ({', '.join(SUPPORTED_EXTENSIONS)})",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Supprimer l'index existant et tout recréer depuis zéro",
    )
    args = parser.parse_args()

    logger.info("=" * 52)
    logger.info("  INDEXATION — Chatbot RAG")
    logger.info("=" * 52)

    documents = []

    # ── Mode : un seul fichier ──────────────────────────────
    if args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            logger.error(f"Fichier introuvable : {file_path}")
            sys.exit(1)
        if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            logger.error(
                f"Format non supporté : {file_path.suffix} "
                f"(acceptés : {', '.join(SUPPORTED_EXTENSIONS)})"
            )
            sys.exit(1)

        categorie = _infer_categorie(file_path)
        documents = load_file(file_path, categorie)

        if not documents:
            logger.warning(f"Aucun contenu extrait de {file_path.name}.")
            sys.exit(0)

        if not index_exists() or args.reset:
            create_index(documents)
            manifest = {str(file_path.resolve()): _file_hash(file_path)}
            save_manifest(manifest)
        else:
            manifest = load_manifest()
            manifest[str(file_path.resolve())] = _file_hash(file_path)
            add_documents_to_index(documents, manifest)

    # ── Mode : reconstruction complète ─────────────────────
    elif args.reset or not index_exists():
        if args.categorie:
            documents = load_category(args.categorie)
        else:
            documents = load_all_documents()

        if not documents:
            logger.error(
                "Aucun document trouvé. Ajoutez des fichiers dans "
                "docs/technique/, docs/rh/, docs/juridique/ puis relancez."
            )
            sys.exit(1)

        create_index(documents)

        # Construire le manifeste initial
        all_files = _collect_files(args.categorie)
        manifest = {str(f.resolve()): _file_hash(f) for f in all_files}
        save_manifest(manifest)

    # ── Mode : ré-indexation incrémentale (défaut) ─────────
    else:
        all_files = _collect_files(args.categorie)
        new_files, manifest = filter_new_files(all_files)

        if not new_files:
            logger.info("Tous les documents sont à jour. Rien à faire.")
            return

        logger.info(f"{len(new_files)} fichier(s) nouveau(x) ou modifié(s) détecté(s).")
        for file_path in new_files:
            cat = _infer_categorie(file_path)
            docs = load_file(file_path, cat)
            documents.extend(docs)

        if not documents:
            logger.warning("Aucun contenu extrait des nouveaux fichiers.")
            return

        add_documents_to_index(documents, manifest)

    logger.info("=" * 52)
    logger.info(f"  Indexation terminée ✓  ({len(documents)} chunks traités)")
    logger.info("=" * 52)


if __name__ == "__main__":
    main()
