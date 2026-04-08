# Travel Planner

当前版本: v1.4.4

版本规则:
- 当前版本号写在 `VERSION`
- 更新说明追加写入 `CHANGELOG.md`
- 保留历史记录，不删除旧版本说明

智能旅行规划助手 - API-only 版本

## 部署到 Railway

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template)

### 手动部署

1. 用 GitHub 登录 [Railway](https://railway.app)
2. New Project → Deploy from GitHub repo
3. 选择 `LHY-1/travel-planner` 仓库，`deploy` 分支
4. Railway 自动检测 Python 并部署

### 环境变量（可选）

| 变量名 | 说明 |
|--------|------|
| `TONGCHENG_TOKEN` | 同程 API token（提高限额） |
| `TONGCHENG_USER_ID` | 用户 ID |

## 本地运行

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

访问 http://localhost:8000
