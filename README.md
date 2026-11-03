# GDUTNIC 排班签到

当前主页用于登录和签到，管理端维护排班及普通用户，界面保留 Material You 风格。Wiki 接入暂不启用。

- 主页 `/`：使用姓名和密码登录，仅查看本人的排班和签到信息，仅可为本人在班次时间内签到。签完一班后，若同一人当天还被安排在该班相邻的配对班次（第 1→2 班或第 3→4 班，且两班首尾相接），会自动签到配对班次并沿用首次签到时间，使其记为正常；第 2→3 班、第 4 班与次日第 1 班不会自动连签，当前班次本身的迟到/旷班判定不受影响。
- 管理端：使用启动控制台输出的随机地址；首次进入创建管理员，现有管理员直接登录。
- 每日排班：新增、编辑、删除班次，维护人员、时间和备注，查看签到进度，无需填写地点。
- 每周排班：核对图片预填的人员，补齐四个班次的时间后保存，选择“生成到某日期”，从北京时间今天起按星期匹配模板，生成至指定日期（包含当天）。支持下载 CSV 模板后一键导入：第一行列星期（星期一–日，可只写工作日）、第一列写班次，同一格多人用 `/` 分隔，导入时自动拆成换行；核对并保存名单后，仅为名单中的新人员自动创建账号（初始密码 `gg2017`），不重置已有账号。重复生成会跳过已存在或时间冲突的班次，后续修改模板不改动历史签到。“清除所有排班”经确认后删除全部日期的班次及签到记录，保留每周模板与用户账号。
- 用户管理：所有账号（含管理员）统一在账号表中管理，每个账号带一张权限表，可“更改权限”和“更改密码”，也可重置密码、启用/停用、删除。用户名即姓名，初始密码 `gg2017`，密码以带盐哈希保存，用户可在主页修改密码。
- 权限分组（更改权限时以可折叠树展示，勾选父级会展开并选中全部子项）：`用户界面`；`管理员` → `更改排班`（每日/每周/特殊排班及其他设置）、`用户管理` → `操作账号`（重置密码、启用/停用）、`添加/删除账号`、`更改权限`（为他人分配权限，并保护持有权限的账号不被无此权限者删除、停用、重置或改密）、`外勤管理`。更改密码只能由账号本人或持有“更改权限”者操作。
- 概览：点击“当前值班”中的人员行可手动改判考勤状态（准时/迟到/旷班），手动结果优先于按签到时间自动计算的结果。
- 外勤管理：按月份以卡片展示参与情况；点击人员卡片可手动改为已参加/未参加外勤，管理员修改的条目标注“管理员修改”。
- 特殊排班：单独添加临时班次，可一次安排多位人员，保存后查看未来特殊排班并修改或删除。
- 其他设置：配置提前打卡、迟到和旷班分钟数，控制签到按钮出现时间及到岗状态。
- 用户、管理员、排班、签到、每周模板和配置统一保存到 **MySQL 8.4**，支持中文姓名。已有签到的班次不能更改日期、时间或移除已签到人员。
- 时间按 `Asia/Shanghai` 计算；结束时间早于开始时间表示次日结束，跨日班次会出现在次日列表并可正常签到。

## MySQL 配置与启动

需要 Python 3.10+ 和 MySQL 8.4。复制 `.env.example` 为 `.env` 并填写 `MYSQL_*` 连接参数，环境变量优先于 `.env`。

使用本地 Docker MySQL：

```bash
docker compose up -d mysql
./start.sh
```

Docker 服务仅绑定 `127.0.0.1:3307`，MySQL 业务数据保存在 Docker 命名卷 `mysql_data`（容器内 `/var/lib/mysql`），不直接写入项目 `data/`。项目 `data/` 保存会话密钥、旧 SQLite 文件、迁移备份、每周名单种子（`weekly_roster.json`）及导入文件（`data/imports/`），不是当前 MySQL 数据目录，默认不提交到 Git。首次创建容器需在 `.env` 设置数据库用户和 root 密码，连接已有 MySQL 时无需使用 Docker，填入对应地址、端口和凭证即可。请事先创建 `gdutnic` 数据库并授予应用账号该库的建表及读写权限；应用会自动建表，不会自动覆盖旧数据。远程 TLS 可设置 `MYSQL_SSL_CA`。

Windows 使用 `start.bat`。启动时会为每周排班及已排班人员补齐缺失的普通账号，也可单独执行：

```bash
.venv/bin/python -m server.provision_members
```

本项目当前本地环境已配置 `.env` 并启动 Docker MySQL；凭证保存在不提交到 Git 的 `.env` 中。

## 从 SQLite 迁移

先停止旧版应用写入 SQLite，配置好空的 MySQL 数据库，再执行：

```bash
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m server.migrate_mysql --source data/app.sqlite
.venv/bin/python -m server.provision_members
```

迁移会先在 `data/backups/` 备份 SQLite，再在单个 MySQL 事务中导入、核对所有数据，保留管理员密码哈希、班次 ID 和签到时间。目标库非空时停止，任何导入或校验失败都会回滚，源数据库保持原样。迁移成功后重启服务。不要先启动新版服务再迁移，否则启动初始化会写入目标库。

SQLite 仅保留给迁移兼容及隔离测试，可用 `DB_BACKEND=sqlite` 显式选择，不会在 MySQL 连接失败时自动回退。

## 验证

```bash
.venv/bin/python -m unittest discover -s tests -v
RUN_MYSQL_TESTS=1 .venv/bin/python -m unittest discover -s tests -p test_mysql.py -v
```

MySQL 集成测试使用 `.env` 中的本地服务及 root 凭证，每次创建独立临时测试库并在结束时删除，不修改业务库。

---

以下为原 Wiki 助手说明，供旧服务维护参考。

# 网协 Wiki 查询助手

给泥工网协做的 Wiki Agent：通过 MCP 检索文档，再用兼容 OpenAI 的模型接口生成回答。网页对话走弹出窗口 OAuth；QQ 官方机器人可在管理页用同一套「网协认证登陆」接入，对话等价于网页里的会话。

## 运行环境

- Python 3.10+（建议 3.12）
- 能访问网协 Wiki MCP 的网络
- 任意一家兼容 OpenAI Chat Completions 的模型 Key
- （可选）QQ 官方机器人 AppID / AppSecret

## 启动

本机或局域网：<http://127.0.0.1:50025> 或 `http://本机IP:50025`。

启动后控制台会打印管理员地址，例如 `http://127.0.0.1:50025/a8clrf3j`（8 位随机路径，保存在本机数据库）。**第一次打开站点会跳转到该页**，请先注册管理员，并配置模型接口与网协 MCP 地址。之后普通访问打开对话页。

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
python -m uvicorn server.app:app --host 0.0.0.0 --port 50025
```

默认监听 `0.0.0.0:50025`。只想本机访问时把 `--host` 改成 `127.0.0.1`。局域网若被拦截，请在防火墙放行 50025。

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

- 登录使用 `fetch` 发送 JSON 并强制 POST 提交，即使脚本未加载，用户名和密码也不会出现在网址栏或服务器访问日志中。
- 所有登录会话和数据签名 Cookie 的有效期为 **4 小时**，过期后需重新登录。
- 同一来源连续 8 次登录失败会限制 15 分钟；请勿仅依赖限流，密码仍应足够复杂。
- 登录接口只信任直连地址，不读取可伪造的 `X-Forwarded-For`；部署在反向代理后时请在代理层限流。
- 已设置 `X-Frame-Options: DENY`、`Referrer-Policy: no-referrer`、CSP 禁止外链脚本，并可选择开启 HSTS。
- 公网部署请使用 HTTPS，并设置 `SESSION_HTTPS_ONLY=1` 让 Cookie 仅经 HTTPS 发送。
- 管理员页仍依赖难猜的 8 位路径，不要公开分享。
- 本项目未内置 WAF；公网部署建议放在反向代理或云防护之后。

## 开源协议

本项目采用 [MIT License](LICENSE)
