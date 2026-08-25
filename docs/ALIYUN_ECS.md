# 阿里云 ECS 部署（含本地 SQLite）

本仓库**没有**设备↔云自动同步。上云走计划书方案 A：从指定的权威设备生成一个包含代码、`football.db` 与 `data/models/` 的迁移包，再部署到服务器。官方 Key 已在库的 `app_settings` 里，不必再写进环境变量。

不要混用不同设备的代码、数据库和模型：数据库中的冻结特征必须由同版本算法读取，Pinnacle 盘口样本也必须与对应模型一起迁移。首次拷库后**以 ECS 为唯一写库端**；其他设备的 `uvicorn` 必须停掉，否则多套定时任务会把官方日配额打双份。

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

## 权威设备：生成单一迁移包

将本仓库的 `scripts/create-migration-package.ps1` 放进权威项目的 `scripts/`。尽量先停止该设备的后端，然后在权威项目根目录执行：

```powershell
.\scripts\create-migration-package.ps1
```

脚本使用 SQLite backup API 生成一致副本并执行 `PRAGMA integrity_check`，不会直接打包可能仍带 WAL 的活动库。输出为：

```text
football-analytics-migration-YYYYMMDD-HHMMSS.tar.gz
```

包内包含该设备的完整代码、一致数据库、整个模型目录及 `migration-manifest.json`（数据库/模型 SHA-256）。只需把这一个文件上传网盘。

## 上传与启动

从网盘下载迁移包后，在这台电脑执行（把路径、`ECS_IP`、用户名换成你的）：

```powershell
.\scripts\deploy-aliyun.ps1 `
  -EcsHost ECS_IP `
  -User root `
  -PackagePath "D:\Downloads\football-analytics-migration-20260825-120000.tar.gz"
```

部署脚本**不会再读取当前电脑的数据库**。它只上传指定迁移包；若 ECS 已有库，会先停后端并保留 `football.db.pre-migration-*`，再解包、生成环境配置并执行 `docker compose up -d --build`。

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
- 登录后核对【比赛】/【赛果】是否与权威设备一致
- 服务器执行：`docker compose exec backend python manage.py model-status`
- 核对 `migration-manifest.json` 中的代码提交、数据库和模型哈希
- 在数据库中统计盘口来源，确认生产样本确为 Pinnacle；不要只根据前端标签判断

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
