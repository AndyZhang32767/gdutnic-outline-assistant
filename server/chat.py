from __future__ import annotations

import json
from typing import Any, AsyncIterator

import httpx

from server.mcp_client import OutlineMcpClient

SYSTEM_PROMPT = """你是面向 Outline 知识库的查询助手。
规则：
1. 回答用户问题前，必须先调用 MCP 工具检索或阅读相关文档，不要凭记忆编造。
2. 若检索不到，明确说明知识库中没有找到，并列出你尝试过的关键词。
3. 引用时写明文档标题；若工具返回了链接或 URL，一并给出。
4. 用用户使用的语言作答，默认简体中文。
5. 只基于工具返回的内容作答，不要扩写成未经证实的政策或数据。
"""


def normalize_openai_base(url: str) -> str:
    url = (url or "").strip().rstrip("/")
    if not url:
        return "https://api.openai.com/v1"
    if url.endswith("/chat/completions"):
        return url[: -len("/chat/completions")]
    return url


def mcp_tools_to_openai(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    converted = []
    for tool in tools:
        schema = tool.get("inputSchema") or {"type": "object", "properties": {}}
        converted.append(
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description") or "",
                    "parameters": schema,
                },
            }
        )
    return converted


def _extract_text(result: Any) -> str:
    if result is None:
        return ""
    if isinstance(result, str):
        return result
    content = result.get("content") if isinstance(result, dict) else None
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text") or "")
            elif isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
            else:
                parts.append(json.dumps(item, ensure_ascii=False))
        text = "\n".join(parts)
        if result.get("isError"):
            return f"[工具错误]\n{text}"
        return text
    return json.dumps(result, ensure_ascii=False)


async def stream_chat(
    *,
    openai_base: str,
    openai_key: str,
    model: str,
    messages: list[dict[str, Any]],
    mcp: OutlineMcpClient,
    tools: list[dict[str, Any]],
    extra_headers: dict[str, str] | None = None,
    provider: str = "",
    system_prompt: str = "",
) -> AsyncIterator[dict[str, Any]]:
    openai_tools = mcp_tools_to_openai(tools)
    prompt = (system_prompt or "").strip() or SYSTEM_PROMPT
    working = [{"role": "system", "content": prompt}, *messages]
    endpoint = f"{normalize_openai_base(openai_base)}/chat/completions"
    headers = {
        "Authorization": f"Bearer {openai_key}",
        "Content-Type": "application/json",
        **(extra_headers or {}),
    }
    max_rounds = 8

    async with httpx.AsyncClient(timeout=120.0) as client:
        for _ in range(max_rounds):
            payload: dict[str, Any] = {
                "model": model,
                "messages": working,
                "stream": True,
            }
            if not _is_thinking_model(model, provider):
                payload["temperature"] = 0.2
            else:
                payload["thinking"] = {"type": "enabled"}
                payload["reasoning_effort"] = "high"
            if openai_tools:
                payload["tools"] = openai_tools
                payload["tool_choice"] = "auto"

            assistant: dict[str, Any] = {
                "role": "assistant",
                "content": "",
                "tool_calls": [],
                "reasoning_content": "",
            }
            think_open = False
            async for event in _stream_completion(client, endpoint, headers, payload):
                kind = event["type"]
                if kind == "thinking":
                    if event.get("text"):
                        assistant["reasoning_content"] += event["text"]
                    yield {"type": "thinking"}
                elif kind == "delta":
                    visible, think_open = _strip_think(event["text"], think_open)
                    if think_open:
                        yield {"type": "thinking"}
                    if visible:
                        assistant["content"] += visible
                        yield {"type": "delta", "text": visible}
                elif kind == "tool_call_delta":
                    _merge_tool_call(assistant["tool_calls"], event["index"], event["delta"])
                elif kind == "error":
                    yield event
                    return
                elif kind == "done":
                    pass

            if assistant["tool_calls"]:
                normalized_calls = []
                for call in assistant["tool_calls"]:
                    fn = call.get("function") or {}
                    normalized_calls.append(
                        {
                            "id": call.get("id") or f"call_{len(normalized_calls)}",
                            "type": "function",
                            "function": {
                                "name": fn.get("name") or "",
                                "arguments": fn.get("arguments") or "{}",
                            },
                        }
                    )
                working.append(
                    {
                        "role": "assistant",
                        "content": assistant["content"] or None,
                        "reasoning_content": assistant["reasoning_content"] or None,
                        "tool_calls": normalized_calls,
                    }
                )
                for call in normalized_calls:
                    name = call["function"]["name"]
                    raw_args = call["function"]["arguments"] or "{}"
                    try:
                        arguments = json.loads(raw_args) if raw_args.strip() else {}
                    except json.JSONDecodeError:
                        arguments = {"_raw": raw_args}
                    yield {"type": "tool_start", "name": name, "arguments": arguments}
                    try:
                        result = await mcp.call_tool(name, arguments if isinstance(arguments, dict) else {})
                        text = _extract_text(result)
                    except Exception as exc:
                        text = f"工具调用失败: {exc}"
                    yield {"type": "tool_end", "name": name, "result": text[:8000]}
                    working.append(
                        {
                            "role": "tool",
                            "tool_call_id": call["id"],
                            "content": text[:24000],
                        }
                    )
                continue

            yield {"type": "done", "content": assistant["content"]}
            return

        yield {"type": "error", "message": "工具调用轮次过多，已停止"}


def _is_thinking_model(model: str, provider: str = "") -> bool:
    blob = f"{model} {provider}".lower()
    return any(token in blob for token in ("deepseek", "reasoner", "r1", "thinking"))


def _reasoning_text(choice: dict[str, Any], delta: dict[str, Any]) -> str:
    message = choice.get("message") or {}
    for src in (delta, message, choice):
        if not isinstance(src, dict):
            continue
        for key in ("reasoning_content", "reasoning", "thinking", "reasoning_text"):
            value = src.get(key)
            if isinstance(value, str) and value:
                return value
    return ""


def _strip_think(text: str, in_think: bool) -> tuple[str, bool]:
    visible: list[str] = []
    i = 0
    while i < len(text):
        if in_think:
            end = text.find("</think>", i)
            if end == -1:
                return "".join(visible), True
            i = end + len("</think>")
            in_think = False
            continue
        start = text.find("<think>", i)
        if start == -1:
            visible.append(text[i:])
            break
        visible.append(text[i:start])
        in_think = True
        i = start + len("<think>")
    return "".join(visible), in_think


def _merge_tool_call(calls: list[dict[str, Any]], index: int, delta: dict[str, Any]) -> None:
    while len(calls) <= index:
        calls.append({"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
    target = calls[index]
    if delta.get("id"):
        target["id"] = delta["id"]
    fn = delta.get("function") or {}
    if fn.get("name"):
        target["function"]["name"] += fn["name"]
    if fn.get("arguments"):
        target["function"]["arguments"] += fn["arguments"]


async def _stream_completion(
    client: httpx.AsyncClient,
    endpoint: str,
    headers: dict[str, str],
    payload: dict[str, Any],
) -> AsyncIterator[dict[str, Any]]:
    async with client.stream("POST", endpoint, headers=headers, json=payload) as response:
        if response.status_code >= 400:
            body = (await response.aread()).decode("utf-8", errors="replace")
            yield {"type": "error", "message": f"模型接口错误 HTTP {response.status_code}: {body[:800]}"}
            return
        async for line in response.aiter_lines():
            if not line:
                continue
            if line.startswith(":"):
                continue
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                yield {"type": "done"}
                return
            try:
                chunk = json.loads(data)
            except json.JSONDecodeError:
                continue
            if chunk.get("error"):
                yield {"type": "error", "message": str(chunk["error"])}
                return
            choices = chunk.get("choices") or []
            if not choices:
                continue
            choice = choices[0]
            delta = choice.get("delta") or {}
            reasoning = _reasoning_text(choice, delta)
            if reasoning:
                yield {"type": "thinking", "text": reasoning}
            content = delta.get("content")
            if content:
                yield {"type": "delta", "text": content}
            for tc in delta.get("tool_calls") or []:
                yield {
                    "type": "tool_call_delta",
                    "index": tc.get("index") or 0,
                    "delta": tc,
                }
            if choice.get("finish_reason"):
                yield {"type": "done"}
