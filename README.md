# Football Analytics

足球数据分析全栈项目。后端使用管理员配置的官方 Key 对接 [API-Sports](https://www.api-football.com/)，做**赛前**概率分析并通过 REST API 对外提供；前端用 Vue 展示联赛、今日比赛与分析结果。

> 产品定位、已完成 / 未完成 / 后续规划见 **[PROJECT_PLAN.md](PROJECT_PLAN.md)**。  
> 用户鉴权 / VIP / API 配额设计见 **[docs/AUTH_VIP_QUOTA.md](docs/AUTH_VIP_QUOTA.md)**（规划中，代码未落地）。  
> **换机 / 新环境**：版本、IDE 插件与安装步骤见 **[DEV_SETUP.md](DEV_SETUP.md)**（按该文档准备即可对齐开发环境）。  
> **本机生产预览**：前端打包与后端部署见 **[docs/LOCAL_PROD_DEPLOY.md](docs/LOCAL_PROD_DEPLOY.md)**。  
> **阿里云 ECS（含本地库迁云）**：见 **[docs/ALIYUN_ECS.md](docs/ALIYUN_ECS.md)**。  
> **清空比赛历史 / 换盘口重训**：见 **[docs/RESET_MATCH_HISTORY.md](docs/RESET_MATCH_HISTORY.md)**。

## 仓库结构

```
football-analytics/
├── PROJECT_PLAN.md   # 项目计划书（进度与路线图）
├── DEV_SETUP.md      # 本地开发环境标准（版本 / 插件 / 配置）
├── docs/             # 专题设计文档
│   ├── LOCAL_PROD_DEPLOY.md  # 本机生产打包与部署
│   ├── ALIYUN_ECS.md         # 阿里云 ECS + 本地 SQLite/模型迁云
│   ├── RESET_MATCH_HISTORY.md  # 清空比赛历史（换盘口后从零攒样本）
│   └── AUTH_VIP_QUOTA.md  # 用户鉴权 / VIP / API 配额（规划）
├── backend/          # Python + FastAPI 后端
│   ├── app/          # 业务代码：API、模型、服务、定时任务
│   ├── main.py       # 应用入口
│   ├── manage.py     # 命令行管理工具
│   └── README.md     # 后端详细文档
└── frontend/         # Vue 3 + Vite 前端
    ├── src/          # 页面、组件、API 封装
    └── README.md     # 前端详细文档
```

| 目录          | 说明                          | 状态      |
|-------------|-----------------------------|---------|
| `backend/`  | FastAPI 服务、本地优先落库、缓存、分析、调度器 | 可用      |
| `frontend/` | Vue 前端，对接 `/api/v1` 接口      | 可用（MVP） |

## 本地全栈启动

完整清单（Python/Node 版本、Cursor/VS Code/PyCharm 插件、密钥与联赛配置）见 **[DEV_SETUP.md](DEV_SETUP.md)**。

开两个终端：

```bash
# 终端 1 - 后端
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
copy .env.example .env            # 配置（可选）
python manage.py init-db
# 启动后注册账号，再配置官方 Key：
#   python manage.py set-admin 你的账号
#   python manage.py set-api-sports-key keyA,keyB
# 或前端「我的 → 管理员设置」
python manage.py fetch-leagues    # 需已配置 Key
python manage.py fetch-today
uvicorn main:app --reload
```

官方 Key 配置与多 Key 切换见 [docs/API_SPORTS_KEYS.md](docs/API_SPORTS_KEYS.md)。

```bash
# 终端 2 - 前端
cd frontend
npm install
npm run dev
```

访问：

- 前端：http://127.0.0.1:5173
- 后端健康检查：http://127.0.0.1:8000/api/v1/health
- API 文档：http://127.0.0.1:8000/docs

详细说明见 [backend/README.md](backend/README.md) 与 [frontend/README.md](frontend/README.md)。

## API 概览

接口前缀：`/api/v1`

| 方法  | 路径                                | 说明        |
|-----|-----------------------------------|-----------|
| GET | `/health`                         | 服务状态      |
| GET | `/leagues`                        | 联赛列表      |
| GET | `/fixtures/today?league_id=39`    | 今日赛程（含分析） |
| GET | `/fixtures/{fixture_id}/analysis` | 单场比赛分析    |

常用联赛 ID：英超 `39`、西甲 `140`、德甲 `78`、意甲 `135`、法甲 `61`、欧冠 `2`、欧罗巴 `3`、亚冠 `10`、日职联 `98`、韩K联 `292`。

管理接口需请求头 `X-Admin-Key`，详见 Swagger 文档。

## 前端页面

| 路由                     | 说明           |
|------------------------|--------------|
| `/`                    | 联赛列表         |
| `/leagues/:leagueId`   | 该联赛今日赛程      |
| `/fixtures/:fixtureId` | 单场比赛分析（含概率图） |

开发时 Vite 会把 `/api` 代理到 `http://127.0.0.1:8000`。注意：`league_id`（联赛 ID，如英超 `39`）与 `fixture_id`（比赛 ID）不要混用。

## 技术栈

**后端**：FastAPI · SQLAlchemy · SQLite · Redis/fakeredis · APScheduler · httpx

**前端**：Vue 3 · Vite · TypeScript · Naive UI · ECharts · Axios · Vue Router

## 许可证

私有项目，仅供学习与内部使用。
