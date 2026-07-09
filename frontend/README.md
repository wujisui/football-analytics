# Football Analytics Frontend

Vue 3 前端，对接后端 `/api/v1`，展示联赛、今日赛程与赛前概率分析。

## 技术栈

- Vue 3 + TypeScript + Vite
- Vue Router
- Naive UI
- Axios
- ECharts（`vue-echarts`）

## 快速开始

先确保后端已在 `http://127.0.0.1:8000` 运行（见仓库根目录或 [backend/README.md](../backend/README.md)）。

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
| `/` | `LeaguesView` | 联赛列表 |
| `/leagues/:leagueId` | `FixturesView` | 指定联赛的今日赛程 |
| `/fixtures/:fixtureId` | `AnalysisView` | 单场比赛分析与概率图 |

## 目录结构

```
frontend/
├── src/
│   ├── api/              # Axios 客户端与接口封装
│   │   ├── client.ts
│   │   ├── leagues.ts
│   │   ├── fixtures.ts
│   │   └── types.ts
│   ├── components/       # LeagueCard / FixtureList / ProbabilityChart
│   ├── views/            # 三个页面
│   ├── router/           # 路由配置
│   ├── App.vue
│   └── main.ts
├── .env.production       # 生产环境 API 前缀
├── vite.config.ts        # 开发代理等
└── package.json
```

## API 对接

开发环境默认请求 `/api/v1/...`，由 Vite 代理到后端：

```ts
// vite.config.ts
server: {
  proxy: {
    '/api': {
      target: 'http://127.0.0.1:8000',
      changeOrigin: true,
    },
  },
}
```

生产环境通过 `VITE_API_BASE_URL` 配置（见 `.env.production`，当前为 `/api/v1`）。也可在本地新建 `.env.development` 覆盖：

```env
VITE_API_BASE_URL=/api/v1
```

推荐调用顺序：

1. `GET /leagues` → 联赛列表
2. `GET /fixtures/today?league_id=39` → 今日赛程
3. `GET /fixtures/{fixture_id}/analysis` → 单场分析

`league_id` 是联赛 ID，`fixture_id` 是比赛 ID，二者不同。

## 常见问题

**页面报网络错误**  
确认后端已启动，且 Vite 代理目标为 `http://127.0.0.1:8000`。

**联赛/赛程为空**  
在后端执行 `python manage.py fetch-leagues` 与 `python manage.py fetch-today`，或等待调度任务 `daily_init`。

**生产部署**  
`npm run build` 后将 `dist/` 交给 Nginx 等静态托管；若前后端同域，保持 `VITE_API_BASE_URL=/api/v1` 并由网关把 `/api` 反代到后端即可。
