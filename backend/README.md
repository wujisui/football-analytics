# Football Analytics

足球数据分析后端服务。使用管理员配置的官方 Key 从 [API-Football](https://www.api-football.com/) 拉取联赛、球队与赛程数据，结合赛前统计做概率分析，并通过 REST API 对外提供。

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
开赛后 / 结束后：**预测快照审计字段冻结**；详情展示包可在用户点开时按需补缺并落库。

| 距开赛      | 分析刷新间隔       | 说明             |
|----------|--------------|----------------|
| > 72 小时  | 24 小时        | 远期赛程提前准备       |
| 24–72 小时 | 12 小时        | 中期准备           |
| 6–24 小时  | 3 小时         | 赛前日，赔率开始变化     |
| 0–6 小时   | 1 小时         | 临场阵容/伤病/赔率最后更新 |
| 已开赛或已结束  | 预测快照不刷新；展示包仍可按点击补缺 | 赛果由固定批次回写 |

赛前关心的数据（目标能力）：

| 数据        |  状态                  |
|-----------|----------------------|
| 历史交锋 / 近况 | 已接；详情 `package` 展示 |
| 赛前概率结果    | 已写入 `pre_match_data` |
| 阵容 / 替补 / 伤病 | 已接 lineups / injuries 并展示 |
| 赛前简报 | 官方 `/predictions` → `package.briefing`，详情页「赛前简报」Tab（与本地「我的预测」无关） |
| 赛前赔率      | 已接 `/odds`（无开盘则为空） |
| 实时比分 / 滚球 | **不做**               |

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

### 2. 配置官方 Key

```bash
python manage.py init-db
# 启动后端 → 注册账号 →
python manage.py set-admin 你的账号
python manage.py set-api-sports-key keyA,keyB
# 或前端「我的 → 管理员设置 → API-Sports 官方 Key」
```

详见 [docs/API_SPORTS_KEYS.md](../docs/API_SPORTS_KEYS.md)。多枚 Key 逗号分隔，当天配额耗尽自动切换。

可选非密钥配置：`copy .env.example .env`

| 变量                                | 说明                                          |
|-----------------------------------|---------------------------------------------|
| `API_BASE_HOST`                   | 默认 `v3.football.api-sports.io`              |
| `DATABASE_URL`                    | 默认 `sqlite+aiosqlite:///./data/football.db` |
| `REDIS_URL`                       | Redis 地址，不可用时会用 fakeredis                   |
| `ADMIN_API_KEY`                   | 管理接口兼容鉴权（脚本用；日常用管理员会话）                    |
| `HTTP_VERIFY_SSL`                 | 公司代理拦截 SSL 时设为 `false`                      |
| `SCHEDULER_TIMEZONE`              | 调度器时区，默认 `Asia/Shanghai`                    |
| `LOCAL_FIRST`                     | `true` 时优先读本地库/缓存，再打官方                      |
| `ENABLE_FREE_QUOTA`               | `true`（默认）=每天 11:00 全量 + 22:00 盘口轻刷；管理员 UI 可覆盖 |
| `API_HISTORY_MODE`                | `free`（默认）=免费套餐日期/赛季夹紧；`full`=付费不限年份与赛程窗口 |

> 官方 Key 只通过管理员配置写入数据库，不要写进前端或提交到 Git。

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
python manage.py trigger-task --name scheduled_fixtures_sync  # 手动触发赛程窗口同步
python manage.py run-scheduler    # 前台运行调度器（调试用）
python manage.py backfill-features  # 从已结束场次回填 match_features 训练行
python manage.py train-model      # 用赛果标签训练 1X2（需 ≥ ML_MIN_TRAIN_SAMPLES）
python manage.py train-goals-model  # 用赛前盘口与终场进球训练 Poisson 分布
python manage.py upgrade-models   # 回填+重训 1X2/AH/进球，并刷新未完赛推荐（不打官方 API）
python manage.py refresh-pending-predictions  # 仅用本地盘口重算未完赛 leans
python manage.py model-status     # 查看 1X2 / 让球 / 进球分布模型及基线门禁
python manage.py backfill-ah-features  # 回填让球特征与 AH 标签
python manage.py train-ah-model   # 训练让球穿盘模型（需 ≥ ML_AH_MIN_TRAIN_SAMPLES）
python manage.py reset-match-history          # 预览：清空比赛/盘口/特征/日推（保留账号）
python manage.py reset-match-history --apply  # 执行清空，便于换盘口后从零攒 ML 样本
```

换盘口后从零攒样本（CLI + 管理员 UI）见 **[docs/RESET_MATCH_HISTORY.md](../docs/RESET_MATCH_HISTORY.md)**。

### 换机后启用模型

新电脑需先在 `backend/.venv` 中执行 `python -m pip install -r requirements.txt`，再依次运行：

```powershell
python manage.py init-db
python manage.py backfill-features
python manage.py backfill-ah-features
python manage.py train-model
python manage.py train-goals-model
python manage.py train-ah-model
python manage.py model-status
python -m unittest discover -s tests -v
```

已有本地数据库时，这些回填/训练命令不调用官方 API。完整的换机步骤、依赖检查及 pip SSL 故障处理见根目录 [`DEV_SETUP.md`](../DEV_SETUP.md)。

> **线上与本地对齐**：上述“重新训练”只保证使用云上样本产生一套可用模型，不保证与本机输出一致。首次上线若要求严格对齐，需停写后同时迁移 `data/football.db` 与整个 `data/models/`（1X2、AH、进球分布的权重及元数据），并保持相同代码提交、`ML_*` 配置、联赛目录和依赖版本。迁移后以服务器为唯一权威源，不在本地与线上分别训练后期待自动一致。

可触发的任务名：`scheduled_fixtures_sync`、`clean_old_data`、`train_model`。

### 概率模型（时间验证 + 基线门禁）

本地数据从现在起积累。链路：

1. 赛前分析写入 `match_features`（冻结特征 + 仅供审计的当时概率）
2. 赛果回写打 `label`；训练输入只使用赛前特征/盘口，标签只使用终场赛果，绝不把旧预测作为训练特征
3. `clean_old_data` 物理删除两类无统计价值的场次：**永远无法结算**的（取消、完场却无比分、延期且原定开赛已过 1 天——即使有完整赛前包也删，因为拿不到终场比分判不了命中），以及**已结算但无赛前 1X2 盘口**的（即使库里冻结过推荐也删：没有盘口的预测没有依据，属无效数据）；未开赛赛程与刚延期场次保留（盘口可能尚未开出）
4. 1X2 使用时间顺序 80/20 验证；拟合模型只有 log-loss 优于去水盘口基线才启用，否则 `source=market_baseline`

配置见 `.env`：`ML_MIN_TRAIN_SAMPLES`、`ML_AUTO_TRAIN`。

### 进球分布模型

`goal_predictor.py` 使用赛前 1X2、大小球、亚盘、近况等冻结特征，以终场主客进球为标签训练双 Poisson 模型：

1. `goal_features_json` 与主客进球标签持久化在 `match_features`，不依赖会被清理的展示数据
2. 时间验证总 MAE 必须优于常数均值基线，模型才标记为 `deployable`
3. 比分、大小球、BTTS 分别设门禁：对应验证指标必须胜过常见比分、盘口方向、类别多数基线
4. 未过门禁时**保留**盘口/启发式 lean，不覆盖成「待分析」；**无赛前 1X2 盘口时整包待分析**（胜平负/比分/大小/双进都不出结论）——盘口是全部玩法的推断依据，缺盘口时近况模型概率不构成依据，这类无效预测不写、不展示、不进统计
5. 固定同步批次回写新增赛果标签后自动重训；也可运行 `python manage.py upgrade-models`

### 让球模型（M-AH）

与 1X2 独立：`ah_predictor.py` 预测主侧穿盘概率，标签 `cover` / `no_cover`（走盘不训练）。

1. 赛前分析 / 赔率入库写入 `match_features` 的 AH 字段
2. 固定同步批次回写赛果并打 `ah_label`；样本 ≥ `ML_AH_MIN_TRAIN_SAMPLES`（默认 80）且有新增 → 自动训练
3. 推断优先级：结构性双选 > ML > multifactor 启发式（相对水位 + 1X2 分歧）

配置：`ML_AH_MIN_TRAIN_SAMPLES`、`ML_AH_AUTO_TRAIN`。
## API 接口

所有业务接口前缀为 `/api/v1`。完整请求/响应结构见 **[/docs](http://127.0.0.1:8000/docs)**。

### 公开接口

| 方法  | 路径                                | 说明                           |
|-----|-----------------------------------|------------------------------|
| GET | `/health`                         | 服务状态与缓存统计                    |
| GET | `/leagues`                        | 已配置联赛列表；可选 `date`、`days`；含今日/近期场次数 |
| GET | `/fixtures/today`                 | 赛程列表；可选 `league_id`、`date`、`days`（默认仅当天） |
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
| POST | `/admin/tasks/trigger` | 手动触发任务，body: `{"name": "scheduled_fixtures_sync"|"clean_old_data"|"train_model"}` |
| GET  | `/admin/settings/scheduled-full-detail` | 读取「定时全量详情」开关（DB 覆盖优先，否则 env） |
| PATCH | `/admin/settings/scheduled-full-detail` | 写入开关到 `app_settings`（body: `{"enabled": true\|false}`） |
| GET  | `/admin/settings/free-quota` | 读取「免费配额模式」开关（默认 ON；只改同步整点） |
| PATCH | `/admin/settings/free-quota` | 写入并立刻重排 cron；若从关→开且已过今日 11:00 则后台补跑一次同步 |
| GET  | `/admin/settings/api-sports-key` | 读取官方 Key 配置（数量 + 每枚末 4 位） |
| PUT  | `/admin/settings/api-sports-key` | 管理员密码确认后写入；body `{"password","keys"}`，`keys` 可逗号分隔多枚；空字符串清除库覆盖改回 env |
| POST | `/admin/reset-match-history` | 需**管理员账号登录** + body `{"password","apply"}`；`apply=true` 时物理清空 |

前端「我的 → 管理员设置」可配置官方 Key、切换免费配额/详情预拉，并用登录密码一键清空比赛历史。密钥见 [docs/API_SPORTS_KEYS.md](../docs/API_SPORTS_KEYS.md)；清空见 [docs/RESET_MATCH_HISTORY.md](../docs/RESET_MATCH_HISTORY.md)。

### 常用联赛 ID

**默认目录**：`config/leagues.json`（也可设环境变量 `LEAGUES_JSON`）——热门联赛与主要洲际/国际赛事，**筛选默认勾选**，盘口补全默认覆盖此范围。  
**非目录联赛**：赛程按日全量入库后，当日有赛但不在 `leagues.json` 的联赛自动出现在筛选勾选框（`extra` / 其他赛事）；勾选只影响本地显示，不触发官方请求。不再维护单独的次级目录文件。

API-Sports 没有跨国家统一可靠的“第几级联赛”字段，因此**默认勾选范围**由 `leagues.json` 按稳定 `league.id` 人工维护。条目字段：`name`（中文显示名）、`id`（API-Sports）、`country`；可选 `season`（如世界杯）、`region`（仅注释用，程序忽略）。修改后需**重启后端**。

筛选只展示所选日期在本地已有赛程的联赛，并按默认目录 / 其他联赛分组。固定批次按日**全量入库赛程**，盘口范围固定为 `leagues.json`，不受前端筛选影响。

热门目录覆盖：五大联赛 + 英冠/德乙/法乙/荷甲/荷乙/葡超/苏超/挪超/瑞典超 + 中超/日职联/韩K联/澳超/沙特联 + 美职联/巴甲/阿甲 + 欧冠/欧罗巴/欧协联/亚冠/亚冠精英/解放者杯/南美杯/世俱杯 + 世界杯/欧洲杯/欧国联/美洲杯/非洲杯/亚洲杯/金杯赛。完整 ID 以 `config/leagues.json` 为准。

赛程同步按官方 `date=` 拉当日全量赛事写入本地；`league_ids` 只约束盘口补全范围（默认热门目录）。

## 定时任务

应用启动时（`uvicorn main:app`）会自动注册并运行调度器：

| 任务                     | 触发规则      | 作用                                      |
|------------------------|-----------|-----------------------------------------|
| `scheduled_fixtures_sync` | 默认每天 **11:00** 全量 + **22:00** 盘口（免费配额模式）；关闭后恢复 00/06/11/16/19/22 | 免费模式 11:00 先回写昨天赛果并打标，再拉今天赛程与盘口；22:00 只刷新盘口并重算每日推荐；跳过积分榜、不拉未来比赛；关闭后才拉未来窗口与积分榜 |
| `clean_old_data`       | 每天 11:00 全量同步之后（管理员「立即同步」也会带上） | 物理删除「永远无法结算」（取消/无比分/延期过期）与「完场且无赛前盘口」（含有预测但无盘口的无依据预测）的场次、空联赛行与孤立球队，并清理过期分析与日志 |

时区由 `SCHEDULER_TIMEZONE` 控制（默认 `Asia/Shanghai`）。  
默认定时跑 **11:00** 全量与 **22:00** 盘口轻刷（管理员「打开免费配额」可关，恢复六个整点）。免费模式固定**先拉昨天赛果，再拉今天赛程/盘口，跳过积分榜、不请求未来比赛**（积分榜逐联赛拉取易耗光当日配额；排名读上一次本地快照）；22:00 只刷新今天热门联赛盘口并重算每日推荐。详情预拉即使另行开启也只覆盖今天。列表 / F5 / 筛选只读本地；用户打开详情时若展示包缺失，后端按需补拉并落库。无公开 sync、无 SSE、无轮询。
手动：`python manage.py trigger-task --name scheduled_fixtures_sync`。

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
先执行 `python manage.py fetch-upcoming`，或等待后端定时任务 / 刷新前端页面触发同步。

**API 配额不足**  
用 `python manage.py check-quota` 查看剩余次数；缓存开启后可减少重复请求。
