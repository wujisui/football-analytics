# 清空比赛历史（换盘口后从零攒 ML 样本）

换赛前盘口博彩公司后，旧盘口写入的特征 / 标签不宜继续训练。可用本流程清空**比赛相关数据**，保留用户账号。

## 会删除 / 会保留

| 删除 | 保留 |
|------|------|
| 赛程 `fixtures`、赛前包 `pre_match_data`、特征 `match_features` | 用户 `users`、会话 `user_sessions` |
| 每日推荐快照 `auto_pick_snapshots`、关注（含手动） | 过关方案 `bet_plans`（方案行保留，旧场次引用会失效） |
| 官方 API 快照 `api_snapshots`、积分榜快照 | 管理员开关等 `app_settings`（日推激励态会清掉） |
| `backend/data/models/` 下已训模型文件 | 联赛 `leagues`、球队 `teams`（含译名） |
| Redis / 本地 `api:football:*` 缓存 | |

## 方式 A：管理员设置一键清空（推荐）

1. 用 **is_admin** 账号登录前端（「我的」）。
2. 打开 **我的 → 管理员设置**。
3. 点 **一键清空**，核对预览数量。
4. 输入**当前管理员登录密码**，点 **确认清空**。
5. 再点 **立即同步**（或等免费配额 11:00），重新拉今天赛程与新盘口。
6. 样本攒够后再 `python manage.py train-model` / `train-ah-model` / `train-goals-model`。

说明：此接口要求管理员**会话登录**，不能只用 `X-Admin-Key`；密码按当前登录账号校验。

## 方式 B：命令行（另一台电脑 / 无 UI）

在目标机器上进入后端目录（已建好 `.venv` 且能连到本机 `football.db`）：

```powershell
cd backend
.\.venv\Scripts\Activate.ps1

# 1) 预览（不删）
python manage.py reset-match-history

# 2) 确认数量无误后执行
python manage.py reset-match-history --apply

# 3) 重新拉赛程盘口（消耗官方配额；或前端「立即同步」）
python manage.py trigger-task --name scheduled_fixtures_sync
```

Linux / macOS：

```bash
cd backend
source .venv/bin/activate
python manage.py reset-match-history
python manage.py reset-match-history --apply
python manage.py trigger-task --name scheduled_fixtures_sync
```

若数据库不在默认路径，先确认 `backend/data/football.db`（或 `.env` / `secrets.local.env` 中的库路径）指向要清空的那台机器上的文件。

## 清空后建议

1. 确认列表几乎为空后，再同步官方数据。
2. `python manage.py model-status` 应显示无可用旧权重 / 样本接近 0。
3. 等完场样本积累到训练门槛后再重训，不要用清空前的模型文件。
4. python manage.py train-model / model-status 看进度
更细的产品边界见根目录 `PROJECT_PLAN.md` 与 `backend/README.md`。
