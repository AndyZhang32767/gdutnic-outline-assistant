const ICON_FILES = {
  compose: "/icon/symbol/new_window_24dp_1F1F1F_FILL0_wght400_GRAD0_opsz24.svg",
  close: "/icon/symbol/close_24dp_1F1F1F_FILL0_wght400_GRAD0_opsz24.svg",
  send: "/icon/symbol/send_24dp_1F1F1F_FILL0_wght400_GRAD0_opsz24.svg",
  stop: "/icon/symbol/stop_24dp_1F1F1F_FILL0_wght400_GRAD0_opsz24.svg",
  user: "/icon/symbol/user_24dp_1F1F1F_FILL0_wght400_GRAD0_opsz24.svg",
  server: "/icon/symbol/server_24dp_1F1F1F_FILL0_wght400_GRAD0_opsz24.svg",
};

function mdIcon(name) {
  return `<span class="md-icon" style="--md-icon:url('${ICON_FILES[name]}')" aria-hidden="true"></span>`;
}

const ICON = {
  compose: mdIcon("compose"),
  close: mdIcon("close"),
  send: mdIcon("send"),
  stop: mdIcon("stop"),
};
const HISTORY_KEY = "gdutnic-chat-history";
const AUTH_KEY = "gdutnic-wiki-auth";

const els = {
  wikiGate: document.getElementById("wikiGate"),
  app: document.getElementById("app"),
  gateStatus: document.getElementById("gateStatus"),
  historyList: document.getElementById("historyList"),
  thread: document.getElementById("thread"),
  input: document.getElementById("input"),
  form: document.getElementById("composer"),
  composerDock: document.getElementById("composerDock"),
  btnOauth: document.getElementById("btnOauth"),
  btnNewSession: document.getElementById("btnNewSession"),
  btnLogout: document.getElementById("btnLogout"),
  btnSend: document.getElementById("btnSend"),
  chatBar: document.getElementById("chatBar"),
  chatTitle: document.getElementById("chatTitle"),
};

let messages = [];
let programmaticScroll = false;
let headerFadeTimer = 0;
let currentId = null;
let sessions = [];
const inflight = new Map();

function newId() {
  return crypto.randomUUID();
}

function loadAuth() {
  try {
    return JSON.parse(localStorage.getItem(AUTH_KEY) || "null");
  } catch {
    return null;
  }
}

function saveAuth(data) {
  const access = (data?.access_token || "").trim();
  if (!access) return;
  localStorage.setItem(
    AUTH_KEY,
    JSON.stringify({
      access_token: access,
      refresh_token: data.refresh_token || "",
      mcp_url: data.mcp_url || "",
    })
  );
}

function authScope() {
  const token = loadAuth()?.access_token || "";
  let h = 0;
  for (let i = 0; i < token.length; i += 1) {
    h = (Math.imul(31, h) + token.charCodeAt(i)) | 0;
  }
  return String(h);
}

function historyStorageKey() {
  return `${HISTORY_KEY}:${authScope()}`;
}

const THEME_COOKIE = "gdutnic_themes";
let saveChatsTimer = 0;

function readThemeCookie() {
  const hit = document.cookie.split("; ").find((row) => xStarts(row, THEME_COOKIE + "="));
  if (!hit) return {};
  try {
    const parsed = JSON.parse(decodeURIComponent(hit.slice(THEME_COOKIE.length + 1)));
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function xStarts(row, prefix) {
  return row.startsWith(prefix);
}

function writeThemeCookie(map) {
  document.cookie = `${THEME_COOKIE}=${encodeURIComponent(JSON.stringify(map))}; Path=/; Max-Age=${60 * 60 * 24 * 30}; SameSite=Lax`;
}

function themeIndex(theme) {
  const i = USER_THEMES.findIndex((t) => t.bg === theme.bg && t.ink === theme.ink);
  return i >= 0 ? i : 0;
}

function themeFromCookie(id) {
  const idx = readThemeCookie()[id];
  if (Number.isInteger(idx) && USER_THEMES[idx]) return { ...USER_THEMES[idx] };
  return null;
}

function rememberThemeCookie(id, theme) {
  if (!id || !theme) return;
  const map = readThemeCookie();
  map[id] = themeIndex(theme);
  writeThemeCookie(map);
}

async function loadHistoryStore() {
  try {
    const res = await fetch("/api/chats");
    const packed = await res.json();
    if (res.ok && Array.isArray(packed.sessions)) {
      sessions = packed.sessions;
      currentId = packed.currentId || null;
      if (sessions.length) return;
    }
  } catch {
    /* fall through */
  }
  try {
    const scoped = JSON.parse(localStorage.getItem(historyStorageKey()) || "null");
    if (scoped && Array.isArray(scoped.sessions) && scoped.sessions.length) {
      sessions = scoped.sessions;
      currentId = scoped.currentId || null;
      persistHistoryStore();
      return;
    }
    const legacy = JSON.parse(localStorage.getItem(HISTORY_KEY) || "{}");
    sessions = Array.isArray(legacy.sessions) ? legacy.sessions : [];
    currentId = legacy.currentId || null;
  } catch {
    sessions = [];
    currentId = null;
  }
}

function persistHistoryStore(immediate) {
  sessions.forEach((s) => {
    if (s.userTheme) rememberThemeCookie(s.id, s.userTheme);
  });
  const push = () =>
    fetch("/api/chats", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ currentId, sessions }),
    }).catch(() => {});
  clearTimeout(saveChatsTimer);
  if (immediate === false) {
    saveChatsTimer = setTimeout(push, 280);
    return;
  }
  push();
}

function sessionTitleFrom(msgs) {
  const first = (msgs || []).find((m) => m.role === "user");
  const text = String(first?.content || "新会话").replace(/\s+/g, " ").trim();
  return text.slice(0, 36) || "新会话";
}

const USER_THEMES = [
  { bg: "#D1E4FF", ink: "#001D33" },
  { bg: "#DCF8C6", ink: "#102008" },
  { bg: "#FFDCC8", ink: "#311300" },
  { bg: "#E8DEF8", ink: "#1D192B" },
  { bg: "#E6E1E5", ink: "#1C1B1F" },
];

function pickUserTheme() {
  return USER_THEMES[Math.floor(Math.random() * USER_THEMES.length)];
}

function applyUserChatTheme(theme) {
  const t = theme && theme.bg && theme.ink ? theme : pickUserTheme();
  document.documentElement.style.setProperty("--user-bubble", t.bg);
  document.documentElement.style.setProperty("--user-ink", t.ink);
}

function sortSessions() {
  sessions.sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0));
}

function ensureSession(id) {
  let rec = sessions.find((s) => s.id === id);
  if (!rec) {
    rec = { id, title: "新会话", messages: [], updatedAt: 0 };
    sessions.push(rec);
  }
  if (!Array.isArray(rec.messages)) rec.messages = [];
  const fromCookie = themeFromCookie(id);
  if (fromCookie) {
    rec.userTheme = fromCookie;
  } else if (!rec.userTheme || !rec.userTheme.bg || !rec.userTheme.ink) {
    rec.userTheme = pickUserTheme();
  }
  rememberThemeCookie(id, rec.userTheme);
  return rec;
}

function bindCurrent(id) {
  const rec = ensureSession(id);
  currentId = id;
  messages = rec.messages;
  applyUserChatTheme(rec.userTheme);
  persistHistoryStore();
  syncHistoryActive();
  renderThreadFromMessages();
  setSending(inflight.has(id));
}

function syncHistoryActive() {
  if (!els.historyList) return;
  const items = els.historyList.querySelectorAll(".history-item");
  if (!items.length) {
    renderHistory();
    return;
  }
  items.forEach((el) => {
    el.classList.toggle("active", el.dataset.id === currentId);
  });
  updateChatTitle();
}

function markRound(id) {
  const rec = ensureSession(id);
  rec.title = sessionTitleFrom(rec.messages);
  rec.updatedAt = Date.now();
  sortSessions();
  persistHistoryStore();
  renderHistory();
}

function updateChatTitle() {
  if (!els.chatTitle) return;
  const rec = sessions.find((s) => s.id === currentId);
  els.chatTitle.textContent = rec?.title || "新会话";
}

function renderHistory() {
  if (!els.historyList) return;
  const saved = [...sessions]
    .filter((s) => (s.messages || []).length)
    .sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0));
  if (!saved.length) {
    els.historyList.innerHTML = '<p class="history-empty">暂无历史会话</p>';
    updateChatTitle();
    return;
  }
  els.historyList.innerHTML = saved
    .map(
      (s) =>
        `<div class="history-item${s.id === currentId ? " active" : ""}" data-id="${s.id}">` +
        `<button type="button" class="history-open" data-id="${s.id}">${escapeHtml(s.title || "新会话")}</button>` +
        `<button type="button" class="history-del" data-del="${s.id}" title="删除" aria-label="删除">${ICON.close}</button>` +
        `</div>`
    )
    .join("");
  updateChatTitle();
}

function renderThreadFromMessages() {
  if (!els.thread) return;
  els.thread.innerHTML = "";
  for (const m of messages) {
    if (m.role !== "user" && m.role !== "assistant") continue;
    addMessage(m.role, m.content, "", { scroll: false });
  }
  if (inflight.has(currentId)) {
    const last = messages[messages.length - 1];
    if (!last || last.role !== "assistant") {
      const thinkingChip = document.createElement("div");
      thinkingChip.className = "thinking-chip";
      thinkingChip.dataset.thinking = currentId;
      thinkingChip.innerHTML = '<span class="thinking-spinner" aria-hidden="true"></span><span>思考中...</span>';
      els.thread.appendChild(thinkingChip);
    }
  }
  scrollThreadToBottom();
  updateComposerChrome();
}

function startNewConversation() {
  if (!messages.length && !inflight.has(currentId)) {
    if (!currentId) currentId = newId();
    persistHistoryStore();
    renderHistory();
    renderThreadFromMessages();
    return;
  }
  bindCurrent(newId());
}

function openSession(id) {
  if (!id || id === currentId) return;
  bindCurrent(id);
}

function deleteSession(id) {
  const ctrl = inflight.get(id);
  if (ctrl) ctrl.abort();
  sessions = sessions.filter((s) => s.id !== id);
  if (currentId === id) {
    bindCurrent(newId());
    return;
  }
  persistHistoryStore();
  renderHistory();
}

function setSending(on) {
  if (!els.btnSend) return;
  els.btnSend.classList.toggle("stop", on);
  els.btnSend.setAttribute("aria-label", on ? "中止" : "发送");
  if (on) {
    els.btnSend.innerHTML = ICON.stop;
  } else {
    els.btnSend.innerHTML = ICON.send;
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
    const capsule = event.target.closest(".history-item");
    const btn = capsule || event.target.closest(".btn");
    if (!btn || btn.classList.contains("send")) return;
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

function setStatus(text, kind) {
  if (els.gateStatus && !document.body.classList.contains("wiki-ready")) {
    els.gateStatus.textContent = text;
    els.gateStatus.className = `hint status-text ${kind || ""}`;
  }
}

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function clearAuth() {
  localStorage.removeItem(AUTH_KEY);
}

async function logoutWiki() {
  try {
    await fetch("/api/mcp/logout", { method: "POST" });
  } catch {
    /* still leave locally */
  }
  clearAuth();
  inflight.forEach((ctrl) => ctrl.abort());
  inflight.clear();
  setSending(false);
  showGate();
  setStatus("", "idle");
}

function showGate() {
  document.body.classList.remove("wiki-ready");
  if (els.app) {
    els.app.hidden = true;
    els.app.classList.add("field-hidden");
  }
  if (els.wikiGate) {
    els.wikiGate.hidden = false;
    els.wikiGate.classList.remove("is-leaving");
  }
}

async function showApp() {
  if (els.wikiGate && !els.wikiGate.hidden) {
    els.wikiGate.classList.add("is-leaving");
    await wait(260);
    els.wikiGate.hidden = true;
    els.wikiGate.classList.remove("is-leaving");
  }
  document.body.classList.add("wiki-ready");
  if (els.app) {
    els.app.hidden = false;
    els.app.classList.remove("field-hidden");
  }
  updateComposerChrome();
}

function addMessage(role, text, extraClass, opts) {
  const bubble = document.createElement("div");
  bubble.className = `msg ${role}${extraClass ? " " + extraClass : ""}`;
  if (role === "assistant") {
    bubble.classList.add("markdown");
    bubble.innerHTML = renderMarkdown(text || "");
  } else {
    bubble.textContent = text;
  }
  if (role === "user" || role === "assistant") {
    const row = document.createElement("div");
    row.className = `msg-row ${role}`;
    const avatar = document.createElement("span");
    avatar.className = "msg-avatar";
    avatar.setAttribute("aria-hidden", "true");
    const icon = document.createElement("span");
    icon.className = "md-icon";
    icon.style.setProperty("--md-icon", `url('${ICON_FILES[role === "user" ? "user" : "server"]}')`);
    avatar.appendChild(icon);
    if (role === "user") {
      row.append(bubble, avatar);
    } else {
      row.append(avatar, bubble);
    }
    els.thread.appendChild(row);
  } else {
    els.thread.appendChild(bubble);
  }
  if (!opts || opts.scroll !== false) {
    scrollThreadToBottom();
    updateComposerChrome();
  }
  return bubble;
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
  const token = (loadAuth()?.access_token || "").trim();
  return token ? { mcp_api_key: token } : {};
}

async function restoreServerSession() {
  const auth = loadAuth();
  if (!auth?.access_token) return false;
  try {
    const res = await fetch("/api/mcp/restore", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        outline_token: auth.access_token,
        outline_refresh: auth.refresh_token || "",
        mcp_url: auth.mcp_url || "",
      }),
    });
    return res.ok;
  } catch {
    return false;
  }
}

async function applyLogin(data) {
  if (data?.access_token) saveAuth(data);
  await restoreServerSession();
  await loadHistoryStore();
  if (!currentId) currentId = newId();
  bindCurrent(currentId);
}

async function connect() {
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

async function sendChat(text, sessionId, signal) {
  const rec = ensureSession(sessionId);
  rec.messages.push({ role: "user", content: text });
  markRound(sessionId);
  if (currentId === sessionId) addMessage("user", text);

  let thinkingChip = null;
  if (currentId === sessionId) {
    thinkingChip = document.createElement("div");
    thinkingChip.className = "thinking-chip";
    thinkingChip.dataset.thinking = sessionId;
    thinkingChip.innerHTML = '<span class="thinking-spinner" aria-hidden="true"></span><span>思考中...</span>';
    els.thread.appendChild(thinkingChip);
    scrollThreadToBottom();
  }

  const snapshot = rec.messages
    .filter((m) => m.role === "user" || m.role === "assistant")
    .map((m) => ({ role: m.role, content: m.content }));
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...payload(), messages: snapshot }),
    signal,
  });
  if (!res.ok || !res.body) {
    thinkingChip?.remove();
    const data = await res.json().catch(() => ({}));
    throw new Error(errorText(data));
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let full = "";
  let assistant = null;

  const showAssistant = () => {
    if (currentId !== sessionId) return;
    const chip = els.thread.querySelector("[data-thinking]");
    if (chip) chip.remove();
    if (assistant && assistant.isConnected) return;
    assistant = addMessage("assistant", "");
    assistant.dataset.stream = sessionId;
  };

  const writeAssistant = (textValue) => {
    const row = ensureSession(sessionId);
    const last = row.messages[row.messages.length - 1];
    if (last && last.role === "assistant") last.content = textValue;
    else row.messages.push({ role: "assistant", content: textValue });
    persistHistoryStore(false);
    if (currentId === sessionId) {
      showAssistant();
      if (assistant) assistant.innerHTML = renderMarkdown(textValue);
      scrollThreadToBottom();
    }
  };

  try {
    while (true) {
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
          if (currentId === sessionId) {
            const chip = els.thread.querySelector("[data-thinking]");
            if (chip) chip.style.display = "flex";
          }
        } else if (event.type === "delta") {
          full += event.text;
          writeAssistant(full);
        } else if (event.type === "error") {
          throw new Error(event.message);
        }
      }
    }
  } catch (err) {
    if (full) writeAssistant(full);
    throw err;
  }

  if (!full) {
    const fallback = "（模型没有返回文本）";
    writeAssistant(fallback);
  } else {
    writeAssistant(full);
  }
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

function startOauth() {
  const popup = window.open(
    "/api/mcp/oauth/start",
    "outline-oauth",
    "width=520,height=740,menubar=no,toolbar=no,status=no"
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
        if (d.oauth_connected || d.has_outline_token || loadAuth()?.access_token) {
          setStatus("企业登录成功，正在连接知识库…", "ok");
          return applyLogin(d).then(() => connect()).then(() => showApp());
        }
        if (!document.body.classList.contains("wiki-ready")) {
          setStatus("登录未完成，请再试一次", "bad");
        }
      })
      .catch(() => {
        setStatus("无法确认登录状态，请再试一次", "bad");
      });
  }, 600);
}

async function boot() {
  attachRipple();
  await restoreServerSession();
  await loadHistoryStore();
  if (!currentId) currentId = newId();
  bindCurrent(currentId);
  els.thread.addEventListener("scroll", onThreadScroll, { passive: true });
  updateComposerChrome();

  window.addEventListener("message", (event) => {
    if (event.origin !== location.origin) return;
    const data = event.data || {};
    if (data.type !== "outline-oauth") return;
    if (data.status === "ok") {
      setStatus("企业登录成功，正在连接知识库…", "ok");
      applyLogin(data)
        .then(() => connect())
        .then(() => showApp())
        .catch((err) => {
          setStatus(err.message || "连接知识库失败", "bad");
        });
      return;
    }
    const map = {
      missing_url: "请先在管理员界面填写网协 MCP 地址",
      start: "无法打开企业登录：" + (data.message || ""),
      missing: "登录未完成",
      state: "登录校验失败，请再试一次",
      token: "登录换票失败：" + (data.message || ""),
    };
    setStatus(map[data.status] || "登录未完成", "bad");
  });

  try {
    const res = await fetch("/api/defaults");
    const d = await res.json();
    if (!d.mcp_url) {
      showGate();
      setStatus("请先在管理员界面填写网协 MCP 地址", "idle");
    } else if (d.oauth_connected || d.has_outline_token || loadAuth()?.access_token) {
      try {
        await applyLogin(d);
        await connect();
        await showApp();
      } catch (err) {
        showGate();
        setStatus(err.message || "知识库未连接，请重新登录", "bad");
      }
    } else {
      showGate();
    }
  } catch {
    showGate();
  }

  els.btnOauth.addEventListener("click", (e) => {
    e.preventDefault();
    startOauth();
  });

  els.btnNewSession.addEventListener("click", () => {
    startNewConversation();
  });

  if (els.btnLogout) {
    els.btnLogout.addEventListener("click", () => {
      logoutWiki();
    });
  }

  els.historyList.addEventListener("click", (e) => {
    const del = e.target.closest("[data-del]");
    if (del) {
      e.preventDefault();
      e.stopPropagation();
      deleteSession(del.getAttribute("data-del"));
      return;
    }
    const item = e.target.closest(".history-item");
    if (item) openSession(item.getAttribute("data-id"));
  });

  els.form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!currentId) bindCurrent(newId());
    const sessionId = currentId;
    const running = inflight.get(sessionId);
    if (running) {
      running.abort();
      return;
    }
    const text = els.input.value.trim();
    if (!text) return;
    els.input.value = "";
    const ctrl = new AbortController();
    inflight.set(sessionId, ctrl);
    setSending(true);
    try {
      await sendChat(text, sessionId, ctrl.signal);
    } catch (err) {
      if (currentId !== sessionId) return;
      if (err.name === "AbortError") {
        addMessage("error", "已中止当前回复", "error");
      } else {
        addMessage("error", err.message, "error");
      }
    } finally {
      inflight.delete(sessionId);
      if (currentId === sessionId) setSending(false);
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
