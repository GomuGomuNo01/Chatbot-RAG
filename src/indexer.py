"""
Indexer : création et gestion de l'index FAISS
Inclut un manifeste JSON pour la ré-indexation incrémentale.
"""

import hashlib
import json
import logging
from pathlib import Path
from typing import List

from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS

from src.embedder import get_embeddings
from config import FAISS_INDEX_DIR

logger = logging.getLogger(__name__)

INDEX_PATH    = Path(FAISS_INDEX_DIR)
MANIFEST_FILE = INDEX_PATH / "manifest.json"


# ============================================================
# MANIFESTE — suivi des fichiers déjà indexés
# ============================================================

def _file_hash(path: Path) -> str:
    """
    Empreinte rapide d'un fichier : taille + premiers 64 Ko.
    Suffit pour détecter ajouts et modifications sans tout lire.
    """
    h = hashlib.md5()
    h.update(str(path.stat().st_size).encode())
    with path.open("rb") as f:
        h.update(f.read(65_536))
    return h.hexdigest()


def load_manifest() -> dict:
    """Charge le manifeste {chemin_absolu: hash} depuis le disque."""
    if MANIFEST_FILE.exists():
        try:
            return json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.warning("Manifeste corrompu — reconstruction complète.")
    return {}


def save_manifest(manifest: dict) -> None:
    """Persiste le manifeste sur disque."""
    INDEX_PATH.mkdir(parents=True, exist_ok=True)
    MANIFEST_FILE.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def filter_new_files(file_paths: List[Path]) -> tuple:
    """
    Identifie les fichiers nouveaux ou modifiés depuis la dernière indexation.

    Returns:
        (fichiers_à_indexer, manifeste_mis_à_jour)
    """
    manifest     = load_manifest()
    new_manifest = dict(manifest)
    to_index     = []

    for path in file_paths:
        key = str(path.resolve())
        h   = _file_hash(path)
        if manifest.get(key) != h:
            to_index.append(path)
            new_manifest[key] = h

    skipped = len(file_paths) - len(to_index)
    if skipped:
        logger.info(f"  {skipped} fichier(s) inchangé(s) — ignoré(s) (cache OK)")

    return to_index, new_manifest


# ============================================================
# CRÉATION DE L'INDEX
# ============================================================

def create_index(documents: List[Document]) -> FAISS:
    """
    Crée un nouvel index FAISS depuis zéro et le sauvegarde sur disque.
    Le manifeste est géré séparément par l'appelant.
    """
    if not documents:
        raise ValueError("Impossible de créer un index : aucun document fourni.")

    logger.info(f"Création de l'index FAISS ({len(documents)} chunks)…")
    embeddings  = get_embeddings()
    vectorstore = FAISS.from_documents(documents=documents, embedding=embeddings)
    vectorstore.save_local(str(INDEX_PATH))
    logger.info(f"Index FAISS sauvegardé : {INDEX_PATH}")
    return vectorstore


# ============================================================
# CHARGEMENT DE L'INDEX
# ============================================================

def load_index() -> FAISS:
    """
    Charge l'index FAISS depuis le disque.

    Raises:
        FileNotFoundError : si l'index n'existe pas encore.
    """
    index_file = INDEX_PATH / "index.faiss"
    if not index_file.exists():
        raise FileNotFoundError(
            f"Index FAISS introuvable dans {INDEX_PATH}.\n"
            "Lance d'abord : python ingest.py"
        )
    logger.info(f"Chargement de l'index FAISS : {INDEX_PATH}")
    embeddings  = get_embeddings()
    vectorstore = FAISS.load_local(
        str(INDEX_PATH),
        embeddings,
        allow_dangerous_deserialization=True,
    )
    logger.info("Index FAISS chargé : OK")
    return vectorstore


# ============================================================
# MISE À JOUR INCRÉMENTALE
# ============================================================

def add_documents_to_index(
    new_documents: List[Document],
    new_manifest: dict | None = None,
) -> FAISS:
    """
    Ajoute des documents à l'index existant sans tout recalculer.
    Si new_manifest est fourni, le manifeste est mis à jour sur disque.
    """
    logger.info(f"Ajout de {len(new_documents)} chunk(s) à l'index existant…")
    vectorstore = load_index()
    vectorstore.add_documents(new_documents)
    vectorstore.save_local(str(INDEX_PATH))

    if new_manifest is not None:
        save_manifest(new_manifest)

    logger.info("Index mis à jour et sauvegardé : OK")
    return vectorstore


# ============================================================
# UTILITAIRES
# ============================================================

def index_exists() -> bool:
    """Vérifie si un index FAISS existe déjà sur disque."""
    return (INDEX_PATH / "index.faiss").exists()
