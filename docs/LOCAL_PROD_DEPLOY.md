# 本机生产环境部署

在本机打包前端、以接近生产的方式跑前后端，便于用电脑或手机验证正式构建效果。开发联调仍用 [DEV_SETUP.md](../DEV_SETUP.md)（`npm run dev` + `uvicorn --reload`）。

## 架构说明

| 环境 | 前端 | API 请求 |
|------|------|----------|
| 开发 | Vite `:5173`，自带 `/api` 代理 | `/api/v1` → `127.0.0.1:8000` |
| 生产构建 | 静态文件 `frontend/dist` | 默认仍是相对路径 `/api/v1`（见 `frontend/.env.production`） |

因此生产预览有两种做法：

1. **同源（推荐）**：一个入口（如 Nginx `:80`）同时提供静态页，并把 `/api` 反代到后端。浏览器始终请求同一主机，与线上一致。
2. **分端口（最快）**：后端 `:8000`，静态站另开端口；构建时把 `VITE_API_BASE_URL` 写成后端绝对地址。后端已开 CORS `*`，可跨端口访问。

---

## 前置条件

与开发环境相同：

- Python 3.11 / 3.12，`backend/.venv` 已 `pip install -r requirements.txt`
- Node.js 20+，`frontend` 已 `npm install`
- `backend/secrets.local.env` 已配置 `API_SPORTS_KEY`
- 可选：`backend/.env`（从 `.env.example` 复制）

数据库：

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python manage.py init-db
```

---

## 1. 启动后端（生产方式）

**不要**加 `--reload`（生产无热重载；改代码需手动重启）。

```powershell
cd backend
.\.venv\Scripts\Activate.ps1

# 仅本机浏览器
uvicorn main:app --host 127.0.0.1 --port 8000

# 同局域网手机访问（本机防火墙需放行 8000）
uvicorn main:app --host 0.0.0.0 --port 8000
```

自检：

- http://127.0.0.1:8000/api/v1/health
- http://127.0.0.1:8000/docs

工作目录必须是 `backend/`，否则 SQLite 路径 `./data/football.db` 会错位。

可选：多进程（本机压测用；定时任务注意不要多实例乱开）：

```powershell
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1
```

本机预览保持 `--workers 1` 即可（调度器随进程启动）。

---

## 2. 打包前端

```powershell
cd frontend
npm run build
```

产物目录：`frontend/dist/`（含 `index.html` 与静态资源）。`vue-tsc` 类型检查失败则构建中止，需先修类型错误。

默认 API 基址来自 `frontend/.env.production`：

```env
VITE_API_BASE_URL=/api/v1
```

`VITE_*` 在 **build 时写入包内**，改环境变量后必须重新 `npm run build`。

---

## 3. 部署方式 A：同源反代（推荐，最接近生产）

### 3.1 用 Nginx（Windows / Linux 通用思路）

1. 安装 [Nginx for Windows](https://nginx.org/en/download.html) 或本机已有 Nginx。
2. 假设仓库在 `C:\Users\jisui.wu\PyCharmProjects\football-analytics`，在 `nginx.conf` 的 `http` 里增加（或改 `server`）：

```nginx
server {
    listen       80;
    server_name  localhost;

    # 前端静态资源
    root   C:/Users/jisui.wu/PyCharmProjects/football-analytics/frontend/dist;
    index  index.html;

    # Vue Router history：刷新子路由不 404
    location / {
        try_files $uri $uri/ /index.html;
    }

    # 后端 API
    location /api/ {
        proxy_pass         http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        # 详情分析等可能较慢
        proxy_read_timeout 120s;
    }
}
```

3. 先启动后端（§1），再启动 Nginx。
4. 访问：http://127.0.0.1/  
   局域网手机：http://\<电脑局域网IP\>/（Nginx 需 `listen` 对网卡开放，防火墙放行 80）。

路径里的盘符请改成你的实际仓库路径；Nginx for Windows 用正斜杠。

### 3.2 用 Caddy（配置更短，可选）

安装 Caddy 后，在仓库根或任意目录放 `Caddyfile`：

```caddyfile
:80 {
    root * ./frontend/dist
    encode gzip
    reverse_proxy /api/* 127.0.0.1:8000
    try_files {path} /index.html
    file_server
}
```

在含 `frontend/` 的仓库根执行：`caddy run`（先起后端）。

---

## 4. 部署方式 B：分端口（不装 Nginx，最快试生产包）

适合只想看「打包后的前端」效果，不要求同源。

### 4.1 构建时指向后端绝对地址

本机浏览器：

```powershell
cd frontend
$env:VITE_API_BASE_URL="http://127.0.0.1:8000/api/v1"
npm run build
```

手机访问电脑时，把地址换成电脑的局域网 IP（不要用 `127.0.0.1`）：

```powershell
cd frontend
$env:VITE_API_BASE_URL="http://192.168.1.10:8000/api/v1"
npm run build
```

（`192.168.1.10` 换成 `ipconfig` 看到的 IPv4。）

### 4.2 托管 `dist`

任选其一（需支持 SPA fallback，刷新子路由才不 404）：

```powershell
cd frontend
npx --yes serve -s dist -l 4173
```

或 Vite 自带预览（**不会**自动代理 `/api`，故必须用上面的绝对 `VITE_API_BASE_URL`）：

```powershell
cd frontend
npm run preview -- --host 0.0.0.0 --port 4173
```

访问：

- 电脑：http://127.0.0.1:4173
- 手机：http://\<局域网IP\>:4173  
  同时后端须 `--host 0.0.0.0`，防火墙放行 `4173` 与 `8000`。

用完可关掉终端；下次改代码后重新 `build` 再起静态服务。

恢复默认相对路径构建（给 Nginx 用）：

```powershell
cd frontend
Remove-Item Env:VITE_API_BASE_URL -ErrorAction SilentlyContinue
npm run build
```

---

## 5. 推荐操作顺序（清单）

### 同源（Nginx）

1. `backend`：激活 venv → `uvicorn main:app --host 0.0.0.0 --port 8000`
2. `frontend`：`npm run build`（使用默认 `/api/v1`）
3. 配置并启动 Nginx，`root` 指向 `frontend/dist`
4. 浏览器 / 手机打开 http://\<主机\>/

### 分端口

1. 后端同上
2. 按访问方式设置 `VITE_API_BASE_URL` 后 `npm run build`
3. `npx serve -s dist -l 4173`（或 `npm run preview`）
4. 打开对应端口页面

---

## 6. 与开发环境差异（验收时注意）

| 项 | 开发 | 本机生产预览 |
|----|------|----------------|
| 前端代码 | 热更新 | 改完须重新 `build` |
| 资源 | 未压缩 / source maps 策略不同 | 压缩拆包后的 `dist` |
| API 代理 | Vite `server.proxy` | Nginx 反代或绝对 `VITE_API_BASE_URL` |
| 后端 | 常用 `--reload` | 不加 `--reload` |
| 手机访问 | Vite 已 `host: 0.0.0.0` | 后端 / Nginx / serve 均需对局域网监听并放行防火墙 |

---

## 7. 常见问题

| 现象 | 处理 |
|------|------|
| 页面空白或接口 404 | 同源方案未配 `/api` 反代，却用了相对 `/api/v1` |
| 手机能开页面但无数据 | 分端口构建写成了 `127.0.0.1`；应写成电脑局域网 IP，且后端 `0.0.0.0` |
| 刷新详情页 404 | 静态服务器未做 SPA `try_files` / `serve -s` |
| 数据库找不到 | 在 `backend/` 目录启动 uvicorn |
| 改了 `.env.production` 无效果 | 须重新 `npm run build` |
| 官方 API 证书错误 | `backend/.env` 中 `HTTP_VERIFY_SSL=false`（仅影响官方请求） |
| Windows 防火墙拦截 | 入站规则放行 80 / 8000 / 4173（按实际端口） |

查本机局域网 IP（PowerShell）：

```powershell
Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '127.*' } | Select-Object IPAddress, InterfaceAlias
```

---

## 8. 安全提醒（本机预览即可）

- 不要把 `secrets.local.env`、真实 API Key 打进前端或提交 Git。
- `CORS allow_origins=["*"]` 便于本机联调；真正上公网时应收紧来源并加鉴权（见 [AUTH_VIP_QUOTA.md](AUTH_VIP_QUOTA.md)）。
- 对局域网开放端口时，仅在受信网络使用。

---

## 9. 文档索引

| 文档 | 内容 |
|------|------|
| [DEV_SETUP.md](../DEV_SETUP.md) | 开发环境安装与双进程启动 |
| [LOCAL_PROD_DEPLOY.md](LOCAL_PROD_DEPLOY.md) | **本文：本机生产打包与部署** |
| [backend/README.md](../backend/README.md) | 后端配置与管理命令 |
| [frontend/README.md](../frontend/README.md) | 前端命令与路由 |
