# 模式⑤ ETL代码查询 — 完整实现（keeta-xt-etl-reader）

## 场景映射

| 用户说 | 调用方式 |
|--------|---------|
| 看 xxx 表的 ETL 代码/建表语句 | fetch --task-name hmart_sailor_global.xxx --format text |
| 查 xxx 表的字段定义/DDL | parse-ddl --task-name hmart_sailor_global.xxx --format text |
| 这张表谁负责/负责人是谁 | fetch（看 Creator 字段） |
| 强制拉最新代码（不用本地缓存） | fetch --from-source api |
| mtcli 登录态失效/401 | 先执行 `mtcli auth sso whoami`，必要时 `mtcli auth sso login` |

## 调用方式

```bash
SCRIPT=~/.openclaw/skills/keeta-xt-etl-reader/scripts/keeta_xt_etl_reader.py

# 查 ETL 代码（文本格式）
python3 $SCRIPT fetch --task-name hmart_sailor_global.<表名> --format text

# 只看字段定义
python3 $SCRIPT parse-ddl --task-name hmart_sailor_global.<表名> --format text

# 强制从 API 拉最新
python3 $SCRIPT fetch --task-name hmart_sailor_global.<表名> --from-source api --format text

# 如需强制指定历史 token，可传 --access-token；默认不需要
python3 $SCRIPT fetch --task-name hmart_sailor_global.<表名> --from-source api --access-token <token> --format text
```

## 任务名规则

- 格式：`hmart_sailor_global.<layer>_<table_name>`
- layer 为：fact / dim / aggr / topic / app
- 表名 `mart_sailor_global.xxx_d` → 任务名 `hmart_sailor_global.xxx_d`（mart_ 自动转换为 hmart_）

## fetch --format text 输出格式

```
Task Name: hmart_sailor_global.xxx
Description: ...
Creator: xxx@meituan.com
Target Table: mart_sailor_global.xxx

Columns:
  字段名  类型  注释
  ...

[ETL Code]
##Load##
...
```

## 登录方式

XT 在线查询通过 `mtcli kdata meta xt-task-info` 和 `mtcli kdata meta xt-task-code` 执行。

默认不读取 `.env`、`XT_ACCESS_TOKEN`、缓存文件或浏览器 CDP。脚本会先让 mtcli 处理 SSO；若 XT 服务端返回“请提供 access-token 头”，再通过 mtsso/CIBA 获取 token 并仍然通过 mtcli 重试。`--access-token` 仅作为人工排障时的显式覆盖参数。

## 错误处理

| 错误 | 原因 | 解决 |
|------|------|------|
| 401 / 登录态失效 | mtcli SSO 登录态缺失或过期 | 执行 `mtcli auth sso whoami`，必要时 `mtcli auth sso login` 后重试 |
| 本地文件不存在 | 本地仓库无该任务 | 加 --from-source api 强制走网络 |
| 任务名找不到 | 名称格式错误 | 检查格式：hmart_sailor_global.<layer>_<table_name> |
