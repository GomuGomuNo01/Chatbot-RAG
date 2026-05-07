"""
storage.py — Client Cloudflare R2 (compatible S3)

Stocke les fichiers sources (PDF, DOCX, TXT) dans R2 de façon permanente.
Clé de stockage : docs/{categorie}/{nom_fichier}

Mode dégradé : si R2 n'est pas configuré (variables absentes),
toutes les fonctions retournent des valeurs neutres sans lever d'exception.
Le système continue de fonctionner en mode filesystem local.
"""

import logging
from functools import lru_cache
from typing import List, Optional

from config import (
    R2_ACCOUNT_ID,
    R2_ACCESS_KEY_ID,
    R2_SECRET_ACCESS_KEY,
    R2_BUCKET_NAME,
    is_r2_enabled,
)

logger = logging.getLogger(__name__)

_R2_PREFIX = "docs"


@lru_cache(maxsize=1)
def _get_client():
    """Singleton boto3 vers Cloudflare R2."""
    import boto3
    return boto3.client(
        "s3",
        endpoint_url=f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )


def _object_key(categorie: str, filename: str) -> str:
    return f"{_R2_PREFIX}/{categorie}/{filename}"


# ──────────────────────────────────────────────────────────────
# API publique
# ──────────────────────────────────────────────────────────────

def file_exists_r2(categorie: str, filename: str) -> bool:
    """Vérifie si un fichier est présent dans R2."""
    if not is_r2_enabled():
        return False
    try:
        from botocore.exceptions import ClientError
        _get_client().head_object(
            Bucket=R2_BUCKET_NAME,
            Key=_object_key(categorie, filename),
        )
        return True
    except Exception as e:
        from botocore.exceptions import ClientError
        if isinstance(e, ClientError) and e.response["Error"]["Code"] in ("404", "NoSuchKey"):
            return False
        logger.warning(f"R2 head_object erreur : {e}")
        return False


def upload_file_r2(content: bytes, categorie: str, filename: str) -> None:
    """Upload un fichier dans R2. Silencieux si R2 non configuré."""
    if not is_r2_enabled():
        return
    key = _object_key(categorie, filename)
    _get_client().put_object(Bucket=R2_BUCKET_NAME, Key=key, Body=content)
    logger.info(f"R2 ← upload : {key}")


def download_file_r2(categorie: str, filename: str) -> bytes:
    """Télécharge un fichier depuis R2."""
    key = _object_key(categorie, filename)
    response = _get_client().get_object(Bucket=R2_BUCKET_NAME, Key=key)
    return response["Body"].read()


def list_files_r2(categorie: Optional[str] = None) -> List[dict]:
    """
    Liste les fichiers stockés dans R2.

    Retourne une liste de dicts ``{categorie, filename}`` pour chaque objet
    sous la clé ``docs/{categorie}/{filename}``.
    Retourne [] si R2 n'est pas configuré.
    """
    if not is_r2_enabled():
        return []
    try:
        prefix = (
            f"{_R2_PREFIX}/{categorie}/"
            if categorie
            else f"{_R2_PREFIX}/"
        )
        paginator = _get_client().get_paginator("list_objects_v2")
        results: List[dict] = []
        for page in paginator.paginate(Bucket=R2_BUCKET_NAME, Prefix=prefix):
            for obj in page.get("Contents", []):
                parts = obj["Key"].split("/")
                if len(parts) == 3:  # docs / {cat} / {filename}
                    results.append({"categorie": parts[1], "filename": parts[2]})
        logger.debug(f"R2 list ({prefix}) → {len(results)} fichier(s)")
        return results
    except Exception as e:
        logger.warning(f"R2 list_objects erreur : {e}")
        return []


def sync_r2_to_local(docs_dir) -> int:
    """
    Télécharge depuis R2 tous les fichiers absents du dossier docs/ local.
    Utile avant une ré-indexation complète sur Render (filesystem éphémère).

    Args:
        docs_dir : Path vers le répertoire docs/ racine

    Returns:
        Nombre de fichiers téléchargés.
    """
    if not is_r2_enabled():
        return 0

    from pathlib import Path
    docs_dir = Path(docs_dir)
    downloaded = 0

    for item in list_files_r2():
        cat      = item["categorie"]
        filename = item["filename"]
        dest     = docs_dir / cat / filename
        if not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                dest.write_bytes(download_file_r2(cat, filename))
                downloaded += 1
                logger.info(f"R2 → local : {cat}/{filename}")
            except Exception as e:
                logger.warning(f"R2 download {cat}/{filename} erreur : {e}")

    return downloaded
