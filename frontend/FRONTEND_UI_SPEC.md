# 前端 UI 需求说明（赛前分析）

> 本文档描述前端页面结构、交互与对接约定，供实现与迭代对照。  
> 接口字段以运行中的后端 OpenAPI / 代码为准；下文示例仅作说明。  
> 产品边界见仓库根目录 `PROJECT_PLAN.md`。  
> API 约定见 `.cursor/rules/frontend-api.mdc`。  
> **Naive UI 组件优先与全屏布局**见 `.cursor/rules/frontend-ui.mdc`（开发时必须遵守）。

---

## 1. 产品与技术背景

- **定位**：轻量级**赛前**分析工具，只关注未开赛（`pending`）比赛；不是实时比分站。
- **特色**：人机协同——后端算法给出基础胜平负分析；用户可输入主观意见，前端做融合对比展示。
- **前端栈**：Vue 3 + TypeScript + Vite + Vue Router + Axios + Naive UI + ECharts。
- **后端**：本项目 FastAPI，开发时代理 `/api` → `http://127.0.0.1:8000`；基址 `VITE_API_BASE_URL` 或默认 `/api/v1`。
- **禁止**：前端存放或直连 API-Sports / RapidAPI Key。
- **UI**：全屏 `n-layout`；侧栏 / 顶栏固定，内容区滚动；优先使用 Layout、Menu、Breadcrumb、PageHeader 等组件，避免手写平行布局。
- **多端**：手机 / 平板可用（侧栏抽屉、双栏改单列、安全区）；不依赖 Tailwind。

---

## 2. 路由

| 路径                    | 名称               | 页面       |
|-----------------------|------------------|----------|
| `/`                   | `home`           | 赛事列表（主页） |
| `/results`            | `results`        | 赛果（按日期）  |
| `/fixture/:fixtureId` | `fixture-detail` | 比赛详情     |

兼容重定向：

- `/leagues/:leagueId` → `/?league=:leagueId`
- `/fixtures/:fixtureId` → `/fixture/:fixtureId`

查询参数：`/?league=<league_id>` 表示首页按联赛筛选；无参数表示「全部」。

顶栏导航：**赛前** / **赛果**。

---

## 3. 页面一：赛事列表（主页）

### 3.1 布局（全屏 Layout）

应用壳占满视口。首页使用 `n-layout has-sider`：

| 区域    | 组件 / 行为                                             |
|-------|-----------------------------------------------------|
| 左侧联赛  | 桌面：`n-layout-sider`（约 232px，可折叠）+ `n-menu`；平板默认折叠；手机改为顶栏「联赛」+ 左侧 `n-drawer` |
| 右侧工具条 | `n-breadcrumb` + `n-page-header`（标题、场次、刷新）          |
| 右侧列表  | `n-layout-content` 内滚动；卡片纵向排列，间距约 12–16px           |

### 3.2 数据加载（重要）

1. 进入首页时**并行**请求：
   - `GET /api/v1/leagues?days=7`
   - `GET /api/v1/fixtures/today?days=7`（**不传** `league_id`，一次拉全量近期赛程）
2. 默认选中左侧 **「全部」**，右侧展示全部 `status === pending` 的比赛。
3. 点击某个联赛时：**不再请求接口**，在已加载的全量列表上按 `league_id` **本地筛选**。
4. 左侧数量角标：优先用本地 pending 场次统计（与右侧一致），避免「联赛有入库场次但右侧为空」的错觉。
5. 点「**强制刷新**」：先 `POST /api/v1/fixtures/sync?days=7`（绕过 Redis/SQLite 日缓存打官方），成功后再重拉本地列表。有约 90 秒冷却，避免刷爆配额。

### 3.3 左侧联赛菜单

- 使用 `n-menu`；首项 **全部**，其后各联赛；数量用 `n-badge`
- 当前项高亮；不同联赛可用色点区分
- 面包屑：`赛前赛事` / `全部` 或当前联赛名

### 3.4 右侧比赛列表

- 仅展示 `pending`（未开始）
- 按开赛时间从近到远排序
- 空态文案示例：
  - 全部：`近 7 日暂无未开赛赛事`
  - 某联赛：`近 7 日暂无{联赛名}未开赛赛事`
- Loading / Error + 重试

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
2. **右侧**：当日准确率 + 历史总准确率（并排，四维：胜平负 / 比分 / 大小 / 双方进球）+ 准确率走势图

手机：上方限高列表滚动，下方准确率与图表。

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
      └── 我的预测 PredictionTab
            ├── OpinionInput
            └── PredictionResult
```

面包屑：`赛前赛事` / `{联赛}` / `{主队 VS 客队}`（前两级可点击）。

### 4.2 数据策略（当前实现）

后端**尚无**独立的 `/form`、`/h2h`、`/stats`、`/lineup`、`/prediction`、`POST /predict`。

当前约定：

1. 首页：`/leagues` + `/fixtures/today` 只读本地库；模块级缓存约 5 分钟，详情返回不重复请求；切换联赛仅前端过滤
2. 进入详情页请求一次：`GET /api/v1/fixtures/{fixture_id}/analysis`（此处才可能打官方 API）
3. 响应中的 `analysis` + `analysis.package`（赔率 / 近况 / 交锋 / 阵容 / 伤病等）供各 Tab 共用
4. Tabs：**首次切换到某 Tab 再挂载内容**（懒渲染）；已访问过的 Tab 保留，不重复请求
5. 「我的预测」中融合结果为**前端本地启发式**（`utils/opinionAdjust.ts`），差异高亮；待后端提供预测接口后再改为服务端融合

### 4.3 各 Tab 展示要求

| Tab   | 内容                                                                                                                    |
|-------|-----------------------------------------------------------------------------------------------------------------------|
| 统计 | 无外层 card；历史交锋 / 近期战绩色带分隔；`MatchStatsSummary` + **`n-data-table`（MatchStatsTable）**；近期主客 `n-grid` 左右分栏 |
| 赛季数据  | 在独立 stats 接口就绪前，可用近况估算胜率、场均进/失球；可附带 1X2 赔率参考；需标明数据来源局限                                                                |
| 伤病与阵容 | 双方伤病列表；首发 / 替补 / 阵型（无数据时空态）                                                                                           |
| 我的预测  | 算法原始胜平负 + 推荐；主观意见输入；提交后展示融合对比（差异高亮）                                                                                   |

### 4.4 状态处理

- 详情首屏：整体 Loading；失败可重试
- 各 Tab：共享同一份 analysis 缓存；切换时若已加载则直接展示
- 提交主观意见时：仅预测区域 Loading，不影响其他 Tab

---

## 5. API 对接（以现网为准）

### 5.1 联赛列表

`GET /api/v1/leagues?days=7`

主要字段：`league_id`、`league_name`、`country`、`today_fixtures_count`、`upcoming_fixtures_count`。

### 5.2 近期赛程（列表）

`GET /api/v1/fixtures/today?days=7`  
可选：`league_id`、`date`（首页默认不传 `league_id`）。

只读本地库；列表项含简要 `analysis`（概率 / 推荐 / 置信度），**不含**完整 `package`。

### 5.3 强制同步赛程

`POST /api/v1/fixtures/sync?days=7`  
可选：`date=YYYY-MM-DD`（单日）、`include_results=true`。

绕过 Redis/SQLite 日缓存拉取官方并写入本地；约 90 秒冷却。

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
| `GET .../prediction` + `POST .../predict` | 服务端预测与主观意见融合 |

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
│       ├── OpinionInput.vue
│       └── PredictionResult.vue
├── composables/
│   └── useFixtureAnalysis.ts
├── utils/
│   ├── format.ts
│   ├── leagueNames.ts
│   ├── teamNames.ts
│   └── opinionAdjust.ts
├── views/
│   ├── Home.vue
│   └── Detail.vue
└── router/index.ts
```

---

## 7. UI 与质量要求

- **组件优先**：遵守 `.cursor/rules/frontend-ui.mdc`（Layout / Menu / Breadcrumb / PageHeader 等）
- 全屏壳 + 内容区滚动；勿用整站 `max-width` 居中窄栏代替布局
- 风格：简洁、白/灰为主，信息密度适中
- Composition API（`<script setup>`）+ TypeScript
- Loading / 空态 / 错误重试用 `n-spin` / `n-empty` / `n-alert`
- `league_id` 与 `fixture_id` 不得混用

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
- 本文替代原 `frontend/web.md`（提示词草稿）。
