from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
STORE_PATH = DATA / "chats.json"
_LOCK = threading.Lock()
MAX_SESSIONS = 80
MAX_MESSAGES = 240
MAX_CONTENT = 20000


def _empty() -> dict[str, Any]:
    return {"max_mb": 32, "visitors": {}}


def _load() -> dict[str, Any]:
    DATA.mkdir(parents=True, exist_ok=True)
    if not STORE_PATH.exists():
        return _empty()
    try:
        data = json.loads(STORE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return _empty()
    if not isinstance(data.get("visitors"), dict):
        data["visitors"] = {}
    if "max_mb" not in data:
        data["max_mb"] = 32
    return data


def _save(data: dict[str, Any]) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    STORE_PATH.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _trim_session(raw: dict[str, Any]) -> dict[str, Any] | None:
    sid = str(raw.get("id") or "").strip()
    if not sid:
        return None
    messages = []
    for item in raw.get("messages") or []:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "")
        if role not in {"user", "assistant"}:
            continue
        content = str(item.get("content") or "")[:MAX_CONTENT]
        messages.append({"role": role, "content": content})
        if len(messages) >= MAX_MESSAGES:
            break
    theme = raw.get("userTheme") if isinstance(raw.get("userTheme"), dict) else {}
    return {
        "id": sid,
        "title": str(raw.get("title") or "新会话")[:80],
        "userTheme": {
            "bg": str(theme.get("bg") or ""),
            "ink": str(theme.get("ink") or ""),
        },
        "messages": messages,
        "updatedAt": int(raw.get("updatedAt") or 0),
    }


def _max_mb(data: dict[str, Any]) -> int:
    try:
        value = int(data.get("max_mb") or 32)
    except (TypeError, ValueError):
        value = 32
    return max(1, min(value, 4096))


def _usage_bytes(data: dict[str, Any]) -> int:
    return len(json.dumps(data, ensure_ascii=False).encode("utf-8"))


def _evict_oldest(data: dict[str, Any], max_mb: int) -> None:
    limit = max_mb * 1024 * 1024
    visitors = data.setdefault("visitors", {})
    while _usage_bytes(data) > limit:
        oldest: tuple[int, str, str] | None = None
        for visitor_id, rec in visitors.items():
            if not isinstance(rec, dict):
                continue
            for session in rec.get("sessions") or []:
                if not isinstance(session, dict) or not session.get("id"):
                    continue
                key = (int(session.get("updatedAt") or 0), str(visitor_id), str(session.get("id")))
                if oldest is None or key < oldest:
                    oldest = key
        if oldest is None:
            break
        _, visitor_id, chat_id = oldest
        rec = visitors.get(visitor_id) or {}
        remaining = [
            session
            for session in rec.get("sessions") or []
            if isinstance(session, dict) and str(session.get("id")) != chat_id
        ]
        if remaining:
            rec["sessions"] = remaining
            visitors[visitor_id] = rec
        else:
            visitors.pop(visitor_id, None)


def stats() -> dict[str, Any]:
    with _LOCK:
        data = _load()
        used = _usage_bytes(data)
        max_mb = _max_mb(data)
    return {
        "max_mb": max_mb,
        "used_bytes": used,
        "used_mb": round(used / (1024 * 1024), 2),
    }


def set_max_mb(max_mb: int) -> dict[str, Any]:
    with _LOCK:
        data = _load()
        data["max_mb"] = max(1, min(int(max_mb), 4096))
        _evict_oldest(data, data["max_mb"])
        _save(data)
    return stats()


def save_visitor_chats(visitor_id: str, sessions: list[Any], current_id: str | None) -> None:
    visitor_id = (visitor_id or "").strip()
    if not visitor_id:
        return
    cleaned: list[dict[str, Any]] = []
    for item in sessions:
        if not isinstance(item, dict):
            continue
        row = _trim_session(item)
        if row:
            cleaned.append(row)
    cleaned.sort(key=lambda row: int(row.get("updatedAt") or 0), reverse=True)
    cleaned = cleaned[:MAX_SESSIONS]
    with _LOCK:
        data = _load()
        data["visitors"][visitor_id] = {
            "currentId": str(current_id or ""),
            "sessions": cleaned,
        }
        _evict_oldest(data, _max_mb(data))
        _save(data)


def load_visitor_chats(visitor_id: str) -> dict[str, Any]:
    visitor_id = (visitor_id or "").strip()
    with _LOCK:
        data = _load()
        rec = data["visitors"].get(visitor_id) or {}
    sessions = rec.get("sessions") if isinstance(rec, dict) else []
    if not isinstance(sessions, list):
        sessions = []
    return {
        "currentId": str(rec.get("currentId") or "") if isinstance(rec, dict) else "",
        "sessions": sessions,
    }


def list_all() -> list[dict[str, Any]]:
    with _LOCK:
        data = _load()
    items: list[dict[str, Any]] = []
    for visitor_id, rec in (data.get("visitors") or {}).items():
        if not isinstance(rec, dict):
            continue
        for session in rec.get("sessions") or []:
            if not isinstance(session, dict):
                continue
            messages = session.get("messages") or []
            if not messages:
                continue
            items.append(
                {
                    "visitor_id": visitor_id,
                    "id": session.get("id"),
                    "title": session.get("title") or "新会话",
                    "updatedAt": int(session.get("updatedAt") or 0),
                    "userTheme": session.get("userTheme") or {},
                    "message_count": len(messages),
                    "preview": next(
                        (
                            str(m.get("content") or "")[:80]
                            for m in messages
                            if isinstance(m, dict) and m.get("role") == "user"
                        ),
                        "",
                    ),
                }
            )
    items.sort(key=lambda row: int(row.get("updatedAt") or 0), reverse=True)
    return items


def get_session(visitor_id: str, chat_id: str) -> dict[str, Any] | None:
    packed = load_visitor_chats(visitor_id)
    for session in packed["sessions"]:
        if isinstance(session, dict) and str(session.get("id")) == chat_id:
            return session
    return None
