# Football Analytics

足球数据分析后端服务。从 [API-Football](https://www.api-football.com/)（通过 RapidAPI）拉取联赛、球队与赛程数据，结合赛前统计做概率分析，并通过 REST API 对外提供。

## 功能概览

- **数据拉取**：联赛、球队、当日赛程、历史交锋、球队统计等
- **本地优先**：官方响应写入 SQLite（`api_snapshots`），业务优先读本地，过期再请求官方
- **缓存层**：Redis 作热缓存（无 Redis 时自动降级为 fakeredis）
- **赛前分析**：多因子胜/平/负概率（近况/交锋/均值回归/轻度盘口）及推荐，结果写入 `pre_match_data` + `match_features`
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
| 赛前简报 | 官方 `/predictions` → `package.briefing`，详情页「赛前简报」Tab（与本地「我的预测」无关） |
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

换机或新电脑请先按仓库根目录 **[DEV_SETUP.md](../DEV_SETUP.md)** 安装 Python / Node / IDE 插件并配置密钥。

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
| `API_HISTORY_MODE`                | `full`=付费历史（H2H 不限年份）；`free`=仅 2022–2024      |
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
python manage.py trigger-task --name midday_fixtures_sync   # 手动触发中午赛程同步
python manage.py run-scheduler    # 前台运行调度器（调试用）
python manage.py backfill-features  # 从已结束场次回填 match_features 训练行
python manage.py train-model      # 用赛果标签训练 1X2（需 ≥ ML_MIN_TRAIN_SAMPLES）
python manage.py model-status     # 查看标签数与当前 multifactor / ml
```

可触发的任务名：`midday_fixtures_sync`、`pre_match_update`、`capture_results`、`clean_old_data`、`train_model`。

### 概率模型（多因子 → 自动切 ML）

本地数据从现在起积累。链路：

1. 赛前分析写入 `match_features`（特征 + 当时概率）
2. 赛果回写打 `label`；`capture_results` 后若标签 ≥ `ML_MIN_TRAIN_SAMPLES`（默认 30）且有新增 → **自动训练**
3. 有合格模型后，新分析自动 `source=ml`；否则继续 `multifactor`

配置见 `.env`：`ML_MIN_TRAIN_SAMPLES`、`ML_AUTO_TRAIN`。盘口权重刻意偏低；长连胜淡化、长不胜抬升反弹。
## API 接口

所有业务接口前缀为 `/api/v1`。完整请求/响应结构见 **[/docs](http://127.0.0.1:8000/docs)**。

### 公开接口

| 方法  | 路径                                | 说明                           |
|-----|-----------------------------------|------------------------------|
| GET | `/health`                         | 服务状态与缓存统计                    |
| GET | `/leagues`                        | 已配置联赛列表；可选 `date`、`days`；含今日/近期场次数 |
| GET | `/fixtures/today`                 | 赛程列表；可选 `league_id`、`date`、`days`（默认仅当天） |
| POST | `/fixtures/sync`                 | 强制同步赛程（绕过日缓存）；可选 `days` / `date`；约 90s 冷却 |
| GET | `/fixtures/results`               | 按日查赛果 + 当日预测命中；必填 `date=YYYY-MM-DD` |
| GET | `/fixtures/results/history`       | 历史准确率汇总 + 按日序列；`days=0`（默认）全部本地样本，`>0` 为近 N 日 |
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
| POST | `/admin/tasks/trigger` | 手动触发任务，body: `{"name": "midday_fixtures_sync"|"pre_match_update"|"capture_results"|"clean_old_data"|"train_model"}` |

### 常用联赛 ID

**生效目录**：`config/leagues.json`（也可设环境变量 `LEAGUES_JSON`）。  
**参考目录**：`config/leagues.example.json`（全球一级联赛清单；后端会加载为筛选「额外联赛」与 sync 白名单，**不会**替代 `leagues.json` 的默认勾选集）。

用法：从 example 里复制需要的条目到 `leagues.json`，保存后**重启后端**。条目字段：`name`（中文显示名）、`id`（API-Sports）、`country`；可选 `season`（如世界杯）、`region`（仅注释用，程序忽略）。

增删联赛只改 `leagues.json`；左侧菜单、筛选目录与强制刷新都只认该文件。

| 联赛（当前 `leagues.json` 常用） | ID |
|-----|------|
| 英超  | 39   |
| 西甲  | 140  |
| 德甲  | 78   |
| 意甲  | 135  |
| 法甲  | 61   |
| 欧冠  | 2    |
| 欧罗巴 | 3    |
| 欧协联 | 848  |
| 亚冠  | 10   |
| 中超  | 169  |
| 世界杯 | 1    |
| 美职联 | 253  |
| 巴甲  | 71   |
| 日职联 | 98   |
| 韩K联 | 292  |

更多一级联赛（荷甲/土超/墨超/沙特联/解放者杯等）见 `leagues.example.json`。

赛程同步按**配置联赛**调用 `fixtures?league=&season=&from=&to=`；免费套餐对当前赛季受限时会回退到按日 `date=` 并过滤目录联赛。

## 定时任务

应用启动时（`uvicorn main:app`）会自动注册并运行调度器：

| 任务                     | 触发规则      | 作用                                      |
|------------------------|-----------|-----------------------------------------|
| `midday_fixtures_sync` | 每天 12:00  | 强制拉取近期窗口赛程 + 缺盘补全（对齐首页同步窗口）              |
| `pre_match_update`     | 每 5 分钟    | 更新开赛前 2 小时内的比赛数据与分析                     |
| `capture_results`      | 每 30 分钟   | 回写近日终场比分                                  |
| `clean_old_data`       | 每周一 03:00 | 清理 7 天前的分析数据与过期日志                       |

时区由 `SCHEDULER_TIMEZONE` 控制（默认 `Asia/Shanghai`）。  
官网文档：赛前 `/odds` 约每 3 小时更新；赛程类日更一次即可。本项目用中午任务对齐「日更」，并把该次首次落库的盘口冻为**初盘**；首页强制刷新 / 详情补拉写入**即时盘**。  
手动：`python manage.py trigger-task midday_fixtures_sync`。

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
先执行 `python manage.py fetch-upcoming`，或等待中午 `midday_fixtures_sync` / 首页强制刷新。

**API 配额不足**  
用 `python manage.py check-quota` 查看剩余次数；缓存开启后可减少重复请求。
