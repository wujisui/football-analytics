# 前端 UI 需求说明（赛前分析）

> 本文档描述前端页面结构、交互与对接约定，供实现与迭代对照。  
> 接口字段以运行中的后端 OpenAPI / 代码为准；下文示例仅作说明。  
> 产品边界见仓库根目录 `PROJECT_PLAN.md`。  
> API 约定见 `.cursor/rules/frontend-api.mdc`。  
> **Naive UI 组件优先与全屏布局**见 `.cursor/rules/frontend-ui.mdc`（开发时必须遵守）。

---

## 1. 产品与技术背景

- **定位**：轻量级**赛前**分析工具，只关注未开赛（`pending`）比赛；不是实时比分站。
- **特色**：赛前盘口与本地算法给出胜平负等倾向；详情「我的预测」用盘口解释文案对照算法结论。
- **前端栈**：Vue 3 + TypeScript + Vite + Vue Router + Axios + Naive UI + ECharts。
- **后端**：本项目 FastAPI，开发时代理 `/api` → `http://127.0.0.1:8000`；基址 `VITE_API_BASE_URL` 或默认 `/api/v1`。
- **禁止**：前端存放或直连 API-Sports / RapidAPI Key。
- **UI**：全屏 `n-layout`；侧栏 / 顶栏固定，内容区滚动；优先使用 Layout、Menu、Breadcrumb、PageHeader 等组件，避免手写平行布局。
- **多端**：手机 / 平板可用（侧栏抽屉、双栏改单列、安全区）；不依赖 Tailwind。

---

## 2. 路由

| 路径                    | 名称               | 页面       |
|-----------------------|------------------|----------|
| `/`                   | —                | 重定向到计算器 |
| `/predictions`        | `predictions`    | 预测与投注计算器 |
| `/results`            | `results`        | 赛果（按日期）  |
| `/favorites`          | `favorites`      | 关注场次（手机底栏入口） |
| `/mine/*`             | `mine-*`         | 我的（关注 / 方案 / 偏好 / 关于） |
| `/fixture/:fixtureId` | `fixture-detail` | 比赛详情     |

兼容重定向：

- `/leagues/:leagueId` → `/predictions?league=:leagueId`
- `/plans` → `/mine/plans`
- `/fixtures/:fixtureId` → `/fixture/:fixtureId`

查询参数：`/predictions?league=<league_id>` 表示计算器按联赛筛选；无参数表示「全部」。

顶栏导航：桌面为 **计算器** / **赛程**，未登录显示 **登录**（弹窗表单），登录后才出现 **我的**；手机底栏为 **计算器** / **赛程** / **关注** / **我的**。关注页沿用赛程未来日期的单日卡片列表样式，并仍可从「我的 → 本地数据 → 关注」进入；「我的方案」只从「我的」进入。计算器桌面为赔率/预测（含让球主盘行，多盘悬停展开）、可选玩法、投注详情三列；手机为场次玩法列表 + 选中后底部固定投注摘要。

---

## 3. 页面一：计算器（唯一赛前列表）

### 3.1 布局（全屏 Layout）

应用壳占满视口。计算器使用 `n-layout has-sider`：

| 区域    | 组件 / 行为                                             |
|-------|-----------------------------------------------------|
| 左侧联赛  | 桌面：`n-layout-sider`（约 232px，可折叠）+ `n-menu`；平板默认折叠；手机改为顶栏「联赛」+ 左侧 `n-drawer` |
| 右侧工具条 | `n-breadcrumb` + `n-page-header`（标题、场次、刷新）          |
| 右侧列表  | `n-layout-content` 内滚动；卡片纵向排列，间距约 12–16px           |

### 3.2 数据加载（重要）

1. 进入计算器时**并行**请求：
   - `GET /api/v1/leagues?days=7`
   - `GET /api/v1/fixtures/today?days=7`（**不传** `league_id`，一次拉全量近期赛程）
2. 默认选中左侧 **「全部」**，右侧展示全部 `status === pending` 的比赛。
3. 点击某个联赛时：**不再请求接口**，在已加载的全量列表上按 `league_id` **本地筛选**。
4. 左侧数量角标：优先用本地 pending 场次统计（与右侧一致），避免「联赛有入库场次但右侧为空」的错觉。
5. **每个浏览器会话首次打开**自动跑一次 `POST /api/v1/fixtures/sync`（绕过 Redis/SQLite 日缓存打官方）；杀页冷启动若会话仍在则不再自动打官方，只读本地库。列表期间照常展示本地内容，落库后自动重拉本地列表。需要更新时在计算器 / 赛程列表**下拉刷新**（列表顶提示文案）。
6. 勾选到本次同步范围外的联赛时，按 `odds_only` 单独补拉该联赛盘口。

### 3.3 左侧联赛菜单

- 使用 `n-menu`；首项 **全部**，其后各联赛；数量用 `n-badge`
- 当前项高亮；不同联赛可用色点区分
- 面包屑：`赛前赛事` / `全部` 或当前联赛名

### 3.4 右侧比赛列表

- 仅展示未开赛（pending）；开赛后归赛果列表
- 按开赛时间从近到远排序，并按**本地日历日**分组（`n-divider` 显示日期+星期）
- 顶栏「全部比赛」行右侧：`n-date-picker`（可清空，默认全部日期；选中后只显示该日）
- 空态文案示例：
  - 全部：`近 7 日勾选联赛暂无未开赛赛事`
  - 某联赛：`近 7 日暂无{联赛名}未开赛赛事`
- Loading / Error + 重试
- 副标题仅「未开赛 N 场」，不展示同步窗口说明

### 3.5 比赛卡片

展示要点：

- 联赛 Tag、开赛时间、状态（未开始）
- 主队 **VS** 客队：仅点击中间 VS 进入详情（可复制卡片文字，不会误跳转）
- 分析结论（由推荐方向 + 概率推导，如「主胜概率较高（约 62%）」）
- 推荐方向、置信度、主/平/客概率摘要；不再使用底部「查看详细分析」按钮

说明：队徽、大小球/双方进球等若后端列表未返回，可不展示或后续增强；**以实际 `FixtureResponse` 为准**。

---

## 3A. 页面：赛果（`/results`）

分区（桌面 **左右分栏**，整页高度固定不滚）：

1. **左侧** `n-layout-sider`：赛果列表（`n-scrollbar` 内滚动）
2. **右侧**：当日准确率 + 历史总准确率（并排：推荐结果 / 胜平负单选 / 比分 / 大小球 / 双方进球 / 让球胜平负）+ 准确率走势图

各玩法样本量不同（某场次可能缺盘口或缺该维度预测），因此**每个百分比都必须带 `命中/样本`**，走势图 tooltip 同理。

口径：当日统计 = 勾选联赛内当天场次；历史统计与走势图 = 本地库**全部有预测快照的场次**（不按联赛过滤），tooltip 表头写「已预测 N 场」。两处百分比因此可能不同，属预期。

手机（赛果日）：两个 Tab——**赛程列表**（工具栏「当日统计」弹窗）/ **历史统计**（上方指标 + 下方走势图上下排布）。未来赛程日仍为单列列表。

当日列表含 **完场 + 进行中（live）**（开赛后从计算器迁入；不做滚球轮询，比分随本地库更新）。命中统计仍只计已完场且可评估的场次。

---

## 4. 页面二：比赛详情

### 4.1 整体结构

```
n-layout-content（全屏滚动）
├── BasicInfo：n-breadcrumb + n-page-header（对阵 / 联赛 / 时间）
└── TabsContainer（n-tabs）
      ├── 统计 H2HTab（历史交锋 + 主客近期战绩，MatchStatsTable）
      ├── 赛季数据 StatsTab
      ├── 伤病与阵容 LineupTab
      ├── 赛前简报 BriefingTab（官方 /predictions）
      └── 我的预测 PredictionTab
            └── PredictionResult（左算法预测 / 右盘口解释）
```

面包屑：`赛前赛事` / `{联赛}` / `{主队 VS 客队}`（前两级可点击）。

### 4.2 数据策略（当前实现）

后端**尚无**独立的 `/form`、`/h2h`、`/stats`、`/lineup`、`/prediction`、`POST /predict`。

当前约定：

1. 计算器：`/leagues` + `/fixtures/today` 只读本地库；模块级缓存约 5 分钟，详情返回不重复请求；切换联赛仅前端过滤
2. 进入详情页请求一次：`GET /api/v1/fixtures/{fixture_id}/analysis`（此处才可能打官方 API）
3. 响应中的 `analysis` + `analysis.package`（赔率 / 近况 / 交锋 / 阵容 / 伤病 / 官方简报等）供各 Tab 共用
4. Tabs：**首次切换到某 Tab 再挂载内容**（懒渲染）；已访问过的 Tab 保留，不重复请求
5. 「我的预测」左侧为算法结论，右侧为根据即时/初盘与倾向生成的解释文案（无主观因素融合）
6. 「赛前简报」来自官方 `GET /predictions`，落库 `package.briefing`，与「我的预测」本地模型无关

### 4.3 各 Tab 展示要求

| Tab   | 内容                                                                                                                    |
|-------|-----------------------------------------------------------------------------------------------------------------------|
| 统计 | 无外层 card；历史交锋 / 近期战绩色带分隔；`MatchStatsSummary` + **`n-data-table`（MatchStatsTable）**；近期主客 `n-grid` 左右分栏 |
| 赛季数据  | 在独立 stats 接口就绪前，可用近况估算胜率、场均进/失球；可附带 1X2 赔率参考；需标明数据来源局限                                                                |
| 伤病与阵容 | 双方伤病列表；首发 / 替补 / 阵型（无数据时空态）                                                                                           |
| 赛前简报 | 官方 advice / 胜平负占比 / 大小球 / 对比表；无 coverage 时空态                                                                 |
| 我的预测  | 算法原始胜平负 + 推荐；盘口：仅初盘未变时只显示「初盘」，有更新后才并排「即时盘」；右侧盘口解释 |

### 4.4 状态处理

- 详情首屏：整体 Loading；失败可重试
- 各 Tab：共享同一份 analysis 缓存；切换时若已加载则直接展示

---

## 5. API 对接（以现网为准）

### 5.1 联赛列表

`GET /api/v1/leagues?days=7`

主要字段：`league_id`、`league_name`、`country`、`today_fixtures_count`、`upcoming_fixtures_count`。

### 5.2 近期赛程（列表）

`GET /api/v1/fixtures/today?days=7`  
可选：`league_id`、`date`（计算器默认不传 `league_id`）。

只读本地库；列表项含简要 `analysis`（概率 / 推荐 / 置信度），**不含**完整 `package`。

### 5.3 强制同步赛程

`POST /api/v1/fixtures/sync?days=7`  
可选：`date=YYYY-MM-DD`（单日）、`include_results=true`、`odds_only=true`（仅补盘口）。

绕过 Redis/SQLite 日缓存拉取官方并写入本地，**赛程/盘口/赛果全部落库后才返回**。
已有同步在跑时立即返回 `status="running"`，本次不打官方。

### 5.4 赛果（按日）

`GET /api/v1/fixtures/results?date=YYYY-MM-DD`

只读本地已结束场次（含 `home_goals` / `away_goals`）。

### 5.5 单场分析（详情）

`GET /api/v1/fixtures/{fixture_id}/analysis`

含完整 `analysis.package`（有数据时）：`odds`、`home_form` / `away_form`、`head_to_head`、`lineups`、`injuries` 等。

### 5.6 规划中（未实现，勿在前端写死依赖）

| 设想接口                                      | 用途           |
|-------------------------------------------|--------------|
| `GET .../form`                            | 近期战绩         |
| `GET .../h2h`                             | 历史交锋         |
| `GET .../stats`                           | 赛季主客场统计      |
| `GET .../lineup`                          | 伤病与阵容        |
| `GET .../prediction` + `POST .../predict` | 服务端预测接口（可选增强） |

接入后可改为「按 Tab 请求 + 分 Tab 缓存」，并去掉前端本地融合。

---

## 6. 目录结构（当前）

```
frontend/src/
├── api/                 # client / leagues / fixtures / types
├── components/
│   ├── LeagueMenu.vue
│   ├── FixtureCard.vue
│   ├── FixtureList.vue
│   ├── ProbabilityChart.vue
│   └── detail/
│       ├── BasicInfo.vue
│       ├── TabsContainer.vue
│       ├── H2HTab.vue             # 统计页编排
│       ├── MatchStatsSummary.vue  # 共N场 + 胜率/进失汇总
│       ├── MatchStatsTable.vue    # 对阵统计表（matches + focusTeamId）
│       ├── StatsTab.vue
│       ├── LineupTab.vue
│       ├── PredictionTab.vue
│       └── PredictionResult.vue
├── composables/
│   └── useFixtureAnalysis.ts
├── utils/
│   ├── format.ts
│   ├── leagueNames.ts
│   ├── opinionAdjust.ts
│   └── predictionExplanation.ts
├── views/
│   ├── Predictions/
│   ├── Results/
│   ├── Mine/
│   └── Detail/
└── router/index.ts
```

---

## 7. UI 与质量要求

- **组件优先**：遵守 `.cursor/rules/frontend-ui.mdc`（Layout / Menu / Breadcrumb / PageHeader 等）
- **少写 CSS**：优先依赖 Naive 默认样式与 props；自定义 class 只留给复杂布局（见 `frontend-ui.mdc`「少写 CSS」）
- **就近组织**：路由与应用级抽屉统一用 `views/<Feature>/index.vue`；专属子组件和 composable 分别放同目录 `components/`、`composables/`，跨功能复用代码才进入全局目录
- 全屏壳 + 内容区滚动；勿用整站 `max-width` 居中窄栏代替布局
- 风格：简洁、白/灰为主，信息密度适中
- Composition API（`<script setup>`）+ TypeScript
- Loading / 空态 / 错误重试用 `n-spin` / `n-empty` / `n-alert`
- `league_id` 与 `fixture_id` 不得混用

---

## 7.1 登录 / VIP / 配额（规划，未落地）

当前登录为前端 stub。后续用户档位、手动同步额度、PC「刷新官方」、用尽只读等，以根目录 **[docs/AUTH_VIP_QUOTA.md](../docs/AUTH_VIP_QUOTA.md)** 为准；落地时同步改「我的」页与顶栏入口，并回写本节。

---

## 8. 本地运行

```bash
# 后端 :8000
cd frontend && npm install && npm run dev
# http://127.0.0.1:5173
```

库中无赛程时，在后端执行 `fetch-leagues` / `fetch-upcoming`（或 `fetch-today`）后再刷新前端。

---

## 9. 文档维护

- 页面交互或默认筛选策略变更时，先改本文，再改代码。
- 产品是否做直播等边界变更，先改根目录 `PROJECT_PLAN.md` 第 1 节。
- 用户鉴权 / VIP / 配额变更，先改 `docs/AUTH_VIP_QUOTA.md` 与 `PROJECT_PLAN.md` §1.4，再改代码。
- 本文替代原 `frontend/web.md`（提示词草稿）。
