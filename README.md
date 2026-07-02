# Football Analytics

足球数据分析全栈项目。后端从 [API-Football](https://www.api-football.com/)（RapidAPI）拉取联赛与赛程数据，做赛前概率分析并通过 REST API 对外提供；前端用于展示联赛、今日比赛与分析结果。

## 仓库结构

```
football-analytics/
├── backend/          # Python + FastAPI 后端（已实现）
│   ├── app/          # 业务代码：API、模型、服务、定时任务
│   ├── main.py       # 应用入口
│   ├── manage.py     # 命令行管理工具
│   └── README.md     # 后端详细文档
└── frontend/         # 前端项目（待开发）
```

| 目录 | 说明 | 状态 |
|------|------|------|
| `backend/` | FastAPI 服务、数据拉取、缓存、分析、调度器 | 可用 |
| `frontend/` | Web 前端，对接 `/api/v1` 接口 | 规划中 |

## 快速开始（后端）

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
copy .env.example .env            # 配置 API 密钥等
python manage.py init-db
python manage.py fetch-leagues
python manage.py fetch-today
uvicorn main:app --reload
```

启动后访问：

- 健康检查：http://127.0.0.1:8000/api/v1/health
- API 文档：http://127.0.0.1:8000/docs

更完整的后端说明（环境变量、CLI 命令、定时任务、常见问题）见 [backend/README.md](backend/README.md)。

## API 概览

接口前缀：`/api/v1`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 服务状态 |
| GET | `/leagues` | 联赛列表 |
| GET | `/fixtures/today?league_id=39` | 今日赛程（含分析） |
| GET | `/fixtures/{fixture_id}/analysis` | 单场比赛分析 |

管理接口需请求头 `X-Admin-Key`，详见 Swagger 文档。

## 前端对接

1. 后端默认运行在 `http://127.0.0.1:8000`，已开启 CORS
2. 推荐调用顺序：`/leagues` → `/fixtures/today?league_id=...` → `/fixtures/{id}/analysis`
3. `league_id`（联赛 ID，如英超 `39`）与 `fixture_id`（比赛 ID）不要混用
4. 前端代码放在 `frontend/` 目录，后续可独立选型（React / Vue 等）

## 技术栈

**后端**：FastAPI · SQLAlchemy · SQLite · Redis/fakeredis · APScheduler · httpx

**前端**：待定

## 许可证

私有项目，仅供学习与内部使用。
