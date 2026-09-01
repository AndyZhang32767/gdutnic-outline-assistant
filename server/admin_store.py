from __future__ import annotations

import hashlib
import json
import secrets
import string
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
STORE_PATH = DATA / "admin.json"
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
        },
    }


def load() -> dict[str, Any]:
    DATA.mkdir(parents=True, exist_ok=True)
    if not STORE_PATH.exists():
        data = _empty()
        save(data)
        return data
    try:
        data = json.loads(STORE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        data = _empty()
        save(data)
        return data
    if not isinstance(data.get("path"), str) or len(data["path"]) != 8:
        data["path"] = _new_path()
        save(data)
    data.setdefault("model", _empty()["model"])
    data.setdefault("mcp", _empty()["mcp"])
    _ensure_users(data)
    return data


def save(data: dict[str, Any]) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    STORE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


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


def mcp_public() -> dict[str, Any]:
    mcp = mcp_config()
    key = mcp.get("mcp_api_key") or ""
    return {
        "mcp_url": mcp.get("mcp_url") or "",
        "mcp_api_key": key,
        "has_key": bool(str(key).strip()),
    }


def save_mcp(body: dict[str, Any]) -> dict[str, Any]:
    from server.mcp_client import normalize_mcp_url

    data = load()
    mcp = data.setdefault("mcp", _empty()["mcp"])
    if "mcp_url" in body:
        raw = str(body.get("mcp_url") or "").strip()
        mcp["mcp_url"] = normalize_mcp_url(raw) if raw else ""
    if "mcp_api_key" in body:
        key = str(body.get("mcp_api_key") or "")
        if key and not set(key) <= {"•"}:
            mcp["mcp_api_key"] = key
        elif key == "":
            mcp["mcp_api_key"] = ""
    save(data)
    return mcp_public()
