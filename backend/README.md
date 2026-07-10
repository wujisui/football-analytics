# Football Analytics

足球数据分析后端服务。从 [API-Football](https://www.api-football.com/)（通过 RapidAPI）拉取联赛、球队与赛程数据，结合赛前统计做概率分析，并通过 REST API 对外提供。

## 功能概览

- **数据拉取**：联赛、球队、当日赛程、历史交锋、球队统计等
- **本地优先**：官方响应写入 SQLite（`api_snapshots`），业务优先读本地，过期再请求官方
- **缓存层**：Redis 作热缓存（无 Redis 时自动降级为 fakeredis）
- **赛前分析**：基于历史数据计算胜/平/负概率及推荐，结果写入 `pre_match_data`
- **定时任务**：每日初始化、赛前更新、过期数据清理
- **管理接口**：查看调度器状态、手动触发任务

### 数据读取顺序（省配额）

```
Redis 热缓存 → SQLite api_snapshots / pre_match_data → API-Sports 官方
                         ↓（命中官方后）
                  写回 Redis + SQLite
```

**产品定位：赛前分析，不是实时比分。**  
开赛后 / 结束后：**不再请求官方**，回溯只读本地库。

| 距开赛      | 分析刷新间隔       | 说明             |
|----------|--------------|----------------|
| > 72 小时  | 24 小时        | 远期赛程提前准备       |
| 24–72 小时 | 12 小时        | 中期准备           |
| 6–24 小时  | 3 小时         | 赛前日，赔率开始变化     |
| 0–6 小时   | 1 小时         | 临场阵容/伤病/赔率最后更新 |
| 已开赛或已结束  | **停止一切官方请求** | 只保留本地分析结果      |

赛前关心的数据（目标能力）：

| 数据        |  状态                  |
|-----------|----------------------|
| 历史交锋 / 近况 | 已接；详情 `package` 展示 |
| 赛前概率结果    | 已写入 `pre_match_data` |
| 阵容 / 替补 / 伤病 | 已接 lineups / injuries 并展示 |
| 赛前赔率      | 已接 `/odds`（无开盘则为空） |
| 实时比分 / 滚球 | **不做**               |

可用 `ANALYSIS_REFRESH_TTL_SECONDS` 强制覆盖刷新间隔（`0` = 上表策略）。

## 技术栈

| 组件                     | 用途                 |
|------------------------|--------------------|
| FastAPI                | Web 框架与 OpenAPI 文档 |
| SQLAlchemy + aiosqlite | 异步 ORM，SQLite 持久化  |
| Redis / fakeredis      | API 响应缓存           |
| APScheduler            | 后台定时任务             |
| httpx                  | 异步 HTTP 客户端        |

## 项目结构

```
football-analytics/
├── main.py                 # 应用入口，启动调度器
├── manage.py               # 命令行管理工具
├── app/
│   ├── api/v1/endpoints/   # API 路由（health、fixtures、leagues、admin）
│   ├── core/               # 配置、数据库、日志
│   ├── models/             # SQLAlchemy 数据模型
│   ├── schemas/            # Pydantic 响应模型
│   ├── services/           # 拉取、缓存、分析等业务逻辑
│   └── tasks/              # APScheduler 定时任务
├── data/                   # SQLite 数据库文件
└── logs/                   # 按日轮转的日志
```

## 快速开始

### 1. 环境准备

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

> Python 3.13 下 `pandas` 可能安装失败。若仅需运行 API，可先安装核心依赖：`fastapi uvicorn sqlalchemy aiosqlite redis apscheduler httpx python-dotenv pydantic-settings fakeredis`。

### 2. 配置环境变量

1. 复制非密钥配置（可选）：`copy .env.example .env`
2. **密钥单独放本地文件**（不会进 Git）：

```bash
copy secrets.local.env.example secrets.local.env
```

编辑 `secrets.local.env`，填入官方 Key：

```env
API_SPORTS_KEY=你的官方Key
```

| 变量                                | 说明                                          |
|-----------------------------------|---------------------------------------------|
| `API_SPORTS_KEY`                  | API-Sports 官方密钥（推荐，放在 `secrets.local.env`）  |
| `RAPIDAPI_KEY`                    | RapidAPI 备用密钥（仅当未配置官方 Key 时使用）              |
| `API_BASE_HOST` / `RAPIDAPI_HOST` | 默认 `v3.football.api-sports.io`              |
| `DATABASE_URL`                    | 默认 `sqlite+aiosqlite:///./data/football.db` |
| `REDIS_URL`                       | Redis 地址，不可用时会用 fakeredis                   |
| `ADMIN_API_KEY`                   | 管理接口鉴权密钥（可放 `secrets.local.env`）            |
| `HTTP_VERIFY_SSL`                 | 公司代理拦截 SSL 时设为 `false`                      |
| `SCHEDULER_TIMEZONE`              | 调度器时区，默认 `Asia/Shanghai`                    |
| `LOCAL_FIRST`                     | `true` 时优先读本地库/缓存，再打官方                      |
| `ANALYSIS_REFRESH_TTL_SECONDS`    | `0`=按开赛时间动态刷新；`>0` 则强制固定秒数                  |

> 不要把真实 Key 写进 `.env.example` 或提交到 Git。本地运行时会先读 `.env`，再读 `secrets.local.env`（后者覆盖前者）。

### 3. 初始化并启动

```bash
python manage.py init-db
python manage.py fetch-leagues
python manage.py fetch-today
uvicorn main:app --reload
```

服务启动后访问：

- 健康检查：http://127.0.0.1:8000/api/v1/health
- **交互式 API 文档**：http://127.0.0.1:8000/docs
- ReDoc：http://127.0.0.1:8000/redoc

## 命令行工具

```bash
python manage.py init-db          # 初始化数据库表
python manage.py fetch-leagues    # 拉取配置的联赛数据
python manage.py fetch-today      # 拉取今日赛程
python manage.py fetch-upcoming   # 拉取未来 N 天赛程（默认 7，含今天）
python manage.py check-quota      # 查看 API 剩余配额
python manage.py test-api         # 测试 API 连通性
python manage.py clear-cache      # 清空足球 API 缓存
python manage.py cache-stats      # 查看缓存命中率
python manage.py list-tasks       # 列出定时任务
python manage.py trigger-task --name daily_init   # 手动触发任务
python manage.py run-scheduler    # 前台运行调度器（调试用）
```

可触发的任务名：`daily_init`、`pre_match_update`、`clean_old_data`。

## API 接口

所有业务接口前缀为 `/api/v1`。完整请求/响应结构见 **[/docs](http://127.0.0.1:8000/docs)**。

### 公开接口

| 方法  | 路径                                | 说明                           |
|-----|-----------------------------------|------------------------------|
| GET | `/health`                         | 服务状态与缓存统计                    |
| GET | `/leagues`                        | 已配置联赛列表；可选 `date`、`days`；含今日/近期场次数 |
| GET | `/fixtures/today`                 | 赛程列表；可选 `league_id`、`date`、`days`（默认仅当天） |
| GET | `/fixtures/{fixture_id}/analysis` | 单场比赛详细分析                     |

**注意**：`league_id` 是联赛 ID（如英超 `39`），`fixture_id` 是具体比赛 ID，二者不同。查英超今日比赛应使用：

```
GET /api/v1/fixtures/today?league_id=39
```

### 管理接口

请求头需携带 `X-Admin-Key: <ADMIN_API_KEY>`。

| 方法   | 路径                     | 说明                                    |
|------|------------------------|---------------------------------------|
| GET  | `/admin/tasks`         | 调度器与任务状态                              |
| POST | `/admin/tasks/trigger` | 手动触发任务，body: `{"name": "daily_init"}` |

### 常用联赛 ID

| 联赛  | ID   |
|-----|------|
| 英超  | 39   |
| 西甲  | 140  |
| 德甲  | 78   |
| 意甲  | 135  |
| 法甲  | 61   |
| 欧冠  | 2    |
| 欧罗巴 | 3    |
| 亚冠  | 10   |
| 中超  | 169  |
| 美职联 | 253  |
| 巴甲  | 71   |
| 日职联 | 98   |
| 韩K联 | 292  |

## 定时任务

应用启动时（`uvicorn main:app`）会自动注册并运行调度器：

| 任务                 | 触发规则      | 作用                  |
|--------------------|-----------|---------------------|
| `daily_init`       | 每天 06:00  | 拉取联赛、球队、今日赛程        |
| `pre_match_update` | 每 5 分钟    | 更新开赛前 2 小时内的比赛数据与分析 |
| `clean_old_data`   | 每周一 03:00 | 清理 7 天前的分析数据与过期日志   |

时区由 `SCHEDULER_TIMEZONE` 控制。

## 前端对接提示

1. 先调 `/api/v1/leagues`（可选 `?days=7`）展示联赛入口与近期场次数
2. 按 `league_id` 调 `/api/v1/fixtures/today?league_id=39&days=7` 获取近期比赛列表
3. 用户点击某场后，用返回的 `fixture_id` 调 `/api/v1/fixtures/{fixture_id}/analysis`

本地无数据时先执行：

```powershell
python manage.py fetch-leagues
python manage.py fetch-upcoming
```
4. 响应头 `X-Data-Source` 表示数据来源（`database` / `cache` / `api`）
5. 开发阶段可直接用 Swagger UI（`/docs`）试调接口

## 常见问题

**SSL 证书错误**  
公司网络代理会拦截 HTTPS，在 `.env` 中设置 `HTTP_VERIFY_SSL=false`。

**今日比赛为空**  
先执行 `python manage.py fetch-today`，或等待 `daily_init` 任务运行。

**API 配额不足**  
用 `python manage.py check-quota` 查看剩余次数；缓存开启后可减少重复请求。
