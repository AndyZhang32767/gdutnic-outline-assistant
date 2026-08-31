# Outline 查询助手

本机运行的知识库问答助手：通过企业 Outline 的 MCP 检索文档，再用兼容 OpenAI 的模型接口生成回答。界面在浏览器里打开，登录走弹出窗口（OAuth）。

## 运行环境

- Python 3.10+（建议 3.12）
- 能访问你们自己的 Outline 知识库（不要用 getoutline.com）
- 任意一家兼容 OpenAI Chat Completions 的模型 Key

## 启动

本机或局域网访问：<http://127.0.0.1:8787> 或 `http://本机IP:8787`。  
企业登录必须用 **127.0.0.1**（不要用 `localhost`），否则 OAuth 回调可能失败。从其他电脑用 IP 访问时，需要在 Outline 侧允许对应回调地址。

**Windows**

```bat
start.bat
```

**Linux / macOS**

```bash
chmod +x start.sh
./start.sh
```

也可手动：

```bash
python3 -m pip install -r requirements.txt
python3 -m uvicorn server.app:app --host 0.0.0.0 --port 8787
```

服务默认监听 `0.0.0.0:8787`。只想本机访问时，把 `--host` 改成 `127.0.0.1`。局域网访问若被拦截，请在系统防火墙放行 8787。

## 使用

1. 填写企业 Outline / MCP 地址（例如 `https://知识库域名` 或 `.../mcp`）。
2. 点「企业登录」，在弹出窗口用企业账号登录。也可选填 Outline API Key。
3. 选模型厂商、填 API Key、选模型（「自定义」厂商需自己填 Base URL 和模型名称）。
4. 在右侧提问。生成中可点发送键上的加载动画中止。

## 会话和密钥存在哪里

本仓库**不保存**你的对话内容、Outline Token、模型 Key。运行后会产生仅限本机的数据，且已被 `.gitignore` 排除。

| 存什么 | 位置 | 说明 |
| --- | --- | --- |
| 登录态、Outline Token、可选的 MCP API Key | **浏览器 Cookie**（Starlette 签名会话，默认 cookie 名 `session`） | 存在**访问者自己的浏览器**里，随请求发给本机服务。不是数据库，也不是 Git。 |
| Cookie 签名密钥 | `data/session_secret.txt`，或环境变量 `SESSION_SECRET` | 只用来给 Cookie 签名，防止被改。删掉后已登录用户需要重新登录。 |
| Outline OAuth 动态注册的 client | `data/oauth_client.json` | 本机向知识库登记的 OAuth 客户端，不要提交。 |
| 厂商、Base URL、**模型 API Key**、MCP 地址 | 浏览器 **localStorage**，键名 `gdutnic-outline-assistant` | 只在该浏览器本机保存，方便下次自动填表。公共电脑请用完清站点数据。 |
| 当前对话消息 | 仅内存（页面里的 JS 数组） | 刷新或点「清空对话」即丢弃，不写磁盘。 |

`data/` 整个目录不要提交。公开仓库前请确认没有把 `.env`、密钥文件加进去。

## 项目结构

```
server/     FastAPI、MCP、OAuth、对话流
web/        静态页面
icon/       站点图标（可选，缺少时无 favicon）
start.bat   Windows 启动
start.sh    Linux / macOS 启动
```

## 安全注意

- 绑在 `0.0.0.0` 时，能访问该 IP:8787 的人都能打开界面；知识库仍需各自完成 OAuth。
- 公网暴露前应使用 HTTPS，并把会话改为 `https_only`。
- 不要把 `data/`、`.env`、真实 API Key 推送到 Git。
