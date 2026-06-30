"""Tracking de cuota diaria de Groq y preferencia de IA.

Extraído de bot.py sin cambios de comportamiento; las rutas de archivo ahora
vienen de core.config para funcionar desde cualquier directorio de trabajo.
"""

import json
import os
from datetime import datetime, timezone

from . import config


def _load_all_quota() -> dict:
    try:
        if os.path.exists(config.QUOTA_FILE) and os.path.getsize(config.QUOTA_FILE) > 0:
            with open(config.QUOTA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_all_quota(all_data: dict):
    with open(config.QUOTA_FILE, "w", encoding="utf-8") as f:
        json.dump(all_data, f)


def load_quota() -> dict:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    entry = _load_all_quota().get("groq", {})
    if entry.get("date") == today:
        return {"count": entry.get("count", 0), "tokens": entry.get("tokens", 0)}
    return {"count": 0, "tokens": 0}


def increment_quota(tokens: int = 0):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    all_data = _load_all_quota()
    entry = all_data.get("groq", {})
    if entry.get("date") != today:
        entry = {"date": today, "count": 0, "tokens": 0}
    entry["count"] += 1
    entry["tokens"] += tokens
    all_data["groq"] = entry
    _save_all_quota(all_data)


def get_preferred_ia() -> str:
    try:
        if os.path.exists(config.PREFERRED_IA_FILE):
            with open(config.PREFERRED_IA_FILE, "r") as f:
                return json.load(f).get("ia", "groq")
    except Exception:
        pass
    return "groq"


def set_preferred_ia(ia: str):
    with open(config.PREFERRED_IA_FILE, "w") as f:
        json.dump({"ia": ia}, f)
