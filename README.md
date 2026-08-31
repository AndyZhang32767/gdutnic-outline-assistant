# 网协 Wiki 查询助手

给泥工网协做的 Wiki Agent, 通过 MCP 检索文档，再用兼容 OpenAI 的模型接口生成回答。界面在浏览器里打开，登录走弹出窗口（OAuth）。

## 运行环境

- Python 3.10+（建议 3.12）
- 能访问网协wiki的 Outline 知识库
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

1. 填写网协 Outline / MCP 地址（例如 `https://知识库域名` 或 `.../mcp`）。
2. 点「网协登录」，在弹出窗口用网协账号登录。也可选填 Outline API Key。
3. 选模型厂商、填 API Key、选模型（「自定义」厂商需自己填 Base URL 和模型名称）。
4. 在右侧提问。生成中可点发送键上的加载动画中止。

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
