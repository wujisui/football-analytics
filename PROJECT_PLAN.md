# Football Analytics 项目计划书

> 更新日期：2026-07-21  
> 仓库：`football-analytics`（`backend/` + `frontend/`）  
> 定位：**赛前分析产品**，不是实时比分站

---

## 1. 产品目标（已明确）

### 1.1 要做什么

面向联赛与杯赛的**赛前分析**：在开赛前准备并展示决策相关数据，给出胜平负倾向与推荐。

核心数据（开赛前准备、写入本地库）：

| 数据项       | 说明                      |
|-----------|-------------------------|
| 赛前赔率      | 开赛前赔率变化，用于辅助判断          |
| 历史交锋      | 双方近期交手记录                |
| 近期战绩 / 近况 | 用于概率与展示                 |
| 阵容        | 首发阵型与名单                 |
| 伤病        | 双方伤停信息                  |
| 替补        | 替补席名单                   |
| 分析结果      | 主胜 / 平局 / 客胜概率、置信度、推荐方向 |

数据价值边界：未开赛赛程一律保留（盘口可能尚未开出）。仅当比赛已完场，且既无赛前 1X2 盘口也无算法推荐时，才物理删除该场及其关联分析数据。训练样本仍只使用有盘口的完场场次。

### 1.2 明确不做

| 不做            | 原因                                       |
|---------------|------------------------------------------|
| 实时比分 / 滚球直播   | 产品不是直播站，配额与架构都不按此设计                      |
| 开赛后轮询官方比分     | 赛果按日一次性回写，不做滚球                            |
| 开赛后改写赛前预测快照   | 预测审计字段冻结；展示数据缺则按需补拉                      |
| 前端直连官方并暴露 Key | Key 放后端 / `secrets.local.env`，前端只调自有 API |

### 1.3 数据与配额原则

```
开赛前：按距开赛远近，偶尔刷新官方 → 写入本地
开赛后：预测快照冻结；详情展示缺数据时仍可按需拉官方（不轮询比分）
赛果：对已入库场次可按日历日一次性回写终场比分（非滚球）
前端：始终只调本项目后端；列表加载只读本地库，用户点击工具栏「同步」时才走 `POST /fixtures/sync`
联赛范围：`backend/config/leagues.json` 为各国顶级联赛 + 主要洲际赛事的默认同步目录；`leagues.example.json` 为次级/其他可选目录，只有筛选勾选后才同步
```

| 距开赛      | 分析侧刷新间隔（可配置）            |
|----------|-------------------------|
| > 72 小时  | 约 24 小时（远期赛程可提前准备，如世界杯） |
| 24–72 小时 | 约 12 小时                 |
| 6–24 小时  | 约 3 小时                  |
| 0–6 小时   | 约 1 小时                  |
| 已开赛或已结束  | **预测快照不再刷新**；详情展示包缺则按需补拉；赛果可按日一次性回写 |

读取顺序：`Redis` → `SQLite（api_snapshots / pre_match_data）` → `API-Sports`（本地缺展示数据时，含完场复盘详情）。

鉴权：优先 **API-Sports 官方 Key**（`API_SPORTS_KEY`），RapidAPI 仅作备用。

---

## 2. 当前进度总览

| 模块               | 进度      | 说明                                          |
|------------------|---------|---------------------------------------------|
| 后端骨架与配置          | ✅ 完成    | FastAPI、配置、日志、CORS、健康检查                     |
| 数据模型与 SQLite     | ✅ 完成    | 联赛 / 球队 / 赛程 / 赛前分析 / API 快照                |
| 官方数据拉取           | 🟡 部分完成 | 联赛/球队/赛程/H2H/近况/统计已接；赔率/阵容/伤病已接并落库（视官方是否有数据） |
| 本地优先与 TTL        | ✅ 完成    | 落库、开赛后冻结、按开赛时间刷新                            |
| 赛前概率分析           | 🟡 持续优化 | 训练只使用冻结赛前特征/盘口与终场标签；1X2 必须优于盘口基线才启用，否则直接采用盘口隐含概率；比分/大小球/BTTS 使用独立 Poisson 进球分布模型；让球独立训练 |
| 业务 API           | ✅ MVP   | leagues / today / sync（含按日批量赔率） / results / analysis / admin |
| 定时任务             | ✅ 完成    | **每日 06:00 / 12:00 / 18:00 赛程同步（初盘冻结）**、赛前窗口、赛果回写（含自动 train）、清理 |
| 密钥管理             | ✅ 完成    | `secrets.local.env`（不进 Git）                 |
| 前端展示             | 🟡 MVP  | 联赛 → 今日赛程 → 详情（概率 + 赛前包分区）                    |
| 赛前详情页（赔率/阵容/伤病等） | 🟡 进行中 | API `package` + 前端分区已接；官方 `/predictions`→「赛前简报」Tab；依赖官方开盘/公布阵容/简报覆盖 |
| 官方 Widgets       | ❌ 未做    | 可选增强，非必须                                    |
| 测试 / 部署          | 🟡 部分完成 | 已补进球模型单测；生产部署方案仍未完成                         |

**整体判断：M4 主链路已通；阶段 M 已形成「冻结赛前输入 → 终场标签 → 时间验证 → 基线门禁 → 自动重训」闭环。**

---

## 3. 已完成（Done）

### 3.1 工程与基础设施

- [x] Monorepo：`backend/` + `frontend/`
- [x] FastAPI 应用入口、CORS、生命周期内启动调度器
- [x] SQLAlchemy 异步 + SQLite（`data/football.db`）
- [x] Redis 缓存，不可用时降级 fakeredis
- [x] 本地密钥：`secrets.local.env` + `.gitignore`（避免 Key 进仓库）
- [x] API-Sports 直连鉴权（`x-apisports-key`），兼容 RapidAPI 回退
- [x] 根目录 / 后端 / 前端 README

### 3.2 数据与联赛覆盖

- [x] 模型：`League` / `Team` / `Fixture` / `PreMatchData` / `MatchFeature` / `ApiSnapshot`
- [x] 配置联赛：英超、西甲、德甲、意甲、法甲、欧冠、欧罗巴、亚冠、中超、美职联、巴甲、日职联(J1)、韩K联(K1)
- [x] CLI：`init-db`、`fetch-leagues`、`fetch-today`、`check-quota`、`test-api`、缓存与任务相关命令

### 3.3 本地优先与赛前冻结策略

- [x] 官方响应写入 `api_snapshots`，业务优先读本地
- [x] 分析结果写入 `pre_match_data`
- [x] 按开赛时间动态刷新；**开赛后 / 结束后预测快照冻结**；详情展示包缺则按需补拉
- [x] 回溯已结束比赛：读本地库

### 3.4 分析与 API（MVP）

- [x] 胜平负概率：拟合模型仅在时间验证集优于盘口基线时启用，否则使用去水后的盘口隐含概率
- [x] 比分/大小球/双方进球：由赛前 1X2、大小球、亚盘及近况训练 Poisson 进球分布，不再从旧预测回灌训练
- [x] 置信度、推荐方向
- [x] `GET /api/v1/health`
- [x] `GET /api/v1/leagues`
- [x] `GET /api/v1/fixtures/today`
- [x] `GET /api/v1/fixtures/{id}/analysis`
- [x] 管理接口：任务状态 / 手动触发（`X-Admin-Key`）

### 3.5 调度

- [x] `scheduled_fixtures_sync`：每日 06:00 / 12:00 / 18:00 拉取近期赛程 + 缺盘补全；首次盘口冻为初盘，手动同步为即时盘
- [x] `pre_match_update`：开赛前窗口内更新（默认 2 小时内）
- [x] `capture_results`：按日回写终场比分 + 打标 + 条件自动 train
- [x] `clean_old_data`：物理删除「已完场且无赛前 1X2、也无算法推荐」的场次及关联数据；清理空联赛行、孤立球队与过期展示分析/日志
- [x] `train_model`：可手动触发训练
### 3.6 前端 MVP

- [x] Vue 3 + Vite + TypeScript + Naive UI + ECharts
- [x] 页面：联赛列表 → 今日赛程 → 单场概率分析
- [x] 开发代理：`/api` → 后端 `8000`

### 3.7 赛前数据包（M4 主链路）

- [x] 官方 `/odds`、`/fixtures/lineups`、`/injuries` 拉取（本地优先缓存）
- [x] `pre_match_data` 扩展 JSON 字段并落库
- [x] `GET /fixtures/{id}/analysis` 返回 `analysis.package`
- [x] 前端详情页分区：赔率、交锋、近况、阵容/替补、伤病、官方赛前简报
- [x] 今日列表分析不拉完整包（省配额）；首页筛选展示本地未完赛联赛（未开盘仍可见）；不再靠全球发现扫出一堆无价值联赛选项
- [x] **ML 概率模型（带基线门禁）**：赛前特征落库、赛果打标、时间切分验证；1X2 未优于盘口时不部署
- [x] **进球分布模型**：持久化 `goal_features_json` 与终场进球标签；Poisson 模型驱动比分、大小球、BTTS，且验证 MAE 必须优于常数基线

---

## 4. 未完成 / 缺口（Not Done）

下列项属于**已明确需求但尚未闭环**（或仅有字段/拉取未用于产品）。

### 4.1 赛前数据闭环（高优先级）

| 需求     | 现状                                       | 缺口                        |
|--------|------------------------------------------|---------------------------|
| 赛前赔率   | 中午任务冻**初盘**（`odds_opening_json`）；强制 sync / 详情补拉写**即时盘**（`odds_json`）并重算 1X2；缺盘补全 | 官方未开盘仍空态 |
| 阵容（首发） | 已接 lineups，落库并展示                         | 临场前官方可能无数据               |
| 替补     | 已随 lineups 解析 `substitutes` 并展示           | 同上                      |
| 伤病     | 已接 `/injuries` 并展示                         | 部分联赛覆盖不全                 |
| 历史交锋展示 | 已进 API `package` + 详情页                      | 已入多因子概率（`h2h_*`）           |
| 近况展示   | 已进 API `package` + 详情页                      | 已入多因子 + 连胜/连败均值回归特征     |
| 球队统计   | 已拉取                                      | 未进入公式，未展示                 |
| ML 推荐  | ✅ 赛前特征/盘口入库 → 赛果打标 → 时间验证 → 优于基线才部署；预测快照仅用于审计，不作为训练输入 | 继续积累分联赛与置信度样本；见 §5 阶段 M |

### 4.2 产品能力增强

| 需求                 | 现状                      |
|--------------------|-------------------------|
| 未来 N 日赛程（非仅今日）     | 未做；远期准备依赖扩展拉取           |
| 积分榜 / 场地 / 教练      | 未做（可选）                  |
| 赛果查询页 / 终场比分落库    | ✅ 已做：`/results` + sync/capture_results |
| 分析模型升级             | ✅ 1X2 基线门禁 + Poisson 进球分布已上线；继续积累样本与校准 |
| 球队 Logo            | 库中有 `logo_url`，API/前端未用 |
| API-Sports Widgets | 未集成（可选，注意 Key 暴露）       |

### 4.3 工程化

| 需求                   | 现状                         |
|----------------------|----------------------------|
| 自动化测试                | 无                          |
| 生产部署（Docker / Nginx） | 无                          |
| 本机数据迁云 / 备份策略       | 无；数据在 `backend/data/football.db`（gitignore），需手动拷或云上重拉（见阶段 D.2） |
| CI                   | 无                          |
| `pandas` / `numpy`   | `numpy` 已用于概率模型训练；`pandas` 仍可清理 |

---

## 5. 将来要做（Roadmap）

按优先级分阶段；完成前一阶段再开下一阶段。

### 阶段 M — 本地训练、基线门禁与自动重训（进行中 · 当前重点）

> **前提**：本地库从现在才开始持续入库，不以历史赛季回灌为前提。  
> **策略**：训练输入只允许冻结赛前特征/盘口，标签只允许终场赛果；预测快照只负责审计。模型达到样本阈值后自动训练，但必须在时间验证集优于对应基线才部署。

#### M.1 数据闭环（已实现，持续跑）

```
赛前分析 → 写 pre_match_data（展示）+ match_features（冻结训练特征/预测审计快照）
     ↓
赛果回写（capture_results）→ 写 1X2 / AH / 主客进球标签
     ↓
样本数 ≥ ML_MIN_TRAIN_SAMPLES（默认 30）且有新增标签
     ↓
自动 train → 时间验证并与盘口/常数基线比较 → 合格 artifact 才部署
不合格时 → 1X2 使用盘口隐含概率；进球分布保留旧规则兜底
```

| 能力 | 状态 | 说明 |
|------|------|------|
| 赛前特征入库 | ✅ | `match_features`（近况/回归/H2H/盘口等） |
| 预测快照入库 | ✅ | 同表记录当时胜平负概率与 `model_source` |
| 赛果打标 | ✅ | `capture_finished_results` 后写 `label` |
| 价值数据清理 | ✅ | `clean_old_data` 只删「完场且无盘口、也无推荐」的场次；未开赛赛程保留 |
| 盘口基线输出 | ✅ | 1X2 拟合模型未胜过盘口时直接采用去水盘口概率 |
| 进球分布输出 | ✅ | Poisson 模型独立评估主客进球、比分、O/U 与 BTTS；各目标单独战胜基线才输出，否则待分析 |
| 自动训练 | ✅ | `capture_results` / `scheduled_fixtures_sync` 后可 `maybe_auto_train_model` |
| 自动切换推断 | ✅ | 有合格 artifact 时才切 ML，不以“样本够”代替“效果好” |
| 运维命令 | ✅ | `backfill-features` / `train-model` / `train-goals-model` / `model-status` |

配置：`ML_MIN_TRAIN_SAMPLES`（默认 30）、`ML_AUTO_TRAIN`（默认 true）。

#### M.2 积累期要做的事（产品侧）

1. 保持日常 sync / 赛前分析 / 赛果回写正常跑，让标签自然增长  
2. 用 `python manage.py model-status` 看 `match_features_labeled` 与 `inference_mode`  
3. **不要**在样本很少时强行调低阈值冒充「已上 ML」；阈值可配，但建议 ≥30  

#### M.3 样本够了之后（自动完成，无需手切）

1. 首次达到阈值 → 自动训练 → 仅验证优于基线的新分析走 `ml`  
2. 之后有新增赛果标签 → 自动重训（`labeled > last_trained_n`）  
3. 人工可随时：`manage.py train-model` 或 `trigger-task --name train_model`  

#### M.4 后续完善（有数据后再做，不挡当前）

| 项 | 说明 |
|----|------|
| 命中率对比看板 | 多因子 vs 拟合模型 vs 盘口基线（复用 `results_accuracy`） |
| 特征增强 | 主客分拆近况、阵容质量、联赛强度编码 |
| 模型升级 | 样本数百场后可换 GBDT + 概率校准 |
| 历史回灌（可选） | 配额允许时按赛季补历史，缩短积累时间；非必须 |
| API/前端标注 | 展示当前 `market_baseline` / `ml` / `poisson_ml` 来源 |

#### M.5 串关推荐（**门禁：ML 就绪后再做**）

> **不做时机**：模型尚未稳定战胜盘口基线时——单场优势不足，2～8 串会放大误差，产品价值低。  
> **开门条件**（建议同时满足）：  
> 1. 推断已稳定 `source=ml`（`model-status` 显示合格 artifact）  
> 2. 标签样本明显超过训练阈值（建议再攒一批赛果后再开，避免刚切 ML 就串关）  
> 3. 赛果页已能对照评估单场命中（便于串关复盘）

| 项 | 说明 |
|----|------|
| 产品 | 独立「串关」页：2～8 串 1；展示算法推荐组合（非滚球跟单） |
| 优化目标 | 先定一种主目标（最高联合命中 / 相对盘口期望价值 / 带约束最优），可多档 |
| 算法 | 候选场次上近似搜索（贪心 / beam / ILP）；默认场次独立乘积；注明偏乐观 |
| 数据 | **只读本地** ML 概率与盘口；不为串关额外打官方接口 |
| 约束 | 开赛后冻结；联赛分散、单场概率下限等可配 |
| 验收 | 给定日期 + \(k\) 返回 Top N；与单场 `ml` 概率一致可复算 |

列入里程碑 **M7**（见 §6）；**不**挤占当前阶段 M 积累与自动切换。

### 阶段 M-AH — 让球穿盘 ML（规划 · 接在阶段 M 之后）

> **动机**：1X2 与让球是不同市场；同一天可既有「主胜 + 让球负」（主让 -0.5 主侧高水）又有「客胜 + 让球胜」（主受让 +0.5 主侧低水）。写死水位规则无法稳定覆盖，需单独学 **「主队是否穿盘」**。  
> **原则**：与 1X2 ML 同架构——本地积累标签 → 样本够自动训练 → 推断切换；**不足样本时保留极简规则兜底**（仅结构性双选 + 无盘口空态）。  
> **不做**：滚球让球、多庄家套利、实时水位跟踪。

#### M-AH.1 问题定义

| 项 | 约定 |
|----|------|
| 预测目标 | 赛前快照时刻 **主盘 Asian Handicap** 上，主队是否 **穿盘**（cover） |
| 标签 `ah_label` | `cover` \| `no_cover`；整球线走水 `push` **不入训**（或单独三分类，首版二分类+过滤） |
| 结算 | 90 分钟比分 + 赛前冻结 `ah_line`：`home_adj = home_goals + line`，与 `away_goals` 比大小 |
| 主盘选取 | 与列表/详情展示一致：取 `pre_match_data.odds_json`（或 `odds_opening_json`）中 **第一条有效 AH 线**；分析时冻结写入特征行 |
| 与 1X2 关系 | **独立模型**；输出可与 `recommendation` 并存，UI 标明「赛果推荐 vs 赢盘推荐」 |

典型分歧（必须靠模型/特征学，不宜写死）：

- 1X2 主胜，主让 -0.5 但 **主侧水位 > 客侧** → 市场看「难穿盘」  
- 1X2 客胜，主受让 +0.5 但 **主侧水位 < 客侧** → 市场看「主队不败穿盘」  

#### M-AH.2 特征（`AH_FEATURE_VERSION = ah_v1`）

在现有 `FEATURE_NAMES`（1X2）基础上 **追加** 让球专用列（训练/推断向量分开或拼接，推荐 **拼接同一行** 便于 join）：

| 分组 | 特征 | 说明 |
|------|------|------|
| 盘口 | `ah_line` | 有符号让球线（主让为负），归一化到约 [-2.5, +2.5] |
| 盘口 | `ah_home_odd`, `ah_away_odd` | 主盘两侧欧赔 |
| 盘口 | `ah_water_diff` | home − away（正 → 主侧相对高水） |
| 盘口 | `ah_implied_cover` | 由两侧赔率反推的穿盘概率（去 margin 后） |
| 盘口 | `ah_line_abs`, `ah_line_shallow`, `ah_line_deep` | 浅/中/深盘 one-hot 或 tier 标量 |
| 交叉 | `mx_home_prob`, `mx_draw_prob`, `mx_away_prob` | 当时 1X2 模型输出（或赔率隐含） |
| 交叉 | `mx_vs_ah_gap` | 1X2 主胜概率 − AH 穿盘隐含（市场分歧强度） |
| 联赛 | `league_tier_top5`, `league_tier_asia`, … | 与 `league_names`/配置 ID 桶一致，避免每联赛 one-hot 过稀 |
| 元 | `has_ah_market` | 是否有有效 AH（无则 whole-head 不输出） |

**不新增官方 API 调用**；特征全部来自已有赛前包 + 当时 1X2 推断。

#### M-AH.3 数据与表结构

**方案（推荐）**：扩展 `match_features` 同表同行，避免双表 join。

| 字段 | 类型 | 说明 |
|------|------|------|
| `ah_line` | Float, nullable | 冻结主盘线 |
| `ah_home_odd`, `ah_away_odd` | Float, nullable | 冻结主盘水位 |
| `ah_features_json` | Text, nullable | `AH_FEATURE_NAMES` 有序 JSON |
| `ah_label` | String(12), nullable | `cover` / `no_cover` / `push` |
| `ah_cover_prob` | Float, nullable | 推断时 P(cover) |
| `ah_model_source` | String(32), nullable | `rules` / `multifactor` / `ml` |

`feature_version` 仍为 1X2 的 `v1`；让球版本用 **`ah_feature_version=ah_v1`** 独立演进。

**写入时机**（与 1X2 对称）：

```
赛前分析 / 赔率入库后
  → extract_ah_features(package, probs_1x2)
  → persist_match_features(..., ah_*)
赛果回写 capture_results
  → settle_ah_label(home_goals, away_goals, ah_line)
  → 写 ah_label（push 可写 NULL 或 push 字符串）
```

**回填**：`manage.py backfill-ah-features` — 从已有 `pre_match_data.odds_json` + 完场比分补历史行（本地库有则做，**不**为回填打官方 API）。

#### M-AH.4 模型与训练

| 项 | 首版 | 样本多后 |
|----|------|----------|
| 算法 | **二元 Logistic**（与 1X2 softmax 并列） | 可选 GBDT + Platt 校准 |
| artifact | `data/models/ah_v1_weights.npz` + `ah_v1_meta.json` | 同路径版本递增 |
| 阈值 | `ML_AH_MIN_TRAIN_SAMPLES` 默认 **80**（二分类，且需覆盖多档盘口） | 可调 |
| 切训条件 | `ML_AH_AUTO_TRAIN=true` 且 labeled 行数 ≥ 阈值且较上次训练有新增 | 同 1X2 |
| 验证 | **按日期 hold-out**（禁止随机打乱同联赛同日） | 分 league_tier、分 line tier 报准确率 / Brier |
| 基线对比 | ① 永远跟低水一侧 ② 当前规则层 ③ 仅 `ah_implied_cover` | 赛果页加 AH 命中统计 |

**推断优先级**：

```
无 AH 盘口 → handicap_lean = 「缺少盘口数据分析」
有 artifact 且 source=ml → P(cover) → 让球胜/负 + 「模型穿盘 xx%」
样本不足 → multifactor 启发（相对水位 + 1X2 分歧，规则极简）
```

**产品输出示例**：

```
让球负（-0.5）· 模型穿盘 38%（与胜平负「主胜」分歧）
让球胜（+0.5）· 模型穿盘 61%
```

#### M-AH.5 代码落点（实现时）

| 模块 | 职责 |
|------|------|
| `backend/app/services/ah_features.py` | `extract_ah_features`, `settle_ah_label`, `AH_FEATURE_NAMES` |
| `backend/app/services/ah_predictor.py` | 训练/推断/持久化；镜像 `ml_predictor.py` 结构 |
| `backend/app/services/prediction.py` | `handicap_lean` 改为 **调 ah_predictor**；删除或降级冗长水位 if-else |
| `backend/app/services/ml_predictor.py` | 不变；1X2 与 AH **解耦** |
| `backend/app/models/match_feature.py` | 新增 AH 列（迁移） |
| `backend/app/tasks/scheduler.py` | `capture_results` 后 `maybe_auto_train_ah_model` |
| `manage.py` | `backfill-ah-features`, `train-ah-model`, `model-status` 展示 AH 段 |
| 前端 | `handicap_lean` 展示理由；可选 badge「ML 让球」 |

#### M-AH.6 里程碑与门禁

| 步骤 | 交付 | 门禁 |
|------|------|------|
| AH-0 | 标签结算函数 + 单元测试（含 -0.5 / +0.5 / -1.5 走水） | 无 |
| AH-1 | 特征提取 + 分析/赔率入库时写入 + backfill 命令 | 本地可看到 `ah_label` 计数 |
| AH-2 | 训练 CLI + 自动训练钩子 + `model-status` | labeled ≥ 80 |
| AH-3 | `handicap_lean` 切 ML 推断；规则仅兜底 | 验证集优于「跟低水」基线 |
| AH-4 | 赛果页 **让球命中率**（cover 预测 vs 实际） | 与 1X2 命中率并列 |

**与阶段 M 关系**：1X2 ML 继续积累；**不等待** 1X2 切 `ml` 才开 AH——两者标签同源、可并行攒样本。  
**与 M.5 串关关系**：串关仍门禁在 1X2 ML；让球 ML 稳定后可把 AH 作为串关第二市场（**M7 扩展**，另议）。

#### M-AH.7 积累期操作（现在起）

1. 保持 sync / 分析 / `capture_results` 运行，确保 **`odds_json` 含 AH 主盘** 且完场比分齐全  
2. 实现 AH-0～AH-1 后跑 `backfill-ah-features`，用 `model-status` 看 `ah_labeled`  
3. **未达 80 条前**：前端仍见规则/占位 `handicap_lean`，产品文案注明「让球模型积累中」  
4. 达标后部署 AH-2～AH-3，用你提供的「同日主客分歧盘」样例做回归验收  

### 阶段 A — 赛前数据包

目标：一场比赛详情页能看到「分析 + 交锋 + 近况 + 赔率 + 阵容/伤病/替补」，且全部来自本地库。

1. 后端接入并落库  
   - `/odds`（赛前赔率）  
   - `/fixtures/lineups`（首发 + 替补）  
   - `/injuries`（伤病）  
2. 扩展 `pre_match_data`（或关联表）持久化上述结构化数据  
3. 扩展 `GET /fixtures/{id}/analysis`（或拆分子资源）返回完整赛前包  
4. 前端详情页分区展示：概率、赔率、H2H、近况、阵容、伤病、替补  
5. 开赛后仍只读本地，不刷新官方  

> 主链路已通；空态取决于官方是否开盘/公布阵容。

### 阶段 B — 准备窗口与调度对齐

1. 支持拉取「未来 N 天」赛程（世界杯等提前准备）  
2. 调度与 TTL 策略对齐：远期少拉、临场多拉、开赛后停拉  
3. 将 H2H / 赔率 / 伤病等作为冻结赛前特征；拟合模型必须通过时间验证并战胜盘口基线才接管  
4. 置信度与数据完整度更真实地反映「数据包是否齐全」  

### 阶段 C — 体验与可选增强

1. 积分榜、场地、教练等辅助信息（按需）  
2. 球队 Logo、更完整的联赛/比赛列表筛选  
3. 评估是否嵌入官方 Widgets（仅展示层；Key 需域名限制或代理）  
4. 管理后台简易页（触发任务、看配额）  

### 阶段 D — 工程化与上线

1. 单元测试 / 接口测试（fetcher、analyzer、TTL、API）  
2. Docker Compose（backend + redis + frontend 静态资源）  
3. 清理无用依赖；完善生产环境变量说明  
4. 监控：配额剩余、任务失败告警、**ML 样本数 / inference_mode**  
5. **本地数据 → 云服务器迁移与持久化（勿漏）** — 见下方 D.2  

#### D.2 数据落盘位置与迁云策略

> 产品当前**没有**内置「本机 ↔ 云」自动同步。持久化是单机文件；上线前必须显式处理，否则云上是空库、ML 标签也会丢。

**本机落盘（开发默认）**

| 路径 | 内容 | 是否进 Git |
|------|------|------------|
| `backend/data/football.db` | 联赛/赛程/`pre_match_data`/`match_features`/`api_snapshots` | ❌（gitignore） |
| `backend/data/models/` | 拟合 1X2 权重（样本够后才有） | ❌（gitignore） |
| `backend/secrets.local.env` | API Key / Admin Key | ❌（严禁提交） |
| `backend/logs/` | 运行日志 | ❌ |

热缓存默认 `REDIS_ENABLED=false`（内存），**不落盘**，迁云时不必拷。

**首次上云（二选一，写进发布清单）**

| 方案 | 做法 | 适用 |
|------|------|------|
| A. 整库拷贝 | 停写后拷 `football.db`（+ 可选 `data/models/`）到服务器同路径；服务器单独配置 `secrets.local.env` | 要带走本机已积累的赛果/ML 标签 |
| B. 云上重拉 | 只部署代码 + Key；`init-db` → fetch/sync → 调度自行积累 | 干净环境；本机标签不迁移 |

约束：

- **禁止**把 `football.db` / Key 提交进 Git 当「同步」手段  
- 本机与云**不要长期双写**同一逻辑库；上线后以**服务器为权威源**，本机仅作开发或单向备份  
- 拷库前尽量停掉两边写库进程，避免 SQLite 半写入损坏  

**上线后日常（阶段 D 交付时应具备）**

1. 服务器数据目录挂持久卷（Docker volume / 主机目录），重启不丢库  
2. 定期备份 `football.db`（及 `data/models/`）到对象存储或异地；保留保留点  
3. 文档化：从备份恢复的步骤；`DATABASE_URL` / `ML_*` / Key 的生产配置清单  
4. （推荐演进）生产改 **PostgreSQL**（或同等），减少单文件拷贝与并发限制；SQLite 可留作本地开发  

**M6 验收补充**：发布说明中必须写清「权威数据在哪、如何备份、首次是方案 A 还是 B」。

---

## 6. 里程碑建议

| 里程碑        | 完成标准                         | 状态     |
|------------|------------------------------|--------|
| M0 工程骨架    | 服务可启动、健康检查通过                 | ✅      |
| M1 数据 MVP  | 联赛 + 今日赛程入库，前端可浏览            | ✅      |
| M2 分析 MVP  | 单场胜平负概率 + 推荐可展示              | ✅      |
| M3 本地优先    | 落库、开赛后冻结、密钥本地化               | ✅      |
| M4 赛前数据包   | 赔率 + 阵容 + 伤病 + 替补 + H2H 展示闭环 | 🟡 进行中（主链路已通） |
| M5 模型与调度增强 | 本地积累闭环 + 自动训练切换（未来赛程准备仍缺） | 🟡 阶段 M 进行中 |
| M5-AH 让球 ML | 穿盘标签 + AH 特征 + 二元模型；`handicap_lean` 切 ML（见 M-AH） | ⬜ 已规划 |
| M6 可上线     | 测试 + 部署 + 配额可控 + **数据迁云/备份策略落地（D.2）** | ⬜      |
| M7 串关推荐   | 2～8 串 1 最优组合页；**仅 ML 稳定输出后**（见阶段 M.5） | ⬜ 门禁未开 |

---

## 7. 技术栈与关键路径

| 层   | 技术                                                                        |
|-----|---------------------------------------------------------------------------|
| 后端  | FastAPI · SQLAlchemy · SQLite · Redis/fakeredis · APScheduler · httpx     |
| 前端  | Vue 3 · Vite · TypeScript · Naive UI · ECharts · Axios                    |
| 数据源 | API-Sports（`v3.football.api-sports.io`），Key 存 `backend/secrets.local.env` |

本地启动见根目录 [README.md](README.md)；后端细节见 [backend/README.md](backend/README.md)；前端见 [frontend/README.md](frontend/README.md)。

---

## 8. 风险与约束

| 风险           | 应对                                   |
|--------------|--------------------------------------|
| 官方 API 日配额有限 | 本地优先 + 开赛后冻结 + 按开赛时间刷新               |
| Key 泄露       | 仅本地 `secrets.local.env`；勿提交 Git；勿写前端 |
| 阵容/赔率临场才稳定   | 临场窗口提高刷新频率，但仍在开赛前停止                  |
| 分析模型过简       | 1X2 设盘口基线门禁；比分/O-U/BTTS 使用独立进球分布；让球单独训练 |
| 串关过早上线       | 门禁见 M.5：须 `source=ml` 且样本充足后再做；乘积假设偏乐观 |
| 上云丢库 / 双写冲突  | 明确权威源；整库拷或云上重拉（阶段 D.2）；禁止用 Git 同步 db |
| SQLite 单文件 concurrent | 单实例部署；生产演进 Postgres + 卷备份           |

---

## 9. 文档维护

- 本文档随阶段推进更新「已完成 / 未完成 / 将来要做」勾选状态。  
- 产品边界变更（例如是否做直播）须先改本文第 1 节，再改代码。  
- 接口细节以运行中的 `/docs` 与代码为准；本文描述进度与规划，不替代 OpenAPI。
