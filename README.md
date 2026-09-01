# 网协 Wiki 查询助手

给泥工网协做的 Wiki Agent, 通过 MCP 检索文档，再用兼容 OpenAI 的模型接口生成回答。界面在浏览器里打开，登录走弹出窗口（OAuth）。

## 运行环境

- Python 3.10+（建议 3.12）
- 能访问网协wiki的 MCP 知识库的网络环境
- 任意一家兼容 OpenAI Chat Completions 的模型 Key

## 启动

本机或局域网访问：<http://127.0.0.1:8787> 或 `http://本机IP:8787`。

启动后控制台会展示管理员地址，例如 `http://127.0.0.1:8787/a8clrf3j`（8 位随机路径，固定保存在本机）。**第一次打开站点会跳转到该页**，请先注册管理员，并在侧栏配置模型接口和网协 MCP 地址。之后普通访问打开对话页，模型 Key 与 MCP 地址不再出现在聊天界面。

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

1. 按控制台地址进入管理员页，注册后在「模型接口」和「知识库 MCP」中保存配置。
2. 回到对话页，点「网协登录」，在弹出窗口用网协账号登录。
3. 在右侧提问。生成中可点发送键上的加载动画中止。

## 项目结构

```
server/     FastAPI、MCP、OAuth、对话流
web/        静态页面
icon/       站点图标与界面符号
start.bat   Windows 启动
start.sh    Linux / macOS 启动
```

## 安全注意

- 绑在 `0.0.0.0` 时，能访问该 IP:8787 的人都能打开界面；知识库仍需各自完成 OAuth。
- 公网暴露前应使用 HTTPS，并把会话改为 `https_only`。

## 开源协议

本项目采用 [MIT License](LICENSE)   