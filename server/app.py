from __future__ import annotations

import json
import os
import secrets
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from server.chat import stream_chat
from server.mcp_client import McpError, OutlineMcpClient, normalize_mcp_url
from server.oauth import exchange_code, start_oauth

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
DATA = ROOT / "data"
ICON = ROOT / "icon"
DEFAULT_MCP = ""


def _session_secret() -> str:
    env = os.environ.get("SESSION_SECRET")
    if env:
        return env
    DATA.mkdir(parents=True, exist_ok=True)
    path = DATA / "session_secret.txt"
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    secret = secrets.token_hex(32)
    path.write_text(secret, encoding="utf-8")
    return secret


class NoCacheStatic(StaticFiles):
    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        return response


app = FastAPI(title="GDUTNIC Outline 查询助手")
app.add_middleware(
    SessionMiddleware,
    secret_key=_session_secret(),
    same_site="lax",
    https_only=False,
)

app.mount("/static", NoCacheStatic(directory=WEB), name="static")
ICON.mkdir(parents=True, exist_ok=True)
app.mount("/icon", NoCacheStatic(directory=ICON), name="icon")


@app.get("/favicon.ico")
async def favicon():
    path = ICON / "gdutnic.png"
    if not path.exists():
        raise HTTPException(status_code=404, detail="缺少 icon/gdutnic.png")
    return FileResponse(path, media_type="image/png")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(
        WEB / "index.html",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
        },
    )


@app.get("/api/defaults")
async def defaults(request: Request) -> dict[str, Any]:
    session = request.session
    return {
        "mcp_url": session.get("mcp_url") or "",
        "has_outline_token": bool(session.get("outline_token") or session.get("mcp_api_key")),
        "oauth_connected": bool(session.get("outline_token")),
    }


@app.post("/api/settings")
async def save_settings(request: Request) -> dict[str, Any]:
    body = await request.json()
    raw = (body.get("mcp_url") or "").strip()
    if raw:
        request.session["mcp_url"] = normalize_mcp_url(raw)
    api_key = (body.get("mcp_api_key") or "").strip()
    if api_key:
        request.session["mcp_api_key"] = api_key
    if body.get("clear_mcp_api_key"):
        request.session.pop("mcp_api_key", None)
    return {"ok": True, "mcp_url": request.session["mcp_url"]}


@app.post("/api/mcp/connect")
async def mcp_connect(request: Request) -> dict[str, Any]:
    body = await request.json()
    raw = (body.get("mcp_url") or request.session.get("mcp_url") or "").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="请先填写企业 Outline / MCP 地址")
    mcp_url = normalize_mcp_url(raw)
    request.session["mcp_url"] = mcp_url
    token = _token_from(request, body)
    if not token:
        raise HTTPException(status_code=401, detail="尚未登录：请点击「企业登录」在弹窗中输入账号密码")
    try:
        async with OutlineMcpClient(mcp_url, token) as mcp:
            tools = await mcp.list_tools()
            return {
                "ok": True,
                "mcp_url": mcp.mcp_url,
                "server": mcp.server_info.get("serverInfo") or mcp.server_info,
                "tools": [
                    {"name": t.get("name"), "description": t.get("description") or ""}
                    for t in tools
                ],
            }
    except McpError as exc:
        print(f"[mcp_connect] {exc} payload={exc.payload!r}")
        status = exc.status if exc.status and 400 <= exc.status < 600 else 502
        raise HTTPException(status_code=status, detail=str(exc)) from exc
    except Exception as exc:
        print(f"[mcp_connect] {type(exc).__name__}: {exc}")
        raise HTTPException(status_code=502, detail=f"MCP 连接失败: {type(exc).__name__}: {exc}") from exc


@app.get("/api/mcp/oauth/start")
async def oauth_start(request: Request, mcp_url: str | None = None):
    raw = (mcp_url or request.session.get("mcp_url") or "").strip()
    if not raw:
        return _oauth_popup_result("missing_url")
    mcp_url = normalize_mcp_url(raw)
    redirect_uri = str(request.url_for("oauth_callback"))
    try:
        flow = await start_oauth(mcp_url, redirect_uri)
    except Exception as exc:
        return _oauth_popup_result("start", str(exc))
    request.session["oauth_flow"] = flow
    request.session["mcp_url"] = mcp_url
    return RedirectResponse(flow["authorize_url"], status_code=302)


@app.get("/api/mcp/oauth/callback")
async def oauth_callback(request: Request, code: str | None = None, state: str | None = None) -> HTMLResponse:
    flow = request.session.get("oauth_flow") or {}
    if not code or not flow:
        return _oauth_popup_result("missing")
    if state != flow.get("state"):
        return _oauth_popup_result("state")
    try:
        tokens = await exchange_code(
            token_endpoint=flow["token_endpoint"],
            client_id=flow["client_id"],
            client_secret=flow.get("client_secret") or "",
            code=code,
            redirect_uri=str(request.url_for("oauth_callback")),
            code_verifier=flow["code_verifier"],
            mcp_url=flow["mcp_url"],
        )
    except Exception as exc:
        return _oauth_popup_result("token", str(exc))
    request.session["outline_token"] = (
        tokens.get("access_token")
        or (tokens.get("data") or {}).get("access_token")
        or ""
    )
    request.session["outline_refresh"] = tokens.get("refresh_token")
    request.session["oauth_meta"] = {
        "token_endpoint": flow["token_endpoint"],
        "client_id": flow["client_id"],
        "client_secret": flow.get("client_secret") or "",
        "mcp_url": flow["mcp_url"],
    }
    request.session.pop("oauth_flow", None)
    return _oauth_popup_result("ok")


@app.post("/api/mcp/logout")
async def mcp_logout(request: Request) -> dict[str, bool]:
    for key in ("outline_token", "outline_refresh", "oauth_meta", "mcp_api_key", "oauth_flow"):
        request.session.pop(key, None)
    return {"ok": True}


@app.post("/api/chat")
async def chat(request: Request) -> StreamingResponse:
    body = await request.json()
    raw = (body.get("mcp_url") or request.session.get("mcp_url") or "").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="请先填写企业 Outline / MCP 地址")
    mcp_url = normalize_mcp_url(raw)
    request.session["mcp_url"] = mcp_url
    token = _token_from(request, body)
    if not token:
        return JSONResponse({"error": "尚未连接 Outline MCP，请先在弹窗中完成企业登录"}, status_code=401)

    openai_base = (body.get("openai_base_url") or "").strip()
    openai_key = (body.get("openai_api_key") or "").strip()
    model = (body.get("openai_model") or "").strip()
    messages = body.get("messages") or []
    if not openai_base or not openai_key or not model:
        raise HTTPException(status_code=400, detail="请填写 OpenAI 兼容接口的 Base URL、API Key 和模型名")
    if not messages:
        raise HTTPException(status_code=400, detail="消息不能为空")

    async def events():
        try:
            async with OutlineMcpClient(mcp_url, token) as mcp:
                tools = await mcp.list_tools()
                yield _sse({"type": "mcp_ready", "tools": [t.get("name") for t in tools]})
                async for event in stream_chat(
                    openai_base=openai_base,
                    openai_key=openai_key,
                    model=model,
                    messages=messages,
                    mcp=mcp,
                    tools=tools,
                    provider=body.get("provider") or "",
                ):
                    yield _sse(event)
        except McpError as exc:
            yield _sse({"type": "error", "message": str(exc)})
        except Exception as exc:
            yield _sse({"type": "error", "message": str(exc)})

    return StreamingResponse(events(), media_type="text/event-stream")


def _token_from(request: Request, body: dict[str, Any]) -> str:
    from_body = (body.get("mcp_api_key") or "").strip()
    if from_body:
        request.session["mcp_api_key"] = from_body
        return from_body
    return (request.session.get("mcp_api_key") or request.session.get("outline_token") or "").strip()


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _oauth_popup_result(status: str, message: str = "") -> HTMLResponse:
    payload = json.dumps({"type": "outline-oauth", "status": status, "message": message}, ensure_ascii=False)
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
  <head><meta charset="utf-8"><title>知识库登录</title></head>
  <body style="font-family:sans-serif;padding:24px">
    <p>{"登录成功，正在关闭窗口…" if status == "ok" else "登录未完成，可以关闭此窗口后重试。"}</p>
    <script>
      const payload = {payload};
      try {{
        if (window.opener) {{
          window.opener.postMessage(payload, window.location.origin);
        }}
      }} catch (e) {{}}
      window.close();
      setTimeout(function () {{
        if (!window.closed) location.replace("/?oauth=" + encodeURIComponent(payload.status));
      }}, 400);
    </script>
  </body>
</html>"""
    return HTMLResponse(html)
