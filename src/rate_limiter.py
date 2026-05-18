"""
rate_limiter.py — Limiteur de requêtes journalier (économie de crédits API).

Stocke un compteur par jour dans data/daily_limits.json.
Configurable via les variables d'environnement :
  DAILY_REQUEST_LIMIT  : nombre max de requêtes LLM par jour (défaut: 0 = illimité)
  RATE_LIMIT_EXCLUDE_CACHE : si "true", les cache hits ne comptent pas (défaut: true)
"""

import json
import logging
import os
from datetime import date
from threading import Lock

from config import BASE_DIR

logger = logging.getLogger(__name__)

_LIMITS_FILE = BASE_DIR / "data" / "daily_limits.json"
_lock = Lock()

DAILY_REQUEST_LIMIT: int = int(os.getenv("DAILY_REQUEST_LIMIT", "0"))
EXCLUDE_CACHE_HITS: bool = os.getenv("RATE_LIMIT_EXCLUDE_CACHE", "true").lower() == "true"


def _load() -> dict:
    if _LIMITS_FILE.exists():
        try:
            return json.loads(_LIMITS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save(data: dict) -> None:
    _LIMITS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _LIMITS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_today_count() -> int:
    """Retourne le nombre de requêtes LLM effectuées aujourd'hui."""
    data = _load()
    today = str(date.today())
    return data.get(today, 0)


def get_limit() -> int:
    """Retourne la limite journalière configurée (0 = illimité)."""
    return DAILY_REQUEST_LIMIT


def check_limit() -> tuple[bool, int, int]:
    """
    Vérifie si la limite journalière est atteinte.
    Retourne (allowed, count, limit).
    Si limit == 0, toujours autorisé.
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
