"""
indexer.py — Création et gestion de l'index FAISS + index BM25 jumeaux.

Refonte v2 : à chaque (re)construction de l'index FAISS, l'index BM25
est aussi reconstruit pour rester en synchronisation. La métadonnée des
chunks utilise désormais la clé `workspace` (au lieu de `categorie`).
"""

import hashlib
import json
import logging
from pathlib import Path

from config import FAISS_INDEX_DIR, get_chunk_config_fingerprint
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

from src.bm25_store import rebuild_bm25, reset_bm25_index
from src.embedder import get_embeddings

logger = logging.getLogger(__name__)

INDEX_PATH = Path(FAISS_INDEX_DIR)
MANIFEST_FILE = INDEX_PATH / "manifest.json"
CHUNK_CONFIG_FILE = INDEX_PATH / "chunk_config.json"


# ============================================================
# MANIFESTE
# ============================================================


def _file_hash(path: Path) -> str:
    h = hashlib.md5()
    h.update(str(path.stat().st_size).encode())
    with path.open("rb") as f:
        h.update(f.read(65_536))
    return h.hexdigest()


def load_manifest() -> dict:
    if MANIFEST_FILE.exists():
        try:
            return json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.warning("Manifeste corrompu — sera reconstruit.")
    return {}


def save_manifest(manifest: dict) -> None:
    INDEX_PATH.mkdir(parents=True, exist_ok=True)
    MANIFEST_FILE.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def filter_new_files(file_paths: list[Path]) -> tuple:
    manifest = load_manifest()
    new_manifest = dict(manifest)
    to_index: list[Path] = []
    for path in file_paths:
        key = str(path.resolve())
        h = _file_hash(path)
        if manifest.get(key) != h:
            to_index.append(path)
            new_manifest[key] = h
    skipped = len(file_paths) - len(to_index)
    if skipped:
        logger.info(f"  {skipped} fichier(s) inchangé(s) — ignoré(s) (cache OK)")
    return to_index, new_manifest


# ============================================================
# EMPREINTE DE CONFIGURATION
# ============================================================


def save_chunk_config() -> None:
    INDEX_PATH.mkdir(parents=True, exist_ok=True)
    fingerprint = get_chunk_config_fingerprint()
    CHUNK_CONFIG_FILE.write_text(
        json.dumps({"fingerprint": fingerprint}, indent=2), encoding="utf-8"
    )
    logger.info(f"Config chunking sauvegardée (empreinte : {fingerprint[:8]}…)")


def is_chunk_config_stale() -> bool:
    if not CHUNK_CONFIG_FILE.exists():
        return False
    try:
        stored = json.loads(CHUNK_CONFIG_FILE.read_text(encoding="utf-8"))
        if stored.get("fingerprint", "") != get_chunk_config_fingerprint():
            logger.warning("Configuration de chunking modifiée — ré-indexation nécessaire.")
            return True
    except Exception as e:
        logger.warning(f"chunk_config lecture échouée : {e}")
    return False


# ============================================================
# CRÉATION / CHARGEMENT INDEX FAISS
# ============================================================


def create_index(documents: list[Document]) -> FAISS:
    """Crée un index FAISS + BM25 jumelés, persiste les deux, pousse sur HF Hub."""
    if not documents:
        raise ValueError("Impossible de créer un index : aucun document fourni.")

    logger.info(f"Création de l'index FAISS ({len(documents)} chunks)…")

    try:
        embeddings = get_embeddings()
        vectorstore = FAISS.from_documents(documents=documents, embedding=embeddings)
    except Exception as e:
        raise RuntimeError(f"Échec embeddings/FAISS ({len(documents)} chunks) : {e}") from e

    try:
        INDEX_PATH.mkdir(parents=True, exist_ok=True)
        vectorstore.save_local(str(INDEX_PATH))
        logger.info(f"Index FAISS sauvegardé : {INDEX_PATH}")
    except Exception as e:
        raise RuntimeError(f"Sauvegarde FAISS impossible dans {INDEX_PATH} : {e}") from e

    save_chunk_config()

    # Index BM25 jumeau
    try:
        rebuild_bm25(documents)
    except Exception as e:
        logger.warning(f"Construction BM25 ignorée (non bloquant) : {e}", exc_info=True)

    return vectorstore


def load_index() -> FAISS:
    """Charge FAISS depuis disque, tente un pull HF Hub si absent."""
    index_file = INDEX_PATH / "index.faiss"
    if not index_file.exists():
        logger.info("Index FAISS absent localement — tentative HF Hub…")
        try:
            from src.hf_store import pull_index_from_hub

            pull_index_from_hub()
        except Exception as e:
            logger.warning(f"HF Hub pull ignoré : {e}")

    if not index_file.exists():
        raise FileNotFoundError(
            f"Index FAISS introuvable dans {INDEX_PATH}. "
            "Uploadez des documents via l'interface ou lancez : python ingest.py"
        )

    logger.info(f"Chargement de l'index FAISS : {INDEX_PATH}")
    try:
        embeddings = get_embeddings()
        vs = FAISS.load_local(str(INDEX_PATH), embeddings, allow_dangerous_deserialization=True)
    except Exception as e:
        raise RuntimeError(
            f"Chargement FAISS impossible depuis {INDEX_PATH} : {e}. "
            "L'index est peut-être corrompu — relancez une ré-indexation complète."
        ) from e
    logger.info("Index FAISS chargé.")
    return vs


def add_documents_to_index(
    new_documents: list[Document],
    new_manifest: dict | None = None,
) -> FAISS:
    """Ajout incrémental à FAISS + reconstruction BM25 sur l'union des chunks."""
    logger.info(f"Ajout de {len(new_documents)} chunk(s) à l'index existant…")
    vs = load_index()
    try:
        vs.add_documents(new_documents)
    except Exception as e:
        raise RuntimeError(f"Ajout FAISS impossible : {e}") from e

    try:
        vs.save_local(str(INDEX_PATH))
    except Exception as e:
        raise RuntimeError(f"Sauvegarde FAISS impossible : {e}") from e

    if new_manifest is not None:
        save_manifest(new_manifest)

    # BM25 doit refléter l'ensemble final : on rebuild depuis tous les chunks de FAISS.
    try:
        all_docs = list(vs.docstore._dict.values())
        rebuild_bm25(all_docs)
    except Exception as e:
        logger.warning(f"Reconstruction BM25 ignorée : {e}", exc_info=True)

    logger.info("Index FAISS + BM25 mis à jour.")
    return vs


def index_exists() -> bool:
    return (INDEX_PATH / "index.faiss").exists()


def reset_indexes() -> None:
    """Invalidation des deux singletons (FAISS + BM25)."""
    from src.retriever import reset_vectorstore

    reset_vectorstore()
    reset_bm25_index()
