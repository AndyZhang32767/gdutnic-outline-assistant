from __future__ import annotations

import hashlib
import secrets
import string
from typing import Any

from server import db

ALPHABET = string.ascii_lowercase + string.digits
ITERATIONS = 180_000


def _new_path() -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(8))


def _hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), ITERATIONS)
    return f"{salt}${dk.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    if not stored or "$" not in stored:
        return False
    salt, _ = stored.split("$", 1)
    return secrets.compare_digest(_hash_password(password, salt), stored)


def _empty() -> dict[str, Any]:
    return {
        "path": _new_path(),
        "username": "",
        "password": "",
        "users": [],
        "model": {
            "provider": "openai",
            "openai_base": "https://api.openai.com/v1",
            "openai_key": "",
            "openai_model": "",
            "system_prompt": "",
            "keys_by_provider": {},
        },
        "mcp": {
            "mcp_url": "",
            "mcp_api_key": "",
            "mcp_heat": 50,
            "outline_access_token": "",
            "outline_refresh_token": "",
            "oauth_meta": {},
        },
        "qq": {
            "app_id": "",
            "app_secret": "",
            "enabled": False,
        },
    }


def load() -> dict[str, Any]:
    with db.read() as conn:
        stored_path = db.get_setting(conn, "path", "")
        data = {
            "path": stored_path,
            "username": str(db.get_setting(conn, "username", "") or ""),
            "password": str(db.get_setting(conn, "password", "") or ""),
            "users": [
                {"username": str(row["username"] or ""), "password": str(row["password"] or "")}
                for row in conn.execute("SELECT username, password FROM users ORDER BY username")
            ],
            "model": db.get_setting(conn, "model", {}) or {},
            "mcp": db.get_setting(conn, "mcp", {}) or {},
            "qq": db.get_setting(conn, "qq", {}) or {},
        }
    dirty = False
    if not isinstance(data.get("path"), str) or len(data["path"]) != 8:
        data["path"] = _new_path()
        dirty = True
    if not isinstance(data.get("model"), dict):
        data["model"] = {}
        dirty = True
    if not isinstance(data.get("mcp"), dict):
        data["mcp"] = {}
        dirty = True
    if not isinstance(data.get("qq"), dict):
        data["qq"] = {}
        dirty = True
    for section in ("model", "mcp", "qq"):
        for key, value in _empty()[section].items():
            if key not in data[section]:
                data[section][key] = value
                dirty = True
    _ensure_users(data)
    if dirty or not stored_path:
        save(data)
    return data


def save(data: dict[str, Any]) -> None:
    users = _ensure_users(data)
    with db.write() as conn:
        db.set_setting(conn, "path", str(data.get("path") or ""))
        db.set_setting(conn, "username", str(data.get("username") or ""))
        db.set_setting(conn, "password", str(data.get("password") or ""))
        db.set_setting(conn, "model", data.get("model") if isinstance(data.get("model"), dict) else {})
        db.set_setting(conn, "mcp", data.get("mcp") if isinstance(data.get("mcp"), dict) else {})
        db.set_setting(conn, "qq", data.get("qq") if isinstance(data.get("qq"), dict) else {})
        conn.execute("DELETE FROM users")
        for item in users:
            name = str(item.get("username") or "").strip()
            password = str(item.get("password") or "")
            if name:
                conn.execute("INSERT INTO users(username, password) VALUES(?, ?)", (name, password))


def path() -> str:
    return load()["path"]


def _ensure_users(data: dict[str, Any]) -> list[dict[str, Any]]:
    users = data.get("users")
    if not isinstance(users, list):
        users = []
    migrated = [
        {"username": str(item.get("username") or ""), "password": str(item.get("password") or "")}
        for item in users
        if isinstance(item, dict)
    ]
    name = str(data.get("username") or "").strip()
    password = str(data.get("password") or "")
    if name and password and not any(item.get("username") == name for item in migrated):
        migrated.append({"username": name, "password": password})
    data["users"] = migrated
    return migrated


def users() -> list[dict[str, Any]]:
    return list(_ensure_users(load()))


def has_user() -> bool:
    return any(item.get("username") and item.get("password") for item in users())


def _validate_account(username: str, password: str) -> str:
    name = username.strip()
    if not name or len(name) > 64:
        raise ValueError("请填写用户名")
    if len(password) < 6:
        raise ValueError("密码至少 6 位")
    return name


def register(username: str, password: str) -> None:
    if has_user():
        raise ValueError("管理员已注册，请直接登录")
    add_user(username, password)


def add_user(username: str, password: str) -> None:
    name = _validate_account(username, password)
    data = load()
    existing = _ensure_users(data)
    if any(item.get("username") == name for item in existing):
        raise ValueError("用户名已存在")
    existing.append({"username": name, "password": _hash_password(password)})
    if not data.get("username"):
        data["username"] = name
        data["password"] = existing[-1]["password"]
    save(data)


def usernames() -> list[str]:
    return [item["username"] for item in users() if item.get("username")]


def update_user(old_username: str, username: str, password: str) -> str:
    old = old_username.strip()
    name = username.strip()
    if not name or len(name) > 64:
        raise ValueError("请填写用户名")
    data = load()
    existing = _ensure_users(data)
    target = next((item for item in existing if item.get("username") == old), None)
    if not target:
        raise ValueError("账号不存在")
    if name != old and any(item.get("username") == name for item in existing):
        raise ValueError("用户名已存在")
    target["username"] = name
    if password:
        if len(password) < 6:
            raise ValueError("密码至少 6 位")
        target["password"] = _hash_password(password)
    if data.get("username") == old:
        data["username"] = name
        data["password"] = target["password"]
    save(data)
    return name


def delete_user(username: str, current_username: str = "") -> None:
    name = username.strip()
    if current_username and name == current_username.strip():
        raise ValueError("不能删除当前登录的管理员")
    data = load()
    existing = _ensure_users(data)
    if not any(item.get("username") == name for item in existing):
        raise ValueError("账号不存在")
    remaining = [item for item in existing if item.get("username") != name]
    if not remaining:
        raise ValueError("不能删除最后一个管理员")
    data["users"] = remaining
    if data.get("username") == name:
        data["username"] = remaining[0]["username"]
        data["password"] = remaining[0]["password"]
    save(data)


def verify_login(username: str, password: str) -> bool:
    name = username.strip()
    for item in users():
        if item.get("username") == name:
            return _verify_password(password, item.get("password") or "")
    return False


def model_config() -> dict[str, Any]:
    return dict(load().get("model") or {})


def save_model(body: dict[str, Any]) -> dict[str, Any]:
    data = load()
    model = data.setdefault("model", _empty()["model"])
    if "provider" in body:
        model["provider"] = str(body.get("provider") or "").strip() or "custom"
    if "openai_base" in body:
        model["openai_base"] = str(body.get("openai_base") or "").strip()
    if "openai_key" in body:
        key = str(body.get("openai_key") or "")
        if key and not set(key) <= {"•"}:
            model["openai_key"] = key
    if "openai_model" in body:
        model["openai_model"] = str(body.get("openai_model") or "").strip()
    if "system_prompt" in body:
        model["system_prompt"] = str(body.get("system_prompt") or "")
    if isinstance(body.get("keys_by_provider"), dict):
        model["keys_by_provider"] = {
            str(k): str(v) for k, v in body["keys_by_provider"].items() if isinstance(v, str)
        }
    save(data)
    return model_public()


def system_prompt() -> str:
    from server.chat import SYSTEM_PROMPT

    text = str(model_config().get("system_prompt") or "").strip()
    return text or SYSTEM_PROMPT


def model_public() -> dict[str, Any]:
    model = model_config()
    key = model.get("openai_key") or ""
    return {
        "provider": model.get("provider") or "openai",
        "openai_base": model.get("openai_base") or "",
        "openai_model": model.get("openai_model") or "",
        "openai_key": key,
        "system_prompt": system_prompt(),
        "has_key": bool(key.strip()),
        "keys_by_provider": model.get("keys_by_provider") or {},
    }


def clamp_mcp_heat(value: Any) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        n = 50
    return max(0, min(100, n))


def mcp_heat() -> int:
    mcp = mcp_config()
    if "mcp_heat" in mcp:
        return clamp_mcp_heat(mcp.get("mcp_heat"))
    return clamp_mcp_heat(model_config().get("mcp_heat", 50))


def chat_credentials() -> tuple[str, str, str, str]:
    model = model_config()
    return (
        (model.get("openai_base") or "").strip(),
        (model.get("openai_key") or "").strip(),
        (model.get("openai_model") or "").strip(),
        (model.get("provider") or "").strip(),
    )


def mcp_config() -> dict[str, Any]:
    return dict(load().get("mcp") or {})


def mcp_url() -> str:
    return (mcp_config().get("mcp_url") or "").strip()


def mcp_api_key() -> str:
    return (mcp_config().get("mcp_api_key") or "").strip()


def oauth_tokens() -> dict[str, Any]:
    mcp = mcp_config()
    meta = mcp.get("oauth_meta") if isinstance(mcp.get("oauth_meta"), dict) else {}
    return {
        "access_token": str(mcp.get("outline_access_token") or "").strip(),
        "refresh_token": str(mcp.get("outline_refresh_token") or "").strip(),
        "oauth_meta": dict(meta),
    }


def oauth_connected() -> bool:
    return bool(oauth_tokens()["access_token"])


def mcp_oauth_token() -> str:
    return oauth_tokens()["access_token"]


def save_oauth(access: str, refresh: str | None = None, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    data = load()
    mcp = data.setdefault("mcp", _empty()["mcp"])
    mcp["outline_access_token"] = str(access or "").strip()
    if refresh is not None:
        refresh_s = str(refresh or "").strip()
        if refresh_s:
            mcp["outline_refresh_token"] = refresh_s
        elif refresh == "":
            mcp["outline_refresh_token"] = ""
    if meta:
        mcp["oauth_meta"] = {
            "token_endpoint": str(meta.get("token_endpoint") or ""),
            "client_id": str(meta.get("client_id") or ""),
            "client_secret": str(meta.get("client_secret") or ""),
            "mcp_url": str(meta.get("mcp_url") or mcp.get("mcp_url") or ""),
        }
    save(data)
    return mcp_public()


def clear_oauth() -> dict[str, Any]:
    data = load()
    mcp = data.setdefault("mcp", _empty()["mcp"])
    mcp["outline_access_token"] = ""
    mcp["outline_refresh_token"] = ""
    mcp["oauth_meta"] = {}
    save(data)
    return mcp_public()


async def refresh_mcp_oauth() -> str:
    from server.oauth import refresh_access_token

    stored = oauth_tokens()
    refresh = stored["refresh_token"]
    meta = stored["oauth_meta"]
    if not refresh or not str(meta.get("token_endpoint") or "").strip():
        raise RuntimeError("知识库登录已过期，请在管理员界面重新点击「网协认证登陆」")
    tokens = await refresh_access_token(
        token_endpoint=str(meta.get("token_endpoint") or ""),
        client_id=str(meta.get("client_id") or ""),
        client_secret=str(meta.get("client_secret") or ""),
        refresh_token=refresh,
        mcp_url=str(meta.get("mcp_url") or mcp_url()),
    )
    access = str(
        tokens.get("access_token")
        or (tokens.get("data") or {}).get("access_token")
        or ""
    ).strip()
    if not access:
        raise RuntimeError("刷新知识库登录失败，请在管理员界面重新登录")
    save_oauth(access, tokens.get("refresh_token") or refresh, meta)
    return access


def mcp_public() -> dict[str, Any]:
    mcp = mcp_config()
    return {
        "mcp_url": mcp.get("mcp_url") or "",
        "mcp_heat": mcp_heat(),
        "oauth_connected": oauth_connected(),
    }


def save_mcp(body: dict[str, Any]) -> dict[str, Any]:
    from server.mcp_client import normalize_mcp_url

    data = load()
    mcp = data.setdefault("mcp", _empty()["mcp"])
    if "mcp_url" in body:
        raw = str(body.get("mcp_url") or "").strip()
        mcp["mcp_url"] = normalize_mcp_url(raw) if raw else ""
    if "mcp_heat" in body:
        mcp["mcp_heat"] = clamp_mcp_heat(body.get("mcp_heat"))
        model = data.get("model")
        if isinstance(model, dict):
            model.pop("mcp_heat", None)
    save(data)
    return mcp_public()


def qq_config() -> dict[str, Any]:
    cfg = dict(load().get("qq") or {})
    defaults = _empty()["qq"]
    for key, value in defaults.items():
        cfg.setdefault(key, value)
    return cfg


def qq_public() -> dict[str, Any]:
    qq = qq_config()
    secret = str(qq.get("app_secret") or "")
    return {
        "app_id": str(qq.get("app_id") or "").strip(),
        "app_secret": secret,
        "has_secret": bool(secret.strip()),
        "enabled": bool(qq.get("enabled")),
        "oauth_connected": oauth_connected(),
    }


def save_qq(body: dict[str, Any]) -> dict[str, Any]:
    data = load()
    qq = data.setdefault("qq", _empty()["qq"])
    if "app_id" in body:
        qq["app_id"] = str(body.get("app_id") or "").strip()
    if "app_secret" in body:
        secret = str(body.get("app_secret") or "")
        if secret and not set(secret) <= {"•"}:
            qq["app_secret"] = secret
        elif secret == "":
            qq["app_secret"] = ""
    if "enabled" in body:
        qq["enabled"] = bool(body.get("enabled"))
    save(data)
    return qq_public()
