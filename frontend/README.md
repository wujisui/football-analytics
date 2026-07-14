# Football Analytics Frontend

Vue 3 前端，对接后端 `/api/v1`，展示联赛赛程与赛前分析（含主观意见本地融合对比）。

页面交互与对接约定见 [FRONTEND_UI_SPEC.md](./FRONTEND_UI_SPEC.md)。  
Naive UI 组件优先与全屏布局见仓库 `.cursor/rules/frontend-ui.mdc`。

## 技术栈

- Vue 3 + TypeScript + Vite
- Vue Router
- Naive UI
- Axios
- ECharts（`vue-echarts`）

## 快速开始

换机环境（Node 版本、Volar 等）见仓库根目录 **[DEV_SETUP.md](../DEV_SETUP.md)**。  
先确保后端已在 `http://127.0.0.1:8000` 运行（见 [backend/README.md](../backend/README.md)）。

```bash
cd frontend
npm install
npm run dev
```

浏览器打开：http://127.0.0.1:5173

### 常用命令

```bash
npm run dev       # 本地开发（含 API 代理）
npm run build     # 类型检查 + 生产构建
npm run preview   # 预览构建产物
```

## 页面路由

| 路径 | 组件 | 说明 |
|------|------|------|
| `/` | `Home` | 默认全部未开赛；左侧联赛本地筛选 |
| `/fixture/:fixtureId` | `Detail` | 顶部基本信息 + Tabs（战绩/交锋/统计/阵容/预测） |

旧路径 `/leagues/:id`、`/fixtures/:id` 会重定向到新路由。

## 目录结构

```
frontend/
├── src/
│   ├── api/                 # Axios 客户端与接口封装
│   ├── components/
│   │   ├── LeagueMenu.vue
│   │   ├── FixtureCard.vue
│   │   ├── FixtureList.vue
│   │   ├── ProbabilityChart.vue
│   │   └── detail/          # 详情页分区组件
│   ├── views/
│   │   ├── Home.vue
│   │   └── Detail.vue
│   ├── utils/               # 格式化、主观意见本地融合
│   ├── router/
│   ├── App.vue
│   └── main.ts
├── vite.config.ts
└── package.json
```

## API 对接

开发环境默认请求 `/api/v1/...`，由 Vite 代理到后端。

推荐调用顺序（与 `.cursor/rules/frontend-api.mdc` 一致）：

1. `GET /leagues?days=7` → 联赛菜单
2. `GET /fixtures/today?days=7` → 全量近期赛程（首页一次拉取，联赛筛选在前端）
3. `GET /fixtures/{fixture_id}/analysis` → 详情 Tabs 共用的赛前包

说明：

- 列表只展示 `status === pending`；默认「全部」，点击联赛再本地过滤
- 详情 Tabs 与交互见 [FRONTEND_UI_SPEC.md](./FRONTEND_UI_SPEC.md)；数据仍来自 `/analysis`（尚无独立 form/h2h 等接口）
- 「融合主观意见」为前端本地启发式（后端暂无 `/predict`）
- `league_id` 与 `fixture_id` 不要混用

## 常见问题

**页面报网络错误**  
确认后端已启动，且 Vite 代理目标为 `http://127.0.0.1:8000`。

**联赛/赛程为空**  
在后端执行 `python manage.py fetch-leagues` 与 `python manage.py fetch-upcoming`（或 `fetch-today`）。
