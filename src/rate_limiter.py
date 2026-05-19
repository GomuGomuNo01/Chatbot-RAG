"""
rate_limiter.py — Limiteur de requêtes journalier (économie de crédits API).

Stocke un compteur par jour dans data/daily_limits.json.
Persisté sur Cloudflare R2 pour survivre aux redémarrages du Space.

Variables d'environnement :
  DAILY_REQUEST_LIMIT      : nombre max de requêtes LLM par jour (défaut: 0 = illimité)
  RATE_LIMIT_EXCLUDE_CACHE : si "true", les cache hits ne comptent pas (défaut: true)
"""

import json
import logging
import os
import threading
from datetime import date
from threading import Lock

from config import BASE_DIR, is_r2_enabled

logger = logging.getLogger(__name__)

_LIMITS_FILE = BASE_DIR / "data" / "daily_limits.json"
_R2_KEY = "config/daily_limits.json"
_lock = Lock()

DAILY_REQUEST_LIMIT: int = int(os.getenv("DAILY_REQUEST_LIMIT", "0"))
EXCLUDE_CACHE_HITS: bool = os.getenv("RATE_LIMIT_EXCLUDE_CACHE", "true").lower() == "true"


# ============================================================
# Persistance R2 (non bloquante)
# ============================================================


def _pull_from_r2() -> bool:
    """Télécharge daily_limits.json depuis R2 si disponible. Retourne True si succès."""
    if not is_r2_enabled():
        return False
    try:
        from src.storage import download_metadata_r2

        return download_metadata_r2(_R2_KEY, _LIMITS_FILE)
    except Exception as e:
        logger.debug(f"[rate_limit] R2 pull ignoré : {e}")
        return False


def _push_to_r2_daemon(data: dict) -> None:
    """Pousse daily_limits.json vers R2 dans un thread daemon (non bloquant)."""
    if not is_r2_enabled():
        return

    def _do() -> None:
        try:
            from src.storage import upload_metadata_r2

            upload_metadata_r2(_LIMITS_FILE, _R2_KEY)
        except Exception as e:
            logger.debug(f"[rate_limit] R2 push ignoré : {e}")

    threading.Thread(target=_do, daemon=True).start()


# ============================================================
# Lecture / écriture locale
# ============================================================


def _load() -> dict:
    """Charge le fichier local. Si absent, tente un pull R2 d'abord."""
    if not _LIMITS_FILE.exists():
        _pull_from_r2()
    if _LIMITS_FILE.exists():
        try:
            return json.loads(_LIMITS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save(data: dict) -> None:
    """Sauvegarde localement puis pousse sur R2 en arrière-plan."""
    _LIMITS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _LIMITS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    _push_to_r2_daemon(data)


# ============================================================
# API publique
# ============================================================


def restore_from_r2() -> None:
    """À appeler au démarrage pour restaurer le compteur depuis R2."""
    if _pull_from_r2():
        logger.info("[rate_limit] Compteur journalier restauré depuis R2")
    else:
        logger.debug("[rate_limit] Pas de compteur R2 à restaurer (nouveau jour ou R2 absent)")


def get_today_count() -> int:
    """Retourne le nombre de requêtes LLM effectuées aujourd'hui."""
    data = _load()
    return data.get(str(date.today()), 0)


def get_limit() -> int:
    """Retourne la limite journalière configurée (0 = illimité)."""
    return DAILY_REQUEST_LIMIT


def check_limit() -> tuple[bool, int, int]:
    """
    Vérifie si la limite journalière est atteinte.
    Retourne (allowed, count, limit). Si limit == 0, toujours autorisé.
    """
    limit = DAILY_REQUEST_LIMIT
    if limit <= 0:
        return True, get_today_count(), 0
    count = get_today_count()
    return count < limit, count, limit


def increment() -> int:
    """Incrémente le compteur du jour. Retourne le nouveau total."""
    with _lock:
        data = _load()
        today = str(date.today())
        data[today] = data.get(today, 0) + 1
        # Nettoyer les entrées de plus de 7 jours
        from datetime import timedelta

        cutoff = str(date.today() - timedelta(days=7))
        data = {k: v for k, v in data.items() if k >= cutoff}
        _save(data)
        count = data[today]
    logger.info(f"[rate_limit] Requêtes aujourd'hui : {count}/{DAILY_REQUEST_LIMIT or '∞'}")
    return count


def status() -> dict:
    """Retourne un dict de statut lisible (pour l'API health ou debug)."""
    limit = DAILY_REQUEST_LIMIT
    count = get_today_count()
    return {
        "enabled": limit > 0,
        "limit": limit,
        "used_today": count,
        "remaining": max(0, limit - count) if limit > 0 else None,
        "date": str(date.today()),
    }
