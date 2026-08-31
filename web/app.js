const STORAGE_KEY = "gdutnic-outline-assistant";

const PROVIDERS = [
  {
    id: "openai",
    name: "OpenAI",
    base: "https://api.openai.com/v1",
    keyHint: "sk-...",
    models: ["gpt-5.6", "gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna"],
    hint: "官方 OpenAI Chat Completions。gpt-5.6 会路由到 gpt-5.6-sol。",
  },
  {
    id: "gemini",
    name: "Google Gemini",
    base: "https://generativelanguage.googleapis.com/v1beta/openai",
    keyHint: "AIza...",
    models: ["gemini-3.7-flash", "gemini-3.5-flash", "gemini-3.1-pro-preview"],
    hint: "Gemini 的 OpenAI 兼容接口。",
  },
  {
    id: "grok",
    name: "xAI Grok",
    base: "https://api.x.ai/v1",
    keyHint: "xai-...",
    models: ["grok-4.6", "grok-4.5", "grok-4.3"],
    hint: "xAI 控制台申请的 Grok API Key。",
  },
  {
    id: "deepseek",
    name: "DeepSeek",
    base: "https://api.deepseek.com",
    keyHint: "sk-...",
    models: ["deepseek-v4-flash", "deepseek-v4-pro"],
    hint: "DeepSeek 官方 OpenAI 兼容接口。",
  },
  {
    id: "qwen",
    name: "通义千问",
    base: "https://dashscope.aliyuncs.com/compatible-mode/v1",
    keyHint: "sk-...",
    models: ["qwen3.7-plus", "qwen3.7-max", "qwen-plus", "qwen-flash", "qwen-max"],
    hint: "阿里云百炼 compatible-mode。",
  },
  {
    id: "moonshot",
    name: "Moonshot / Kimi",
    base: "https://api.moonshot.cn/v1",
    keyHint: "sk-...",
    models: ["kimi-k3", "kimi-k2.6", "kimi-k2.7-code", "kimi-k2.7-code-highspeed"],
    hint: "Kimi 开放平台。kimi-k2 / moonshot-v1 已下线。",
  },
  {
    id: "zhipu",
    name: "智谱 GLM",
    base: "https://open.bigmodel.cn/api/paas/v4",
    keyHint: "API Key",
    models: ["glm-5.3", "glm-5.3-flash", "glm-5.2", "glm-4.7", "glm-4.7-flash"],
    hint: "智谱开放平台，路径已含 v4。",
  },
  {
    id: "siliconflow",
    name: "硅基流动",
    base: "https://api.siliconflow.cn/v1",
    keyHint: "sk-...",
    models: [
      "deepseek-ai/DeepSeek-V4-Pro",
      "deepseek-ai/DeepSeek-V4-Flash",
      "Qwen/Qwen3.5-397B-A17B",
      "Qwen/Qwen3-32B",
    ],
    hint: "国内常用中转，模型名需带组织前缀。",
  },
  {
    id: "doubao",
    name: "火山方舟 Doubao",
    base: "https://ark.cn-beijing.volces.com/api/v3",
    keyHint: "方舟 API Key",
    models: ["doubao-seed-2.1-pro", "doubao-seed-2.1-turbo"],
    hint: "也可在厂商「自定义」中填写方舟接入点 ID（ep-...）。",
  },
  {
    id: "ollama",
    name: "Ollama（本地）",
    base: "http://127.0.0.1:11434/v1",
    keyHint: "可填 ollama",
    models: ["llama3.2", "qwen3", "deepseek-r1"],
    hint: "本机 Ollama，Key 可填任意非空值。需先 ollama pull 对应模型。",
  },
  {
    id: "custom",
    name: "自定义",
    base: "",
    keyHint: "sk-...",
    models: [],
    hint: "任意兼容 /chat/completions 的网关，自行填写 Base URL 和模型名。",
  },
];

const els = {
  mcpUrl: document.getElementById("mcpUrl"),
  mcpKey: document.getElementById("mcpKey"),
  provider: document.getElementById("provider"),
  openaiBase: document.getElementById("openaiBase"),
  openaiKey: document.getElementById("openaiKey"),
  openaiModelSelect: document.getElementById("openaiModelSelect"),
  openaiModel: document.getElementById("openaiModel"),
  modelSelectWrap: document.getElementById("modelSelectWrap"),
  customModelWrap: document.getElementById("customModelWrap"),
  providerHint: document.getElementById("providerHint"),
  mcpStatus: document.getElementById("mcpStatus"),
  thread: document.getElementById("thread"),
  input: document.getElementById("input"),
  form: document.getElementById("composer"),
  composerDock: document.getElementById("composerDock"),
  btnConnect: document.getElementById("btnConnect"),
  btnOauth: document.getElementById("btnOauth"),
  btnClear: document.getElementById("btnClear"),
  btnSend: document.getElementById("btnSend"),
  chatBar: document.getElementById("chatBar"),
};

let messages = [];
let conversationEpoch = 0;
let keysByProvider = {};
let chatAbort = null;
let programmaticScroll = false;
let headerFadeTimer = 0;

function startNewConversation() {
  conversationEpoch += 1;
  if (chatAbort) {
    chatAbort.abort();
    chatAbort = null;
  }
  messages = [];
  if (els.thread) els.thread.innerHTML = "";
  setSending(false);
  updateComposerChrome();
}

function isCurrentConversation(epoch) {
  return epoch === conversationEpoch;
}

function setSending(on) {
  if (!els.btnSend) return;
  els.btnSend.classList.toggle("stop", on);
  els.btnSend.setAttribute("aria-label", on ? "中止" : "发送");
  if (on) {
    els.btnSend.innerHTML = '<span class="thinking-spinner" aria-hidden="true"></span>';
  } else {
    els.btnSend.textContent = "发送";
  }
}

function scrollThreadToBottom() {
  programmaticScroll = true;
  els.thread.scrollTop = els.thread.scrollHeight;
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      programmaticScroll = false;
    });
  });
}

function attachRipple() {
  document.addEventListener("pointerdown", (event) => {
    const btn = event.target.closest(".btn");
    if (!btn) return;
    const rect = btn.getBoundingClientRect();
    const size = Math.max(rect.width, rect.height) * 2.2;
    const ripple = document.createElement("span");
    ripple.className = "ripple";
    ripple.style.width = `${size}px`;
    ripple.style.height = `${size}px`;
    ripple.style.left = `${event.clientX - rect.left - size / 2}px`;
    ripple.style.top = `${event.clientY - rect.top - size / 2}px`;
    btn.appendChild(ripple);
    ripple.addEventListener("animationend", () => ripple.remove());
  });
}

function loadSettings() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
  } catch {
    return {};
  }
}

function currentProvider() {
  return PROVIDERS.find((p) => p.id === els.provider.value) || PROVIDERS[0];
}

function selectedModel() {
  if (currentProvider().id === "custom") {
    return els.openaiModel.value.trim();
  }
  return els.openaiModelSelect.value;
}

function saveSettings() {
  keysByProvider[els.provider.value] = els.openaiKey.value;
  localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify({
      mcpUrl: els.mcpUrl.value.trim(),
      provider: els.provider.value,
      openaiBase: els.openaiBase.value.trim(),
      openaiKey: els.openaiKey.value,
      openaiModel: selectedModel(),
      keysByProvider,
    })
  );
}

function enhanceSelect(select) {
  if (select.dataset.enhanced === "1") {
    refreshSelectMenu(select);
    return;
  }
  select.dataset.enhanced = "1";
  const wrap = document.createElement("div");
  wrap.className = "md-select";
  select.parentNode.insertBefore(wrap, select);
  wrap.appendChild(select);
  select.classList.add("md-select-native");
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "md-select-btn";
  const menu = document.createElement("div");
  menu.className = "md-select-menu";
  wrap.append(btn, menu);
  select._mdWrap = wrap;
  select._mdBtn = btn;
  select._mdMenu = menu;
  btn.addEventListener("click", (event) => {
    event.preventDefault();
    document.querySelectorAll(".md-select.open").forEach((el) => {
      if (el !== wrap) el.classList.remove("open");
    });
    wrap.classList.toggle("open");
  });
  menu.addEventListener("click", (event) => {
    const opt = event.target.closest(".md-select-option");
    if (!opt) return;
    select.value = opt.dataset.value;
    select.dispatchEvent(new Event("change", { bubbles: true }));
    wrap.classList.remove("open");
    refreshSelectMenu(select);
  });
  refreshSelectMenu(select);
}

function refreshSelectMenu(select) {
  if (!select._mdBtn) return;
  const current = select.options[select.selectedIndex];
  select._mdBtn.textContent = current ? current.text : "";
  select._mdMenu.innerHTML = [...select.options]
    .map(
      (opt) =>
        `<button type="button" class="md-select-option${opt.selected ? " selected" : ""}" data-value="${opt.value}">${opt.text}</button>`
    )
    .join("");
}

function fillProviderSelect() {
  els.provider.innerHTML = PROVIDERS.map(
    (p) => `<option value="${p.id}">${p.name}</option>`
  ).join("");
  enhanceSelect(els.provider);
}

function fillModelSelect(provider, savedModel) {
  const models = provider.models || [];
  els.openaiModelSelect.innerHTML = models.map((m) => `<option value="${m}">${m}</option>`).join("");
  if (savedModel && models.includes(savedModel)) {
    els.openaiModelSelect.value = savedModel;
  } else if (models.length) {
    els.openaiModelSelect.value = models[0];
  }
  syncModelFields();
  refreshSelectMenu(els.openaiModelSelect);
}

function syncModelFields() {
  const custom = currentProvider().id === "custom";
  els.modelSelectWrap.classList.toggle("field-hidden", custom);
  els.modelSelectWrap.hidden = custom;
  els.customModelWrap.classList.toggle("field-hidden", !custom);
  els.customModelWrap.hidden = !custom;
}

function applyProvider(provider, { keepBase = false, savedModel = "" } = {}) {
  els.providerHint.textContent = provider.hint;
  els.openaiKey.placeholder = provider.keyHint;
  if (provider.id === "custom") {
    if (!keepBase) els.openaiBase.value = "";
    els.openaiBase.placeholder = "https://your-gateway/v1";
  } else if (!keepBase && provider.base) {
    els.openaiBase.value = provider.base;
    els.openaiBase.placeholder = "由厂商自动填入，可改";
  }
  fillModelSelect(provider, savedModel);
  enhanceSelect(els.provider);
  enhanceSelect(els.openaiModelSelect);
  refreshSelectMenu(els.provider);
  refreshSelectMenu(els.openaiModelSelect);
  syncModelFields();
  const storedKey = keysByProvider[provider.id];
  if (typeof storedKey === "string") {
    els.openaiKey.value = storedKey;
  }
}

function setStatus(text, kind) {
  els.mcpStatus.textContent = text;
  els.mcpStatus.className = `status ${kind}`;
}

function addMessage(role, text, extraClass) {
  const node = document.createElement("div");
  node.className = `msg ${role}${extraClass ? " " + extraClass : ""}`;
  if (role === "assistant") {
    node.classList.add("markdown");
    node.innerHTML = renderMarkdown(text || "");
  } else {
    node.textContent = text;
  }
  els.thread.appendChild(node);
  scrollThreadToBottom();
  updateComposerChrome();
  return node;
}

function escapeHtml(text) {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function inlineMarkdown(text) {
  let html = escapeHtml(text);
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/__([^_]+)__/g, "<strong>$1</strong>");
  html = html.replace(/(^|[^*])\*([^*]+)\*(?!\*)/g, "$1<em>$2</em>");
  html = html.replace(/(^|[^_])_([^_]+)_(?!_)/g, "$1<em>$2</em>");
  html = html.replace(/\[([^\]]+)\]\((https?:[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>');
  html = html.replace(/https:\/\/[^\s<]+/g, (url, offset, str) => {
    const before = str.slice(Math.max(0, offset - 6), offset);
    if (before.endsWith("href=") || before.endsWith('="') || before.endsWith("='")) {
      return url;
    }
    const cleaned = url.replace(/[),.;:，。；：]+$/, "");
    const trail = url.slice(cleaned.length);
    return `<a href="${cleaned}" target="_blank" rel="noreferrer">${cleaned}</a>${trail}`;
  });
  return html;
}

function isTableRow(line) {
  return /^\s*\|.*\|\s*$/.test(line);
}

function isTableSep(line) {
  return /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?\s*$/.test(line);
}

function splitCells(line) {
  return line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|\s*$/, "")
    .split("|")
    .map((cell) => cell.trim());
}

function renderTable(rows) {
  const body = rows.filter((row) => !isTableSep(row.join("|")));
  if (!body.length) return "";
  const head = body[0];
  const rest = body.slice(1);
  const thead = `<thead><tr>${head.map((c) => `<th>${inlineMarkdown(c)}</th>`).join("")}</tr></thead>`;
  const tbody = `<tbody>${rest
    .map((row) => `<tr>${row.map((c) => `<td>${inlineMarkdown(c)}</td>`).join("")}</tr>`)
    .join("")}</tbody>`;
  return `<div class="table-wrap"><table>${thead}${tbody}</table></div>`;
}

function renderMarkdown(src) {
  const text = (src || "").replace(/\r\n/g, "\n");
  const fences = [];
  const withFences = text.replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) => {
    const i = fences.length;
    fences.push(
      `<pre><code class="lang-${escapeHtml(lang)}">${escapeHtml(code.replace(/\n$/, ""))}</code></pre>`
    );
    return `\n%%FENCE${i}%%\n`;
  });
  const lines = withFences.split("\n");
  const out = [];
  let listType = null;

  const closeList = () => {
    if (listType) {
      out.push(listType === "ol" ? "</ol>" : "</ul>");
      listType = null;
    }
  };

  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];
    const fence = line.match(/^%%FENCE(\d+)%%$/);
    if (fence) {
      closeList();
      out.push(fences[Number(fence[1])]);
      continue;
    }
    if (isTableRow(line) && i + 1 < lines.length && isTableSep(lines[i + 1])) {
      closeList();
      const rows = [];
      while (i < lines.length && (isTableRow(lines[i]) || isTableSep(lines[i]))) {
        if (!isTableSep(lines[i])) rows.push(splitCells(lines[i]));
        i += 1;
      }
      i -= 1;
      out.push(renderTable(rows));
      continue;
    }
    if (/^---+$/.test(line.trim())) {
      closeList();
      out.push("<hr>");
      continue;
    }
    const heading = line.match(/^(#{1,6})\s+(.+)$/);
    if (heading) {
      closeList();
      const level = heading[1].length;
      out.push(`<h${level}>${inlineMarkdown(heading[2])}</h${level}>`);
      continue;
    }
    const quote = line.match(/^>\s?(.*)$/);
    if (quote) {
      closeList();
      out.push(`<blockquote>${inlineMarkdown(quote[1])}</blockquote>`);
      continue;
    }
    const ol = line.match(/^\d+\.\s+(.+)$/);
    if (ol) {
      if (listType !== "ol") {
        closeList();
        listType = "ol";
        out.push("<ol>");
      }
      out.push(`<li>${inlineMarkdown(ol[1])}</li>`);
      continue;
    }
    const ul = line.match(/^[-*]\s+(.+)$/);
    if (ul) {
      if (listType !== "ul") {
        closeList();
        listType = "ul";
        out.push("<ul>");
      }
      out.push(`<li>${inlineMarkdown(ul[1])}</li>`);
      continue;
    }
    closeList();
    if (!line.trim()) {
      continue;
    }
    out.push(`<p>${inlineMarkdown(line)}</p>`);
  }
  closeList();
  return out.join("") || "<p></p>";
}

function errorText(data) {
  const d = data.detail || data.error || data.message;
  if (Array.isArray(d)) return d.map((x) => x.msg || JSON.stringify(x)).join("; ");
  return d || "请求失败";
}

function payload() {
  return {
    mcp_url: els.mcpUrl.value.trim(),
    mcp_api_key: els.mcpKey.value.trim(),
    openai_base_url: els.openaiBase.value.trim(),
    openai_api_key: els.openaiKey.value.trim(),
    openai_model: selectedModel(),
    provider: els.provider.value,
  };
}

async function connect() {
  saveSettings();
  setStatus("正在通过本机网络连接 MCP…", "busy");
  try {
    const res = await fetch("/api/mcp/connect", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload()),
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(errorText(data));
    }
    setStatus("知识库已连接", "ok");
  } catch (err) {
    setStatus(err.message, "bad");
    throw err;
  }
}

async function sendChat(text, signal, epoch) {
  messages.push({ role: "user", content: text });
  addMessage("user", text);
  const thinkingChip = document.createElement("div");
  thinkingChip.className = "thinking-chip";
  thinkingChip.innerHTML = '<span class="thinking-spinner" aria-hidden="true"></span><span>思考中...</span>';
  els.thread.appendChild(thinkingChip);
  scrollThreadToBottom();
  let assistant = null;

  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...payload(), messages }),
    signal,
  });
  if (!isCurrentConversation(epoch)) return;
  if (!res.ok || !res.body) {
    thinkingChip.remove();
    const data = await res.json().catch(() => ({}));
    throw new Error(errorText(data));
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let full = "";

  const showAssistant = () => {
    if (assistant) return;
    thinkingChip.remove();
    assistant = addMessage("assistant", "");
  };

  try {
    while (true) {
      if (!isCurrentConversation(epoch)) return;
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const chunks = buffer.split("\n\n");
      buffer = chunks.pop() || "";
      for (const chunk of chunks) {
        const line = chunk.split("\n").find((l) => l.startsWith("data:"));
        if (!line) continue;
        let event;
        try {
          event = JSON.parse(line.slice(5).trim());
        } catch {
          continue;
        }
        if (event.type === "thinking") {
          thinkingChip.style.display = "flex";
        } else if (event.type === "delta") {
          showAssistant();
          full += event.text;
          assistant.innerHTML = renderMarkdown(full);
        } else if (event.type === "error") {
          thinkingChip.remove();
          throw new Error(event.message);
        } else if (event.type === "mcp_ready") {
          setStatus("知识库已连接", "ok");
        }
        scrollThreadToBottom();
      }
    }
  } catch (err) {
    if (!isCurrentConversation(epoch)) return;
    thinkingChip.remove();
    if (full) {
      messages.push({ role: "assistant", content: full });
    }
    throw err;
  }

  if (!isCurrentConversation(epoch)) return;
  thinkingChip.remove();
  if (!full) {
    addMessage("assistant", "（模型没有返回文本）");
  } else if (assistant) {
    assistant.innerHTML = renderMarkdown(full);
  }
  messages.push({ role: "assistant", content: full });
}

function updateComposerChrome() {
  const thread = els.thread;
  if (!thread || !els.form) return;
  const scrolledUp = thread.scrollHeight - thread.scrollTop - thread.clientHeight > 32;
  if (els.composerDock) els.composerDock.classList.toggle("ghost", scrolledUp);
}

function onThreadScroll() {
  updateComposerChrome();
  if (programmaticScroll || !els.chatBar) return;
  els.chatBar.classList.add("dimmed");
  clearTimeout(headerFadeTimer);
  headerFadeTimer = setTimeout(() => {
    els.chatBar.classList.remove("dimmed");
  }, 500);
}

function boot() {
  attachRipple();
  els.thread.addEventListener("scroll", onThreadScroll, { passive: true });
  updateComposerChrome();
  document.addEventListener("click", (event) => {
    if (!event.target.closest(".md-select")) {
      document.querySelectorAll(".md-select.open").forEach((el) => el.classList.remove("open"));
    }
  });
  const saved = loadSettings();
  keysByProvider = saved.keysByProvider || {};
  fillProviderSelect();

  const remembered = saved.mcpUrl || "";
  els.mcpUrl.value = remembered.includes("getoutline.com") ? "" : remembered;

  const providerId = PROVIDERS.some((p) => p.id === saved.provider) ? saved.provider : "openai";
  els.provider.value = providerId;
  if (saved.openaiKey && !keysByProvider[providerId]) {
    keysByProvider[providerId] = saved.openaiKey;
  }
  els.openaiBase.value = saved.openaiBase || "";
  applyProvider(currentProvider(), {
    keepBase: Boolean(saved.openaiBase),
    savedModel: saved.openaiModel || "",
  });
  if (saved.openaiModel) {
    els.openaiModel.value = saved.openaiModel;
  }

  window.addEventListener("message", (event) => {
    if (event.origin !== location.origin) return;
    const data = event.data || {};
    if (data.type !== "outline-oauth") return;
    if (data.status === "ok") {
      setStatus("企业登录成功，正在测试连接…", "ok");
      connect().catch(() => {});
      return;
    }
    const map = {
      missing_url: "请先填写企业 Outline 地址",
      start: "无法打开企业登录：" + (data.message || ""),
      missing: "登录未完成",
      state: "登录校验失败，请再试一次",
      token: "登录换票失败：" + (data.message || ""),
    };
    setStatus(map[data.status] || "登录未完成", "bad");
  });

  fetch("/api/defaults")
    .then((r) => r.json())
    .then((d) => {
      if (!els.mcpUrl.value && d.mcp_url && !String(d.mcp_url).includes("getoutline.com")) {
        els.mcpUrl.value = d.mcp_url;
      }
      if (d.oauth_connected) setStatus("已有企业登录会话，可点测试连接", "ok");
    })
    .catch(() => {});

  els.provider.addEventListener("change", () => {
    applyProvider(currentProvider());
    saveSettings();
  });
  els.openaiModelSelect.addEventListener("change", () => {
    saveSettings();
  });

  els.btnOauth.addEventListener("click", (e) => {
    e.preventDefault();
    saveSettings();
    const mcpUrl = els.mcpUrl.value.trim();
    if (!mcpUrl) {
      setStatus("请先填写企业 Outline / MCP 地址", "bad");
      els.mcpUrl.focus();
      return;
    }
    if (mcpUrl.includes("getoutline.com")) {
      setStatus("请改成你们自己的知识库地址，不要使用 getoutline.com", "bad");
      return;
    }
    const url = new URL("/api/mcp/oauth/start", location.origin);
    url.searchParams.set("mcp_url", mcpUrl);
    const popup = window.open(
      url.toString(),
      "outline-oauth",
      "popup=yes,width=520,height=740,menubar=no,toolbar=no,status=no"
    );
    if (!popup) {
      setStatus("浏览器拦截了登录弹窗，请允许本站弹出窗口后重试", "bad");
      return;
    }
    setStatus("请在弹出窗口中用企业账号密码登录…", "busy");
    popup.focus();
    const timer = setInterval(() => {
      if (!popup.closed) return;
      clearInterval(timer);
      fetch("/api/defaults")
        .then((r) => r.json())
        .then((d) => {
          if (d.oauth_connected) {
            setStatus("企业登录成功，正在测试连接…", "ok");
            return connect();
          }
        })
        .catch(() => {});
    }, 600);
  });

  els.btnConnect.addEventListener("click", () => connect().catch(() => {}));
  els.btnClear.addEventListener("click", () => {
    startNewConversation();
  });
  ["mcpUrl", "openaiBase", "openaiKey", "openaiModel"].forEach((id) => {
    document.getElementById(id).addEventListener("change", saveSettings);
  });

  els.form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (chatAbort) {
      chatAbort.abort();
      return;
    }
    const text = els.input.value.trim();
    if (!text) return;
    els.input.value = "";
    saveSettings();
    chatAbort = new AbortController();
    const epoch = conversationEpoch;
    setSending(true);
    try {
      await sendChat(text, chatAbort.signal, epoch);
    } catch (err) {
      if (!isCurrentConversation(epoch)) return;
      if (err.name === "AbortError") {
        addMessage("error", "已中止当前回复", "error");
      } else {
        addMessage("error", err.message, "error");
      }
    } finally {
      if (!isCurrentConversation(epoch)) return;
      chatAbort = null;
      setSending(false);
    }
  });

  els.input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      els.form.requestSubmit();
    }
  });
}

boot();
