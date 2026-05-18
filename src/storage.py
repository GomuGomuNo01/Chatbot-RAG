"""
storage.py — Client Cloudflare R2 (compatible S3).

Refonte v2 : les fichiers sont stockés sous `docs/{workspace}/{filename}` dans R2.
Le terme `categorie` est remplacé par `workspace` dans toute l'API.
"""

import logging
from functools import lru_cache

from config import (
    R2_ACCESS_KEY_ID,
    R2_ACCOUNT_ID,
    R2_BUCKET_NAME,
    R2_SECRET_ACCESS_KEY,
    is_r2_enabled,
)

logger = logging.getLogger(__name__)

_R2_PREFIX = "docs"


@lru_cache(maxsize=1)
def _get_client():
    import boto3

    return boto3.client(
        "s3",
        endpoint_url=f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )


def _object_key(workspace: str, filename: str) -> str:
    return f"{_R2_PREFIX}/{workspace}/{filename}"


def file_exists_r2(workspace: str, filename: str) -> bool:
    if not is_r2_enabled():
        return False
    try:
        from botocore.exceptions import ClientError

        _get_client().head_object(Bucket=R2_BUCKET_NAME, Key=_object_key(workspace, filename))
        return True
    except Exception as e:
        from botocore.exceptions import ClientError

        if isinstance(e, ClientError) and e.response["Error"]["Code"] in ("404", "NoSuchKey"):
            return False
        logger.warning(f"R2 head_object erreur : {e}")
        return False


def upload_file_r2(content: bytes, workspace: str, filename: str) -> None:
    if not is_r2_enabled():
        return
    key = _object_key(workspace, filename)
    _get_client().put_object(Bucket=R2_BUCKET_NAME, Key=key, Body=content)
    logger.info(f"R2 ← upload : {key}")


def download_file_r2(workspace: str, filename: str) -> bytes:
    key = _object_key(workspace, filename)
    response = _get_client().get_object(Bucket=R2_BUCKET_NAME, Key=key)
    return response["Body"].read()


def list_files_r2(workspace: str | None = None) -> list[dict]:
    """
    Liste les fichiers stockés dans R2.
    Retourne [{'workspace': str, 'filename': str}, …].
    """
    if not is_r2_enabled():
        return []
    try:
        prefix = f"{_R2_PREFIX}/{workspace}/" if workspace else f"{_R2_PREFIX}/"
        paginator = _get_client().get_paginator("list_objects_v2")
        results: list[dict] = []
        for page in paginator.paginate(Bucket=R2_BUCKET_NAME, Prefix=prefix):
            for obj in page.get("Contents", []):
                parts = obj["Key"].split("/")
                if len(parts) == 3:  # docs / {ws} / {filename}
                    results.append({"workspace": parts[1], "filename": parts[2]})
        return results
    except Exception as e:
        logger.warning(f"R2 list_objects erreur : {e}")
        return []


def delete_file_r2(workspace: str, filename: str) -> None:
    if not is_r2_enabled():
        return
    key = _object_key(workspace, filename)
    try:
        _get_client().delete_object(Bucket=R2_BUCKET_NAME, Key=key)
        logger.info(f"R2 ✗ supprimé : {key}")
    except Exception as e:
        logger.warning(f"R2 delete {key} erreur : {e}")


def delete_prefix_r2(workspace: str) -> int:
    """Supprime tous les fichiers d'un workspace dans R2."""
    if not is_r2_enabled():
        return 0
    deleted = 0
    for item in list_files_r2(workspace=workspace):
        delete_file_r2(item["workspace"], item["filename"])
        deleted += 1
    return deleted


def upload_metadata_r2(file_path, name: str) -> None:
    """Upload un fichier de config (ex. workspaces.json) sous config/{name} dans R2."""
    if not is_r2_enabled():
        return
    from pathlib import Path as _Path

    content = _Path(file_path).read_bytes()
    key = f"config/{name}"
    _get_client().put_object(Bucket=R2_BUCKET_NAME, Key=key, Body=content)
    logger.info(f"R2 ← metadata upload : {key}")


def download_metadata_r2(name: str, dest_path) -> bool:
    """Download config/{name} depuis R2 → dest_path local."""
    if not is_r2_enabled():
        return False
    from pathlib import Path as _Path

    key = f"config/{name}"
    try:
        from botocore.exceptions import ClientError

        response = _get_client().get_object(Bucket=R2_BUCKET_NAME, Key=key)
        dest = _Path(dest_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(response["Body"].read())
        logger.info(f"R2 → metadata download : {key}")
        return True
    except Exception as e:
        from botocore.exceptions import ClientError

        if isinstance(e, ClientError) and e.response["Error"]["Code"] in ("404", "NoSuchKey"):
            return False
        logger.warning(f"R2 metadata download {key} erreur : {e}")
        return False


def sync_r2_to_local(docs_dir) -> int:
    """Télécharge depuis R2 tous les fichiers absents du dossier docs/ local."""
    if not is_r2_enabled():
        return 0
    from pathlib import Path

    docs_dir = Path(docs_dir)
    downloaded = 0
    for item in list_files_r2():
        ws = item["workspace"]
        filename = item["filename"]
        dest = docs_dir / ws / filename
        if not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                dest.write_bytes(download_file_r2(ws, filename))
                downloaded += 1
                logger.info(f"R2 → local : {ws}/{filename}")
            except Exception as e:
                logger.warning(f"R2 download {ws}/{filename} erreur : {e}")
    return downloaded
