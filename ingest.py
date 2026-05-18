"""
ingest.py — Script CLI d'indexation (refonte v2)

Usage :
  python ingest.py                         # Incrémental (nouveaux fichiers)
  python ingest.py --reset                 # Reconstruction complète
  python ingest.py --workspace marketing   # Un seul workspace
  python ingest.py --file docs/foo/note.pdf
"""

import argparse
import logging
import sys
from pathlib import Path

from config import auto_provision_workspaces_from_disk, get_workspaces

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
    load_file,
    load_workspace,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _collect_files(workspace: str | None = None) -> list[Path]:
    workspaces = get_workspaces()
    keys = [workspace] if workspace else list(workspaces.keys())
    files: list[Path] = []
    for key in keys:
        directory = Path(workspaces[key]["dir"])
        for ext in SUPPORTED_EXTENSIONS:
            files.extend(sorted(directory.glob(f"*{ext}")))
    return files


def _infer_workspace(file_path: Path) -> str:
    workspaces = get_workspaces()
    parent = file_path.parent.name
    if parent in workspaces:
        return parent
    logger.warning(f"Workspace inconnu pour « {parent} » — fallback sur le premier workspace.")
    if not workspaces:
        raise SystemExit(
            "Aucun workspace enregistré. Créez-en un via l'interface ou ajoutez un dossier "
            "dans docs/ puis relancez."
        )
    return next(iter(workspaces.keys()))


def main() -> None:
    auto_provision_workspaces_from_disk()

    workspaces = get_workspaces()
    workspace_keys = list(workspaces.keys())

    parser = argparse.ArgumentParser(
        description="Indexation des documents pour DocAssist",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--workspace",
        choices=workspace_keys or None,
        default=None,
        metavar="KEY",
        help=f"Indexer un seul workspace ({', '.join(workspace_keys) if workspace_keys else 'aucun'})",
    )
    parser.add_argument(
        "--file", type=str, default=None, metavar="CHEMIN", help="Indexer un seul fichier"
    )
    parser.add_argument("--reset", action="store_true", help="Reconstruction complète")
    args = parser.parse_args()

    logger.info("=" * 55)
    logger.info("  INDEXATION — DocAssist")
    logger.info("=" * 55)

    documents = []

    if args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            logger.error(f"Fichier introuvable : {file_path}")
            sys.exit(1)
        if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            logger.error(f"Format non supporté : {file_path.suffix}")
            sys.exit(1)

        ws = _infer_workspace(file_path)
        documents = load_file(file_path, ws)

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

    elif args.reset or not index_exists():
        if args.workspace:
            documents = load_workspace(args.workspace)
        else:
            documents = load_all_documents()

        if not documents:
            logger.error("Aucun document trouvé. Ajoutez des fichiers et relancez.")
            sys.exit(1)

        create_index(documents)
        all_files = _collect_files(args.workspace)
        manifest = {str(f.resolve()): _file_hash(f) for f in all_files}
        save_manifest(manifest)

    else:
        all_files = _collect_files(args.workspace)
        new_files, manifest = filter_new_files(all_files)

        if not new_files:
            logger.info("Tous les documents sont à jour.")
            return

        logger.info(f"{len(new_files)} fichier(s) nouveau(x) détecté(s).")
        for file_path in new_files:
            ws = _infer_workspace(file_path)
            documents.extend(load_file(file_path, ws))

        if not documents:
            logger.warning("Aucun contenu extrait des nouveaux fichiers.")
            return

        add_documents_to_index(documents, manifest)

    logger.info("=" * 55)
    logger.info(f"  Indexation terminée ✓  ({len(documents)} chunks)")
    logger.info("=" * 55)


if __name__ == "__main__":
    main()
