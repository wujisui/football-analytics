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
| `/`                   | —                | 重定向到比赛 |
| `/predictions`        | `predictions`    | 比赛（预测与投注计算器） |
| `/results`            | `results`        | 赛果（按日期）  |
| `/favorites`          | `favorites`      | 关注场次（手机底栏 / 桌面顶栏） |
| `/mine/*`             | `mine-*`         | 我的（方案 / 偏好 / 管理员设置 / 关于） |
| `/fixture/:fixtureId` | `fixture-detail` | 比赛详情     |

兼容重定向：

- `/leagues/:leagueId` → `/predictions?league=:leagueId`
- `/plans` → `/mine/plans`
- `/mine/favorites` → `/favorites`
- `/fixtures/:fixtureId` → `/fixture/:fixtureId`

查询参数：`/predictions?league=<league_id>` 表示比赛页按联赛筛选；无参数表示「全部」。

顶栏导航：桌面为 **比赛** / **赛程** / **关注**，未登录显示 **登录**（弹窗表单），登录后才出现 **我的**；PC 从其他顶栏回到「我的」时打开离开前的子页，手机底栏「我的」始终进个人主页。主题与让球玩法（亚盘 / 竞彩）开关都只留在「我的 → 偏好设置」，切换即时生效；手机底栏为 **计算器** / **赛程** / **关注** / **我的**。关注仅走 `/favorites`，不再从「我的」进入；PC 关注页与比赛页同为左侧联赛列表 + 右侧内容区，手机保持单栏；「我的方案」只从「我的」进入。比赛页桌面为 **比赛**（预测卡片 | 计算器卡片左右并排，单列默认滚动）+ **投注详情** 两列；列标题为「比赛」+ 场次统计，右侧「已选」；手机为场次玩法列表 + 选中后底部固定投注摘要。投注详情中的已选项会自动清理：赛程日早于 UTC 今天，或开赛时间已过的场次不再保留（已保存的「我的方案」不受影响）。

主题固定为「深色 / 浅色 / 护眼」三项，下拉选择并保存在本机，新用户默认护眼。浅色使用原始高亮配色；护眼采用暖调米灰（纸感）：页面、卡片与输入控件不使用大面积纯白，页面底色明显低于卡片一档以拉开层级，配柔和暖阴影；胜/平/负、推荐标签、链接等业务强调色保持现有辨识度。表面色真源为 `src/styles/themes/{dark,light,eye-care}.css`（`html[data-theme]`），由 `src/styles/index.ts` 统一导入；`src/styles/base.css` 只放布局与共用 token。`theme/presets.ts` 只保留下拉选项、是否深色、Naive `overrides`（护眼组件表面）。`index.html` 同步脚本在首屏写入 `data-theme`，JS 只改这个属性，不再行内注入颜色。选中 / 激活态（热门联赛勾选块、左侧联赛菜单当前项）统一用 `--fa-accent` 着色，**禁止**引用 Naive 组件作用域变量 `--n-primary-color` 或给它写死十六进制兜底：该变量在普通 DOM 上解析不到，兜底色会成为实际生效色并脱离主题。`utils/format.ts` 的联赛色板与 `utils/accuracyColors.ts` 的玩法色板属于定性分类色，不随主题变化，不在此约束内。

所有会触发后端写操作的按钮（保存、删除、更新、同步、提交）在 Promise 完成前必须进入 `loading` / `disabled`，处理函数入口同时检查 in-flight 状态，避免鼠标连点、回车与弹窗确认走不同入口时重复提交。关键创建操作还应在数据层做 single-flight 或提交稳定客户端 ID；普通导航、筛选和纯本地切换不做这种限制。

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
5. 打开列表页、F5、下拉刷新都只重拉本地接口。每日完整批次为 10:55；密刷开启时按每小时 25/55 分全天刷新今天盘口，关闭时采用 07:00、08:05、10:55、22:00 时刻表。前端无公开 sync、SSE 或轮询。
6. 勾选其他联赛只改变本地筛选，不触发盘口补拉。
7. 进入详情请求 `/fixtures/{id}/analysis`：后端本地优先，缺展示包时可打官方并落库。

### 3.3 左侧联赛菜单

- 使用 `n-menu`；首项 **全部**，其后各联赛；数量用 `n-badge`
- 当前项高亮；不同联赛可用色点区分
- 面包屑：`赛前赛事` / `全部` 或当前联赛名

### 3.4 右侧比赛列表

- 仅展示未开赛（pending）；开赛后归赛果列表
- 按开赛时间从近到远排序，并按**赛程日**分组；日期标题栏 `position: sticky` 吸附顶部，滚动到下一日时由新标题顶替
- 桌面列标题为「比赛」+ 场次统计，右侧「已选」；卡片内只显示开赛时间（日期由分组标题表达）
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
2. **右侧**：当日准确率 + 历史总准确率（并排：胜平负 / 每日推荐 / 比分 / 大小球 / 双方进球 / 让球胜平负）+ 准确率走势图

各玩法样本量不同（某场次可能缺盘口或缺该维度预测），因此**每个百分比都必须带 `命中/样本`**，走势图 tooltip 同理。

口径：当日统计 = 勾选联赛内当天场次；历史统计与走势图 = 本地库**全部有预测快照的场次**（不按联赛过滤），tooltip 表头写「已预测 N 场」。**每日推荐**另计 `auto_pick_snapshots` 冻结场次（与「胜平负」样本可不同）。两处百分比因此可能不同，属预期。

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
2. 进入详情页请求一次：`GET /api/v1/fixtures/{fixture_id}/analysis`（本地优先；缺包时后端按需打官方并落库）
3. 响应中的 `analysis` + `analysis.package`（赔率 / 近况 / 交锋 / 阵容 / 伤病 / 官方简报等）供各 Tab 共用
4. Tabs：**首次切换到某 Tab 再挂载内容**（懒渲染）；已访问过的 Tab 保留，不重复请求
5. 「我的预测」左侧为算法结论，右侧只读展示后端根据初盘 / 中盘 / 临场 / 即时盘生成的结构化盘口解释（无主观因素融合）
6. 「赛前简报」来自官方 `GET /predictions`，落库 `package.briefing`，与「我的预测」本地模型无关

### 4.3 各 Tab 展示要求

| Tab   | 内容                                                                                                                    |
|-------|-----------------------------------------------------------------------------------------------------------------------|
| 统计 | 无外层 card；历史交锋 / 近期战绩色带分隔；`MatchStatsSummary` + **`n-data-table`（MatchStatsTable）**；表列为赛事、日期、半场、对阵；交锋另加本地初盘/即时盘让球主档（有库存才显示，不打官方）；近期主客 `n-grid` 左右分栏 |
| 赛季数据  | 在独立 stats 接口就绪前，可用近况估算胜率、场均进/失球；可附带 1X2 赔率参考；需标明数据来源局限                                                                |
| 伤病与阵容 | 双方伤病列表；首发 / 替补 / 阵型（无数据时空态）                                                                                           |
| 赛前简报 | 官方 advice / 胜平负占比 / 大小球 / 对比表；无 coverage 时空态                                                                 |
| 我的预测  | 「赛前结果预测」与「盘口解释」卡片标题右侧 `#header-extra` 显示本场对局名；赛前卡未开赛时内联展示胜平负 + 推荐 + 饼图，已开赛改渲染 `AlgorithmPredictionCard`，两态共用同一张 `n-card` 与标题；胜平负三行上方固定标注「主盘赔率去水后的市场定价」（`published_match_probabilities` 恒返回去水盘口概率，模型只喂推荐，不进展示百分比）；盘口卡按采集时间去重，初盘早于即时盘才并排，同一次采集只显示「即时盘」；右侧展示后端盘口解释：四阶段主盘轨迹、同庄家同档去水概率、1X2 / 大小球交叉验证、让球返还后期望收益及不可比警告。前端不自行推断走势 |

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

### 5.3 赛果（按日）

`GET /api/v1/fixtures/results?date=YYYY-MM-DD`

只读本地已结束场次（含 `home_goals` / `away_goals`）。

### 5.4 单场分析（详情）

`GET /api/v1/fixtures/{fixture_id}/analysis`

含完整 `analysis.package`（有数据时）：`odds`、`home_form` / `away_form`、`head_to_head`、`lineups`、`injuries` 等。

### 5.5 规划中（未实现，勿在前端写死依赖）

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
│   └── opinionAdjust.ts
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
- **带标题的卡片一律 `:segmented="{ content: true }"`**：标题与正文之间靠 Naive 分隔线分层，赛果统计卡、方案统计卡与「我的」二级页各卡口径一致；无标题卡片加不加都不出线，勿另写 `border-top`
- **「我的方案」列表卡**：PC / 手机同一套 `n-card`，标题「方案列表」，`FavoriteDatesPicker` 走 `#header-extra`；内容区 `n-scrollbar` 滚动、标题固定。PC 顶栏不再放日期选择（第二行只显示当日方案数量）
- 风格：简洁、白/灰为主，信息密度适中
- Composition API（`<script setup>`）+ TypeScript
- Loading / 空态 / 错误重试用 `n-spin` / `n-empty` / `n-alert`
- `league_id` 与 `fixture_id` 不得混用

---

## 7.1 登录 / VIP / 配额（规划，未落地）

后续用户档位与账号权益以根目录 **[docs/AUTH_VIP_QUOTA.md](../docs/AUTH_VIP_QUOTA.md)** 为准；列表不提供「手动刷官方」入口。运维：`/mine/admin` 由订阅状态统一控制完整批次与详情预拉，并可配置全天密刷；打开订阅自动开启密刷，关闭订阅同时关闭并禁用。详情「我的预测」的「更新盘口」只向管理员显示，且仅在 `match_day=今天`、仍在【比赛】并属于配置页目录联赛时显示。该按钮只刷新本场盘口并重载本场算法推荐，不重算日推；日推只在运维「更新盘口」或定时/密刷批量盘口之后重排。

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
