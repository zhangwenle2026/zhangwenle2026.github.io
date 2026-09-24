# 鉴权说明 — keeta-data-query

## 统一鉴权策略

业务接口调用优先交给 `mtcli kdata ...`，由 mtcli 按目标环境处理 SSO 登录态、MOA local exchange 和登录缓存。
只有 mtcli schema 或服务端明确要求 `access-token` header 的接口（Origin，以及 XT 的兼容重试）才通过 `scripts/capability5_meta/auth.py` 获取 token 后传给 mtcli。

```python
from core.auth import get_token, get_mis
```

## 各服务 audience 速查

| 服务 | audience | 用法 | 脚本入口 |
|------|----------|------|---------|
| 魔数BI (bi.keetapp.com) | mtcli schema 管理 | mtcli 自动 SSO | `mtcli kdata meta bi-hive-*` |
| RAG (data.mykeeta.sankuai.com) | mtcli schema 管理 | mtcli 自动 SSO | `mtcli kdata meta rag-table-search` |
| 起源 (origin.keetapp.com) | `5af3aa3409` | Header: `access-token: <token>` | `get_origin_token()` |
| XT (xt.keetapp.com) | `xt` | 先尝试 mtcli 自动 SSO；若服务端要求 `access-token`，用 mtsso/CIBA token 重试 | `mtcli kdata meta xt-task-*` |
| 数据地图 (data.keetapp.com) | mtcli schema 管理 | mtcli 自动 SSO | `mtcli kdata meta datamap-*` |

## 换票命令

```bash
npx mtsso-moa-local-exchange --audience <audience>
# 返回: {"access_token": "AT_...", "expires_in": 10800}
```

## 认证检查

```bash
# 全量检查（BI / RAG / 起源 / XT / KM）
kdata meta auth

# 只检查指定链路，业务探活通过 mtcli 执行
kdata meta auth bi rag --json
```

## Token 缓存

进程级缓存 3h，提前 60s 刷新，无需手动管理。

## 故障排查

| 现象 | 原因 | 处理 |
|------|------|------|
| `mtcli 探活失败` | mtcli 登录态缺失、权限不足或服务异常 | 先执行 `mtcli auth sso whoami`，必要时 `mtcli auth sso login` |
| `mtsso 换票失败` | Origin / XT 显式 token 获取失败 | 确认大象 App 已登录 MOA，必要时走 CIBA 授权 |
| `npx: command not found` | Node.js 未安装 | `brew install node` |
| `mtsso-moa-local-exchange 失败` | 本地 mtsso 未安装 | `npm install -g mtsso-moa-local-exchange` |
