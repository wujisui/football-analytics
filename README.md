# Football Analytics

足球数据分析全栈项目。后端对接 [API-Sports](https://www.api-football.com/)（官方 Key，RapidAPI 仅备用），做**赛前**概率分析并通过 REST API 对外提供；前端用 Vue 展示联赛、今日比赛与分析结果。

> 产品定位、已完成 / 未完成 / 后续规划见 **[PROJECT_PLAN.md](PROJECT_PLAN.md)**。

## 仓库结构

```
football-analytics/
├── PROJECT_PLAN.md   # 项目计划书（进度与路线图）
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

开两个终端：

```bash
# 终端 1 - 后端
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
copy .env.example .env            # 非密钥配置；密钥放 secrets.local.env
python manage.py init-db
python manage.py fetch-leagues
python manage.py fetch-today
uvicorn main:app --reload
```

启动前请先配置 `backend/secrets.local.env` 中的 `API_SPORTS_KEY`（见 [backend/README.md](backend/README.md)）。

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
