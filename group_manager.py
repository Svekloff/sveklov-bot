"""
Менеджер групп: хранит список известных групп и белый список в JSON-файле.
"""
import json
import logging
import os

logger = logging.getLogger(__name__)

DATA_DIR = os.getenv("DATA_DIR", "/data")
GROUPS_FILE = os.path.join(DATA_DIR, "groups.json")


def _ensure_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def _load() -> dict:
    try:
        with open(GROUPS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"known_groups": {}, "allowed_ids": []}


def _save(data: dict) -> None:
    _ensure_dir()
    with open(GROUPS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def register_group(chat_id: int, title: str) -> None:
    data = _load()
    known = data.get("known_groups", {})
    str_id = str(chat_id)
    if str_id not in known or known[str_id] != title:
        known[str_id] = title
        data["known_groups"] = known
        _save(data)
        logger.info(f"[группы] зарегистрирована: {chat_id} — {title}")


def unregister_group(chat_id: int) -> None:
    data = _load()
    str_id = str(chat_id)
    known = data.get("known_groups", {})
    allowed = data.get("allowed_ids", [])
    if str_id in known:
        del known[str_id]
    if chat_id in allowed:
        allowed.remove(chat_id)
    data["known_groups"] = known
    data["allowed_ids"] = allowed
    _save(data)
    logger.info(f"[группы] удалена: {chat_id}")


def get_known_groups() -> dict[int, str]:
    data = _load()
    known = data.get("known_groups", {})
    return {int(k): v for k, v in known.items()}


def get_allowed_ids() -> set[int]:
    data = _load()
    return set(data.get("allowed_ids", []))


def is_group_allowed(chat_id: int) -> bool:
    return chat_id in get_allowed_ids()


def toggle_group(chat_id: int) -> bool:
    data = _load()
    allowed = data.get("allowed_ids", [])
    if chat_id in allowed:
        allowed.remove(chat_id)
        new_state = False
    else:
        allowed.append(chat_id)
        new_state = True
    data["allowed_ids"] = allowed
    _save(data)
    logger.info(f"[группы] {'включена' if new_state else 'выключена'}: {chat_id}")
    return new_state
