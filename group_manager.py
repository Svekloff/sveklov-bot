"""Manages active groups the bot is added to."""
import json
import logging
import os
from datetime import datetime, timezone

from config import GROUPS_FILE

logger = logging.getLogger(__name__)


def _load() -> dict:
    """Load groups from JSON file."""
    if not os.path.exists(GROUPS_FILE):
        return {}
    try:
        with open(GROUPS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.error("Failed to load groups file: %s", e)
        return {}


def _save(data: dict) -> None:
    """Save groups to JSON file."""
    try:
        with open(GROUPS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError as e:
        logger.error("Failed to save groups file: %s", e)


def add_group(group_id: int, title: str) -> None:
    """Register a group."""
    data = _load()
    data[str(group_id)] = {
        "title": title,
        "added_at": datetime.now(timezone.utc).isoformat(),
    }
    _save(data)


def remove_group(group_id: int) -> bool:
    """Unregister a group. Returns True if it existed."""
    data = _load()
    key = str(group_id)
    if key in data:
        del data[key]
        _save(data)
        return True
    return False


def list_groups() -> dict:
    """Return all registered groups as {group_id_str: info_dict}."""
    return _load()
