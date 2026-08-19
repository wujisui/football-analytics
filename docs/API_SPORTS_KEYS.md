# API-Sports Key 配置

官方 Key 只从数据库 `app_settings.api_sports_key` 读取。
多枚 Key 用英文逗号分隔，同一天配额耗尽会自动切换下一枚。

## 配置流程

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python manage.py init-db
# 启动后端与前端后：注册账号
python manage.py set-admin 你的账号
# 写入官方 Key（可多枚）
python manage.py set-api-sports-key keyA,keyB
# 或在前端「我的 → 管理员设置 → API-Sports 官方 Key」保存（需管理员登录密码）
python manage.py check-quota
```

## 相关能力（已收敛）

| 能力 | 说明 |
|------|------|
| 多 Key 自动切换 | 当天某枚耗尽 → 自动切下一枚，状态按调度时区日期重置 |
| 管理员 UI 配置 | 密码确认写入；界面只显示末 4 位 |
| CLI 写入 | `set-api-sports-key`，适合无 UI / 首次上线 |

清空比赛历史见 [RESET_MATCH_HISTORY.md](./RESET_MATCH_HISTORY.md)。
