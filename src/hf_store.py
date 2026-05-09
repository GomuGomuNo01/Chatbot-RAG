"""
hf_store.py — Synchronisation de l'index FAISS avec HuggingFace Hub

L'index FAISS est sauvegardé dans un dépôt de type "dataset" privé sur HF Hub.
Cela garantit sa persistance entre les redémarrages de l'instance Render.

Fichiers synchronisés :
  faiss_index/index.faiss   — vecteurs FAISS
  faiss_index/index.pkl     — métadonnées des chunks
  faiss_index/manifest.json — suivi des fichiers indexés

Mode dégradé : si HF_TOKEN ou HF_REPO_ID sont absents, les fonctions
retournent immédiatement sans lever d'exception.
"""

import logging
from pathlib import Path

from config import FAISS_INDEX_DIR, HF_REPO_ID, HF_TOKEN, is_hf_enabled

logger = logging.getLogger(__name__)

_INDEX_PATH = Path(FAISS_INDEX_DIR)
_INDEX_FILES = ["index.faiss", "index.pkl", "manifest.json"]
_HF_SUBDIR = "faiss_index"


# ──────────────────────────────────────────────────────────────
# Push → Hub
# ──────────────────────────────────────────────────────────────


def push_index_to_hub() -> None:
    """
    Upload tous les fichiers de l'index FAISS vers HuggingFace Hub.
    Appelé automatiquement après chaque indexation réussie.
    """
    if not is_hf_enabled():
        logger.debug("HF Hub désactivé (HF_TOKEN ou HF_REPO_ID absent) — push ignoré.")
        return

    try:
        from huggingface_hub import HfApi

        api = HfApi(token=HF_TOKEN)

        # S'assurer que le dépôt existe (le crée si nécessaire)
        try:
            api.repo_info(repo_id=HF_REPO_ID, repo_type="dataset")
        except Exception:
            api.create_repo(
                repo_id=HF_REPO_ID,
                repo_type="dataset",
                private=True,
                exist_ok=True,
            )
            logger.info(f"HF Hub : dépôt créé → {HF_REPO_ID}")

        uploaded = 0
        for fname in _INDEX_FILES:
            fpath = _INDEX_PATH / fname
            if not fpath.exists():
                continue
            api.upload_file(
                path_or_fileobj=str(fpath),
                path_in_repo=f"{_HF_SUBDIR}/{fname}",
                repo_id=HF_REPO_ID,
                repo_type="dataset",
                commit_message=f"update {fname}",
            )
            uploaded += 1
            logger.info(f"HF Hub ← push : {fname}")

        if uploaded:
            logger.info(f"HF Hub : {uploaded} fichier(s) pushé(s) → {HF_REPO_ID}")

    except Exception as e:
        logger.warning(f"HF Hub push erreur (non bloquant) : {e}")


# ──────────────────────────────────────────────────────────────
# Pull ← Hub
# ──────────────────────────────────────────────────────────────


def pull_index_from_hub() -> bool:
    """
    Télécharge l'index FAISS depuis HuggingFace Hub vers le dossier local.
    Appelé au démarrage de l'app si l'index local est absent.

    Returns:
        True si index.faiss a été récupéré avec succès, False sinon.
    """
    if not is_hf_enabled():
        logger.debug("HF Hub désactivé — pull ignoré.")
        return False

    try:
        from huggingface_hub import hf_hub_download
        from huggingface_hub.utils import EntryNotFoundError, RepositoryNotFoundError

        _INDEX_PATH.mkdir(parents=True, exist_ok=True)
        pulled = False

        for fname in _INDEX_FILES:
            try:
                # hf_hub_download retourne le chemin local du fichier téléchargé
                downloaded_path = hf_hub_download(
                    repo_id=HF_REPO_ID,
                    filename=f"{_HF_SUBDIR}/{fname}",
                    repo_type="dataset",
                    token=HF_TOKEN,
                    local_files_only=False,
                )
                dest = _INDEX_PATH / fname
                # Copier vers notre dossier cible si besoin
                src = Path(downloaded_path)
                if src.resolve() != dest.resolve():
                    dest.write_bytes(src.read_bytes())

                if fname == "index.faiss":
                    pulled = True
                logger.info(f"HF Hub → pull : {fname}")

            except EntryNotFoundError:
                logger.debug(
                    f"HF Hub : {fname} absent dans le dépôt (normal au premier démarrage)."
                )
            except RepositoryNotFoundError:
                logger.warning(f"HF Hub : dépôt {HF_REPO_ID} introuvable.")
                return False
            except Exception as e:
                logger.warning(f"HF Hub pull {fname} erreur : {e}")

        if pulled:
            logger.info(f"HF Hub : index FAISS récupéré depuis {HF_REPO_ID}")
        return pulled

    except ImportError:
        logger.warning("huggingface_hub non installé — pip install huggingface_hub")
        return False
    except Exception as e:
        logger.warning(f"HF Hub pull erreur globale (non bloquant) : {e}")
        return False
