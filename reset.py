"""
reset.py — Remise à zéro complète de DocAssist.

Supprime :
  - Les données générées localement (index FAISS, BM25, cache, workspaces)
  - Les documents et métadonnées sur Cloudflare R2
  - L'index FAISS sur HuggingFace Hub

Après exécution, le projet repart de zéro : aucun workspace, aucun document,
aucun index. Uploadez vos fichiers via l'interface web pour reconstruire.
"""

import logging
import shutil
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.resolve()


# ──────────────────────────────────────────────────────────────
# 1. Données locales
# ──────────────────────────────────────────────────────────────

def _reset_local() -> None:
    targets = [
        BASE_DIR / "data" / "faiss_index",
        BASE_DIR / "data" / "bm25_index.pkl",
        BASE_DIR / "data" / "response_cache.json",
        BASE_DIR / "data" / "daily_limits.json",
        BASE_DIR / "data" / "workspaces.json",
        BASE_DIR / "data" / "documents_meta.json",
        BASE_DIR / "docs",
    ]
    for t in targets:
        if t.exists():
            if t.is_dir():
                shutil.rmtree(t)
                logger.info(f"  [local] Dossier supprimé : {t.name}/")
            else:
                t.unlink()
                logger.info(f"  [local] Fichier supprimé : {t.name}")
        else:
            logger.info(f"  [local] Déjà absent : {t.name}")

    # Recréer les dossiers vides nécessaires au démarrage
    (BASE_DIR / "data").mkdir(parents=True, exist_ok=True)
    (BASE_DIR / "docs").mkdir(parents=True, exist_ok=True)
    logger.info("  [local] Dossiers data/ et docs/ recréés vides.")


# ──────────────────────────────────────────────────────────────
# 2. Cloudflare R2
# ──────────────────────────────────────────────────────────────

def _reset_r2() -> None:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=BASE_DIR / ".env", override=True)

    import os
    account_id  = os.getenv("R2_ACCOUNT_ID", "")
    access_key  = os.getenv("R2_ACCESS_KEY_ID", "")
    secret_key  = os.getenv("R2_SECRET_ACCESS_KEY", "")
    bucket_name = os.getenv("R2_BUCKET_NAME", "")

    if not all([account_id, access_key, secret_key, bucket_name]):
        logger.info("  [R2] Non configuré — ignoré.")
        return

    try:
        import boto3
        client = boto3.client(
            "s3",
            endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name="auto",
        )

        paginator = client.get_paginator("list_objects_v2")
        keys_to_delete = []
        for page in paginator.paginate(Bucket=bucket_name):
            for obj in page.get("Contents", []):
                keys_to_delete.append({"Key": obj["Key"]})

        if not keys_to_delete:
            logger.info("  [R2] Bucket déjà vide.")
            return

        # Suppression par batch de 1000 (limite AWS/R2)
        for i in range(0, len(keys_to_delete), 1000):
            batch = keys_to_delete[i:i + 1000]
            client.delete_objects(Bucket=bucket_name, Delete={"Objects": batch})

        logger.info(f"  [R2] {len(keys_to_delete)} objet(s) supprimé(s) dans '{bucket_name}'.")

    except Exception as e:
        logger.warning(f"  [R2] Erreur : {e}")


# ──────────────────────────────────────────────────────────────
# 3. HuggingFace Hub
# ──────────────────────────────────────────────────────────────

def _reset_hf() -> None:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=BASE_DIR / ".env", override=True)

    import os
    hf_token   = os.getenv("HF_TOKEN", "")
    hf_repo_id = os.getenv("HF_REPO_ID", "")

    if not hf_token or not hf_repo_id:
        logger.info("  [HF] Non configuré — ignoré.")
        return

    try:
        from huggingface_hub import HfApi
        api = HfApi(token=hf_token)

        # Lister tous les fichiers du dataset
        try:
            files = api.list_repo_files(repo_id=hf_repo_id, repo_type="dataset")
        except Exception:
            logger.info("  [HF] Dépôt vide ou inexistant — ignoré.")
            return

        deleted = 0
        for filepath in files:
            if filepath.startswith("."):
                continue  # garder .gitattributes etc.
            try:
                api.delete_file(
                    path_in_repo=filepath,
                    repo_id=hf_repo_id,
                    repo_type="dataset",
                    commit_message="reset: suppression index périmé",
                )
                logger.info(f"  [HF] Supprimé : {filepath}")
                deleted += 1
            except Exception as e:
                logger.warning(f"  [HF] Impossible de supprimer {filepath} : {e}")

        if deleted:
            logger.info(f"  [HF] {deleted} fichier(s) supprimé(s) dans '{hf_repo_id}'.")
        else:
            logger.info("  [HF] Rien à supprimer.")

    except Exception as e:
        logger.warning(f"  [HF] Erreur : {e}")


# ──────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print()
    print("=" * 55)
    print("  DocAssist — REMISE À ZÉRO COMPLÈTE")
    print("=" * 55)
    print()
    print("Cela va supprimer :")
    print("  • L'index FAISS et BM25 local")
    print("  • Le cache des réponses et les workspaces")
    print("  • Tous les documents dans Cloudflare R2")
    print("  • L'index FAISS sur HuggingFace Hub")
    print()
    confirm = input("Confirmer ? (oui / non) : ").strip().lower()
    if confirm not in ("oui", "o", "yes", "y"):
        print("Annulé.")
        sys.exit(0)

    print()
    logger.info("=== 1/3 Nettoyage local ===")
    _reset_local()

    logger.info("=== 2/3 Nettoyage Cloudflare R2 ===")
    _reset_r2()

    logger.info("=== 3/3 Nettoyage HuggingFace Hub ===")
    _reset_hf()

    print()
    logger.info("=" * 55)
    logger.info("  Remise à zéro terminée.")
    logger.info("  Relancez : python api/main.py")
    logger.info("  Puis uploadez vos fichiers via l'interface web.")
    logger.info("=" * 55)
