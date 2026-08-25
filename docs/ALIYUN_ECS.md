# 阿里云 ECS 部署（含本地 SQLite）

本仓库**没有**本机↔云自动同步。上云走计划书方案 A：把 `football.db` 与 `data/models/` 一起拷到服务器，Docker Compose 挂载同一目录。官方 Key 已在库的 `app_settings` 里，不必再写进环境变量。

权威步骤：首次拷库后**以 ECS 为唯一写库端**。本机 `uvicorn` 必须停掉，否则两套定时任务会把官方日配额打双份。

## 机器要求

| 项 | 建议 |
|----|------|
| 规格 | 2 核 4 GB 起（pandas + 约 110MB SQLite） |
| 系统 | Ubuntu 22.04 / 24.04 |
| 安全组入站 | `22`（你的 IP）、`80`；有域名证书后再开 `443`。**不要**对公网开放 `8000` |
| 磁盘 | 系统盘 ≥ 40 GB |

地域选离你近的即可；容器内时区固定 `Asia/Shanghai`，与调度器一致。

## 服务器一次性准备

SSH 登录后：

```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-v2
sudo usermod -aG docker "$USER"   # 重新登录后生效
sudo mkdir -p /opt/football-analytics
sudo chown "$USER":"$USER" /opt/football-analytics
```

## 本机：导出一致库文件

尽量先停掉本机后端，再导出（有 WAL 时命令仍可用）：

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python manage.py export-sqlite
```

产物：`backend/data/football.export.db`。模型在 `backend/data/models/`（约数 KB，必须一起拷）。

## 上传与启动

在仓库根目录（把 `ECS_IP`、用户名换成你的）：

```powershell
.\scripts\deploy-aliyun.ps1 -EcsHost ECS_IP -User root
```

脚本会：打包代码（不含 `.venv` / `node_modules` / 原库文件）→ 把导出库写成服务器上的 `backend/data/football.db` → 同步 `models/` → 若没有 `deploy/cloud.env` 则从 example 生成 → `docker compose up -d --build`。

首次请 SSH 编辑 `/opt/football-analytics/deploy/cloud.env`：

```env
CORS_ALLOW_ORIGINS=http://ECS_IP
```

有域名后改成 `https://你的域名`，并把 `SESSION_COOKIE_SECURE=true`。改完：

```bash
cd /opt/football-analytics
docker compose up -d --force-recreate backend
```

## 验收

- http://ECS_IP/ → 前端
- http://ECS_IP/api/v1/health → 后端
- 登录后核对【比赛】/【赛果】是否与本机一致
- 服务器执行：`docker compose exec backend python manage.py model-status`

## 备份与回滚

数据在主机目录 `/opt/football-analytics/backend/data/`（bind mount），容器重建不会丢库。

备份示例：

```bash
cp /opt/football-analytics/backend/data/football.db \
   /opt/football-analytics/backend/data/football.db.bak-$(date +%F)
```

恢复：停 `docker compose stop backend`，覆盖 `football.db` 与 `models/`，再 `docker compose start backend`。

## 本机开发

上线后本机只读备份或空库开发。不要再开本机调度器打官方接口。
