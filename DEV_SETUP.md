# 本地开发环境标准

在新设备上按本文准备环境，即可与当前仓库对齐开发。产品定位与进度见 [PROJECT_PLAN.md](PROJECT_PLAN.md)；后端/前端细节见各自 README。

## 1. 需要安装的软件（版本）

| 软件 | 建议版本 | 说明 |
|------|----------|------|
| **Git** | 2.40+ | 拉取仓库 |
| **Python** | **3.11 或 3.12**（本机验证：3.12.0） | 勿用 3.13 作首选：`pandas`/`numpy` 可能装不上 |
| **Node.js** | **20 LTS 或 22 LTS**（本机验证：24.x 也可用） | 需自带 **npm 10+** |
| **Redis** | 可选 | 默认 `REDIS_ENABLED=false`，用内存缓存即可；需要共享缓存时再装 |
| **API-Sports Key** | 必填 | 官方 Key；勿提交到 Git |

可选 IDE（任选其一即可）：

| IDE | 说明 |
|-----|------|
| **Cursor** / **VS Code** | 轻量全栈；见下方扩展 |
| **PyCharm**（Professional 或 Community） | 后端调试方便；前端需装 Vue 插件 |

不强制 Docker；本仓库按「本机双进程」开发（后端 + 前端）。

---

## 2. IDE / 编辑器扩展（推荐）

### Cursor / VS Code

扩展市场安装：

| 扩展 | 用途 |
|------|------|
| **Python**（Microsoft） | 后端语法、调试、venv 识别 |
| **Pylance** | Python 类型提示 |
| **Vue - Official**（Vue.volar，原 Volar） | Vue 3 + SFC；**不要**再装已废弃的 Vetur |
| **TypeScript Vue Plugin (Volar)** | 可选，提升 `.vue` 内 TS |
| **EditorConfig** | 若仓库有 `.editorconfig` 时统一缩进 |

可选：GitLens、Even Better TOML（无硬性要求）。

工作区建议：

- Python 解释器指向 `backend/.venv/Scripts/python.exe`（Windows）或 `backend/.venv/bin/python`
- 前端在 `frontend/` 打开或用多根工作区包含 `backend` + `frontend`

### PyCharm

| 插件 / 功能 | 说明 |
|-------------|------|
| 内置 Python | 将 Project Interpreter 设为 `backend/.venv` |
| **Vue.js** 插件 | Settings → Plugins；用于 `.vue` |
| Node.js | Settings 中指定本机 Node / npm |

---

## 3. 获取代码

```bash
git clone <本仓库 URL>
cd football-analytics
```

---

## 4. 后端配置与启动

```bash
cd backend

# 虚拟环境（每台机器做一次）
python -m venv .venv

# 激活
# Windows PowerShell / CMD:
.venv\Scripts\activate
# macOS / Linux:
# source .venv/bin/activate

python -m pip install -U pip
pip install -r requirements.txt
```

### 换机后启用最新预测算法

`pip install` 只负责准备 Python 运行环境，算法代码仍来自仓库。某个终端出现 SSL 安装失败，**不等于这台电脑不能使用新算法**：如果 PyCharm / 后端实际使用的解释器已经安装 `numpy`、`sqlalchemy` 等依赖，更新代码并重启后端后即可运行。先在后端实际使用的解释器中检查：

```powershell
cd backend
python -c "import numpy, sqlalchemy, httpx; print('依赖正常')"
python manage.py model-status
```

回家电脑首次部署或虚拟环境缺少依赖时，按以下顺序执行：

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -r requirements.txt

python manage.py init-db
python manage.py backfill-features
python manage.py backfill-ah-features
python manage.py train-model
python manage.py train-goals-model
python manage.py train-ah-model
python manage.py model-status
python -m unittest discover -s tests -v
```

- 已有 `data/football.db` 时，上述回填与训练使用本地历史数据，不消耗官方 API 配额。
- 新电脑没有历史数据库时，可以启动和预测，但 ML 模型要等本地积累到最低样本数；不要为了训练批量探测官方接口。
- `model-status` 中 1X2 或某个目标显示未通过基线门禁时，系统会使用盘口基线或显示“待分析”，这是预期保护，不是安装失败。
- 每次更新算法代码后无需重新安装全部依赖；只有 `requirements.txt` 变化、虚拟环境不存在或导入报错时才需要重新安装。

若 `pip` 报 `CERTIFICATE_VERIFY_FAILED`，这是 Python 包下载链路的证书问题，与 `.env` 的 `HTTP_VERIFY_SSL`（官方足球 API 请求）不是同一设置。优先在家庭网络执行，或为 `pip` 配置公司提供的根证书；不要长期关闭 pip 的证书校验。

若在 Python 3.13 上 `pandas`/`numpy` 安装失败，可先装核心依赖跑通 API（ML 训练相关能力暂不可用）：

```bash
pip install fastapi uvicorn sqlalchemy aiosqlite redis apscheduler httpx python-dotenv pydantic-settings fakeredis
```

### 配置文件（每台机器）

| 文件 | 是否提交 Git | 操作 |
|------|--------------|------|
| `.env` | 否（可本地有） | `copy .env.example .env`（Windows）或 `cp .env.example .env` |
| `secrets.local.env` | **否** | `copy secrets.local.env.example secrets.local.env`，填入 Key |
| `config/leagues.json` | 是（可按个人改） | 默认可直接用；增删联赛后**重启后端** |

`secrets.local.env` 最少包含：

```env
API_SPORTS_KEY=你的官方Key
```

常用可选（见 `.env.example`）：

| 变量 | 本地默认建议 |
|------|----------------|
| `REDIS_ENABLED` | `false`（无 Redis 时） |
| `HTTP_VERIFY_SSL` | 公司代理劫持 SSL 时设 `false` |
| `LOCAL_FIRST` | `true` |
| `API_HISTORY_MODE` | 免费档用 `free`；付费历史用 `full` |
| `SCHEDULER_TIMEZONE` | `Asia/Shanghai` |

加载顺序：先 `.env`，再 `secrets.local.env`（后者覆盖前者）。**禁止**把真实 Key 写进 `.env.example` 或提交进 Git。

### 初始化数据并启动

```bash
python manage.py init-db
python manage.py fetch-leagues
python manage.py fetch-upcoming
# 或：python manage.py fetch-today

uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

常用管理命令：

```bash
python manage.py check-quota
python manage.py backfill-team-names
python manage.py model-status
```

验证：浏览器打开 http://127.0.0.1:8000/docs ，或 `GET http://127.0.0.1:8000/api/v1/health`。

---

## 5. 前端配置与启动

另开终端：

```bash
cd frontend
npm install
npm run dev
```

- 开发地址：http://127.0.0.1:5173  
- Vite 已将 `/api` 代理到 `http://127.0.0.1:8000`，**前端不配 API Key**  
- 生产构建：`npm run build`（含 `vue-tsc`）

依赖以 `frontend/package.json` 为准（Vue 3、Vite 6、TypeScript 5.7、Naive UI、ECharts、Axios、Vue Router）。

---

## 6. 后端 Python 依赖（钉死版本）

见 `backend/requirements.txt`，当前主要包括：

| 包 | 版本（钉死） | 用途 |
|----|--------------|------|
| fastapi | 0.104.1 | API |
| uvicorn[standard] | 0.24.0 | ASGI |
| sqlalchemy | 2.0.23 | ORM |
| aiosqlite | 0.19.0 | SQLite 异步 |
| redis / fakeredis | 5.0.1 / 2.20.1 | 缓存 |
| apscheduler | 3.10.4 | 定时任务 |
| httpx | 0.25.1 | 请求官方 API |
| pydantic-settings | 2.1.0 | 配置 |
| python-dotenv | 1.0.0 | 环境变量 |
| pandas / numpy | 2.1.3 / 1.26.2 | ML / 特征（可选能力） |

新环境务必 `pip install -r requirements.txt`，避免「随便装最新版」漂移。

---

## 7. 换机检查清单

- [ ] Python 3.11/3.12 + Node 20+ + Git  
- [ ] `backend/.venv` 已创建并 `pip install -r requirements.txt`  
- [ ] `secrets.local.env` 已填 `API_SPORTS_KEY`（且未提交）  
- [ ] `.env` 已从 example 复制（至少确认 `REDIS_ENABLED` / SSL）  
- [ ] `python manage.py init-db` 成功，`data/football.db` 可生成  
- [ ] 后端 `:8000/docs` 可开，前端 `:5173` 可开且首页能拉赛程  
- [ ] IDE 解释器指向 venv；Vue 用 Volar 而非 Vetur  
- [ ] 联赛清单按需改 `backend/config/leagues.json` 后重启后端  

---

## 8. 常见问题

| 现象 | 处理 |
|------|------|
| 前端网络错误 | 先起后端；确认代理目标 `127.0.0.1:8000` |
| 赛程为空 | 等待后端定时任务，或点击工具栏「同步」（耗官方配额） |
| 官方足球 API SSL 证书错误 | `.env` 设 `HTTP_VERIFY_SSL=false`（仅影响官方接口请求） |
| pip `CERTIFICATE_VERIFY_FAILED` | 换可信网络或配置公司根证书；不要用 `HTTP_VERIFY_SSL` 处理 |
| pandas 安装失败 | 换 Python 3.12，或先装核心依赖（见 §4） |
| 配额用尽 | `check-quota`；开发少打官方，优先读本地库 |

---

## 9. 文档索引

| 文档 | 内容 |
|------|------|
| [DEV_SETUP.md](DEV_SETUP.md) | **本文：换机环境标准** |
| [PROJECT_PLAN.md](PROJECT_PLAN.md) | 产品边界与进度 |
| [backend/README.md](backend/README.md) | API、调度、联赛配置 |
| [frontend/README.md](frontend/README.md) | 前端路由与对接 |
| [frontend/FRONTEND_UI_SPEC.md](frontend/FRONTEND_UI_SPEC.md) | UI / Tabs 约定 |
