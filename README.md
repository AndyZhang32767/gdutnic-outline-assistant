# 网协 Wiki 查询助手

给泥工网协做的 Wiki Agent：通过 MCP 检索文档，再用兼容 OpenAI 的模型接口生成回答。网页对话走弹出窗口 OAuth；QQ 官方机器人可在管理页用同一套「网协认证登陆」接入，对话等价于网页里的会话。

## 运行环境

- Python 3.10+（建议 3.12）
- 能访问网协 Wiki MCP 的网络
- 任意一家兼容 OpenAI Chat Completions 的模型 Key
- （可选）QQ 官方机器人 AppID / AppSecret

## 启动

本机或局域网：<http://127.0.0.1:8787> 或 `http://本机IP:8787`。

启动后控制台会打印管理员地址，例如 `http://127.0.0.1:8787/a8clrf3j`（8 位随机路径，保存在本机数据库）。**第一次打开站点会跳转到该页**，请先注册管理员，并配置模型接口与网协 MCP 地址。之后普通访问打开对话页。

**Windows**

```bat
start.bat
```

**Linux / macOS**

```bash
chmod +x start.sh
./start.sh
```

启动脚本会：

1. 在项目目录创建并使用 `.venv` 虚拟环境（避免 Linux 上系统 Python 禁止直接 `pip install`）
2. 先用默认 PyPI 安装依赖；失败时自动依次尝试清华 / 阿里云 / 中科大 / 百度镜像

也可手动（建议同样使用虚拟环境）：

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# 若默认源失败：
# pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn
python -m uvicorn server.app:app --host 0.0.0.0 --port 8787
```

默认监听 `0.0.0.0:8787`。只想本机访问时把 `--host` 改成 `127.0.0.1`。局域网若被拦截，请在防火墙放行 8787。

## 使用

### 网页对话

1. 按控制台地址进入管理员页，注册后配置「模型接口」和「知识库 MCP」。
2. 回到对话页，点「网协认证登陆」，在弹窗里用企业账号登录。
3. 右侧提问；生成中可点发送键上的加载动画中止。

### QQ 机器人（可选）

1. 在管理员侧栏打开「QQ 机器人」，填写 AppID、AppSecret。
2. 在「知识库 MCP」或「QQ 机器人」页点「网协认证登陆」（与网页同一套 OAuth），登录结果会存到服务器，供机器人检索知识库。
3. 打开「启用 QQ 机器人」。私聊或在群里 @ 机器人即可对话；发送「新会话」可再开一轮。

QQ 没有登录弹窗，因此必须由管理员在后台完成一次知识库 OAuth，而不是粘贴 API Token。

### 管理员其它项

- **MCP 调用热度**：控制是否检索、检索强度。
- **对话记录**：查看访客/QQ 会话缓存，可调缓存上限。

## 数据存储

业务数据落在 **SQLite**（`data/app.sqlite`），标准库即可，无需额外部署数据库。主要表：

| 表 | 内容 |
| --- | --- |
| `settings` / `users` | 管理员路径、模型、MCP、QQ、账号 |
| `visitors` / `chats` / `messages` | 对话记录 |
| `oauth_clients` | Wiki OAuth 客户端注册信息 |

从旧版升级时，若仍有 `admin.json` / `chats.json` / `oauth_client.json`，启动会自动迁入 SQLite，并把原文件改名为 `.bak`。`data/` 目录默认不入库。

会话签名密钥仍在 `data/session_secret.txt`（或环境变量 `SESSION_SECRET`）。

## 项目结构

```
server/     FastAPI、MCP、OAuth、对话流、SQLite、QQ 机器人
web/        对话页与管理员静态页面
icon/       站点图标与界面符号
data/       本机数据（SQLite 等，不提交）
start.bat   Windows 启动
start.sh    Linux / macOS 启动
```

## 安全注意

- 绑在 `0.0.0.0` 时，能访问该 IP:8787 的人都能打开界面；网页用户仍需各自完成 OAuth。
- 管理员页依赖难猜的 8 位路径 + 登录；公网暴露前应使用 HTTPS，并把会话改为 `https_only`。
- 管理端知识库 OAuth token 存在 SQLite 中，权限等同于该 Wiki 账号，请勿泄露 `data/`。
- 本项目未内置 WAF / 限流；公网部署建议放在反向代理或云防护之后。

## 开源协议

本项目采用 [MIT License](LICENSE)
