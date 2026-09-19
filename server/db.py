from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DB_PATH = DATA / "app.sqlite"

_lock = threading.RLock()
_conn: sqlite3.Connection | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS users (
  username TEXT PRIMARY KEY,
  password TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS oauth_clients (
  origin TEXT NOT NULL,
  redirect_uri TEXT NOT NULL,
  client_id TEXT NOT NULL,
  client_secret TEXT NOT NULL DEFAULT '',
  PRIMARY KEY (origin, redirect_uri)
);
CREATE TABLE IF NOT EXISTS visitors (
  id TEXT PRIMARY KEY,
  current_id TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS chats (
  visitor_id TEXT NOT NULL,
  id TEXT NOT NULL,
  title TEXT NOT NULL DEFAULT '新会话',
  updated_at INTEGER NOT NULL DEFAULT 0,
  theme_bg TEXT NOT NULL DEFAULT '',
  theme_ink TEXT NOT NULL DEFAULT '',
  PRIMARY KEY (visitor_id, id),
  FOREIGN KEY (visitor_id) REFERENCES visitors(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS messages (
  visitor_id TEXT NOT NULL,
  chat_id TEXT NOT NULL,
  seq INTEGER NOT NULL,
  role TEXT NOT NULL,
  content TEXT NOT NULL,
  PRIMARY KEY (visitor_id, chat_id, seq),
  FOREIGN KEY (visitor_id, chat_id) REFERENCES chats(visitor_id, id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_chats_updated ON chats(updated_at);
"""


def connect() -> sqlite3.Connection:
    global _conn
    with _lock:
        if _conn is None:
            DATA.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(DB_PATH), check_same_thread=False, isolation_level=None)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.executescript(SCHEMA)
            _conn = conn
            _migrate_json(conn)
            _retire_legacy_json()
        return _conn


@contextmanager
def read() -> Iterator[sqlite3.Connection]:
    with _lock:
        yield connect()


@contextmanager
def write() -> Iterator[sqlite3.Connection]:
    with _lock:
        conn = connect()
        conn.execute("BEGIN")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def get_setting(conn: sqlite3.Connection, key: str, default: Any = None) -> Any:
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    if not row:
        return default
    try:
        return json.loads(row["value"])
    except json.JSONDecodeError:
        return default


def set_setting(conn: sqlite3.Connection, key: str, value: Any) -> None:
    conn.execute(
        """
        INSERT INTO settings(key, value) VALUES(?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (key, json.dumps(value, ensure_ascii=False)),
    )


def _count(conn: sqlite3.Connection, table: str) -> int:
    row = conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()
    return int(row["n"] if row else 0)


def _read_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _retire(path: Path) -> None:
    if not path.exists():
        return
    bak = path.with_name(path.name + ".bak")
    try:
        path.replace(bak)
    except OSError as exc:
        print(f"[db] 无法归档 {path.name}: {exc}")


def _retire_legacy_json() -> None:
    for name in ("admin.json", "chats.json", "oauth_client.json"):
        _retire(DATA / name)


def _migrate_json(conn: sqlite3.Connection) -> None:
    admin = _read_json(DATA / "admin.json")
    chats = _read_json(DATA / "chats.json")
    oauth = _read_json(DATA / "oauth_client.json")
    changed = False
    conn.execute("BEGIN")
    try:
        if admin and isinstance(admin, dict) and _count(conn, "settings") == 0:
            _import_admin(conn, admin)
            changed = True
        if chats and isinstance(chats, dict) and _count(conn, "visitors") == 0 and _count(conn, "chats") == 0:
            _import_chats(conn, chats)
            changed = True
        if oauth and isinstance(oauth, dict) and _count(conn, "oauth_clients") == 0:
            _import_oauth(conn, oauth)
            changed = True
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    if changed:
        print(f"[db] 已迁移 JSON 到 SQLite: {DB_PATH}")


def _import_admin(conn: sqlite3.Connection, data: dict[str, Any]) -> None:
    set_setting(conn, "path", str(data.get("path") or ""))
    set_setting(conn, "username", str(data.get("username") or ""))
    set_setting(conn, "password", str(data.get("password") or ""))
    set_setting(conn, "model", data.get("model") if isinstance(data.get("model"), dict) else {})
    set_setting(conn, "mcp", data.get("mcp") if isinstance(data.get("mcp"), dict) else {})
    set_setting(conn, "qq", data.get("qq") if isinstance(data.get("qq"), dict) else {})
    users = data.get("users")
    if not isinstance(users, list):
        users = []
    name = str(data.get("username") or "").strip()
    password = str(data.get("password") or "")
    if name and password and not any(isinstance(u, dict) and u.get("username") == name for u in users):
        users.append({"username": name, "password": password})
    for item in users:
        if not isinstance(item, dict):
            continue
        username = str(item.get("username") or "").strip()
        hashed = str(item.get("password") or "")
        if username and hashed:
            conn.execute(
                "INSERT OR REPLACE INTO users(username, password) VALUES(?, ?)",
                (username, hashed),
            )


def _import_chats(conn: sqlite3.Connection, data: dict[str, Any]) -> None:
    try:
        max_mb = int(data.get("max_mb") or 32)
    except (TypeError, ValueError):
        max_mb = 32
    set_setting(conn, "chat_max_mb", max(1, min(max_mb, 4096)))
    visitors = data.get("visitors") if isinstance(data.get("visitors"), dict) else {}
    for visitor_id, rec in visitors.items():
        vid = str(visitor_id or "").strip()
        if not vid or not isinstance(rec, dict):
            continue
        sessions = rec.get("sessions") if isinstance(rec.get("sessions"), list) else []
        conn.execute(
            "INSERT OR REPLACE INTO visitors(id, current_id) VALUES(?, ?)",
            (vid, str(rec.get("currentId") or "")),
        )
        for session in sessions:
            if not isinstance(session, dict):
                continue
            sid = str(session.get("id") or "").strip()
            messages = session.get("messages") if isinstance(session.get("messages"), list) else []
            if not sid or not messages:
                continue
            theme = session.get("userTheme") if isinstance(session.get("userTheme"), dict) else {}
            conn.execute(
                """
                INSERT OR REPLACE INTO chats(visitor_id, id, title, updated_at, theme_bg, theme_ink)
                VALUES(?, ?, ?, ?, ?, ?)
                """,
                (
                    vid,
                    sid,
                    str(session.get("title") or "新会话")[:80],
                    int(session.get("updatedAt") or 0),
                    str(theme.get("bg") or ""),
                    str(theme.get("ink") or ""),
                ),
            )
            for seq, item in enumerate(messages):
                if not isinstance(item, dict):
                    continue
                role = str(item.get("role") or "")
                if role not in {"user", "assistant"}:
                    continue
                conn.execute(
                    "INSERT INTO messages(visitor_id, chat_id, seq, role, content) VALUES(?, ?, ?, ?, ?)",
                    (vid, sid, seq, role, json.dumps(item.get("content"), ensure_ascii=False)),
                )


def _import_oauth(conn: sqlite3.Connection, stored: dict[str, Any]) -> None:
    for key, rec in stored.items():
        if not isinstance(rec, dict):
            continue
        origin, sep, redirect_uri = str(key).partition("|")
        if not sep:
            continue
        conn.execute(
            """
            INSERT OR REPLACE INTO oauth_clients(origin, redirect_uri, client_id, client_secret)
            VALUES(?, ?, ?, ?)
            """,
            (
                origin,
                redirect_uri,
                str(rec.get("client_id") or ""),
                str(rec.get("client_secret") or ""),
            ),
        )
