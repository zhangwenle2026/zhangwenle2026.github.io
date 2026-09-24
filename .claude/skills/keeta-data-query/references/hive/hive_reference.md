# Keeta Hive SQL 执行参考

## 前提条件

Hive 查询通过 `mtcli kdata meta bi-hive-*` 执行业务调用，登录态由 mtcli 统一处理：
1. 已缓存目标 `ssoid`
2. 单 audience 场景的 MOA local exchange
3. `mtcli auth sso login` 保存的 SSO 登录缓存

> ⚠️ 若报登录态失效或鉴权失败，先执行 `mtcli auth sso whoami`，必要时执行 `mtcli auth sso login` 后重试。

## SQL 生成规范

生成或执行 Hive SQL 前，必须通过元数据命令验证表名和字段存在，禁止凭印象写表名或字段名。

```bash
# 只有业务关键词时，先找候选表
kdata meta table bi "<关键词>"

# 已有完整表名时，查字段和分区
kdata table info <schema>.<table>
```

只有在用户明确给出完整表名，且本次会话中已验证过该表和相关字段时，才可以跳过重复验表。

| 规范 | 说明 |
|------|------|
| 天分区 | `dt`，格式 `yyyymmdd` |
| 小时分区 | `dt_hour`，格式 `yyyymmddhh`，范围写法：`>= '2026030100' AND < '2026040100'` |
| 地区过滤 | `WHERE region = 'SA'`（SA/HK/AE/QA/KW/BR/BH/OM） |
| 成单口径 | `is_arrange = 1` |
| 排除取消 | `status != 50` 或 `status = 40` |
| 金额单位 | 最小辅币，除以精度换算为展示值 |
| 时间戳转换 | `from_unixtime(order_time / 1000, 'yyyy-MM-dd')` |

## 执行 SQL

```bash
# 提交 SQL 并等待结果
# 方式1：直接传 SQL 文本（自动转为临时文件）
kdata hive run "SELECT dt, COUNT(*) as cnt FROM mart_sailor_global.topic_ord_info_d WHERE dt='20260324' GROUP BY dt LIMIT 10"

# 方式2：传已有的 SQL 文件路径
kdata hive run /path/to/query.sql

# 异步提交（返回 query_id）
kdata hive submit "SELECT ..." --queue default

# 查状态 / 拉结果
kdata hive status <query_id>
kdata hive result <query_id>

# 列出可用工作空间和队列
kdata hive spaces
kdata hive queues
```

底层脚本：`scripts/capability2_hive/keeta_bi_skill.py`

> ⚠️ 推荐统一使用 `kdata hive run` 命令，自动处理 SQL 文件转换、项目空间、日志上报等。

常用队列：`root.fra02.hadoop-sailor.query`

## 异步查询轮询规则

`kdata hive submit` 返回 `query_id` 后，按以下规则执行 `kdata hive status <query_id>` / `kdata hive result <query_id>`：

- 轮询间隔：每 10 秒执行一次 `kdata hive status <query_id>`。
- 最大轮询次数：30 次，即最多等待 5 分钟。
- 成功时：执行 `kdata hive result <query_id>` 获取结果。
- `FAILED` / `CANCELLED` 时：立即终止并输出错误信息。
- 达到最大轮询次数仍未完成时：停止轮询，告知用户查询可能仍在运行，并给出 `query_id`，后续可用 `kdata hive status <query_id>` 或 `kdata hive result <query_id>` 继续查看。

## 权限处理流程

### 第一步：个人空间执行
默认不带 `--project`，用个人空间执行。

### 第二步：权限错误 → 询问用户切换项目空间
若报权限相关错误（`库表字段权限不足`、`Schema xxx does not exist`、`access denied` 等），执行 `kdata hive spaces` 获取项目空间列表，询问用户：

> 个人空间无表权限，你有以下项目空间权限：
> - `108359` sailor-bi
> - `109495` sailor-product-data
>
> 是否指定某个项目空间，或由我依次尝试？

根据用户回应用 `--project <ID>` 重新执行。

### 第三步：所有空间都无权限 → 提供申请链接
若个人空间和所有项目空间均失败，CLI 输出内容中会包含申请链接，**直接将其展示给用户**：

```
无表权限，可申请以下表的访问权限（个人空间，建议申请 6 个月有效期，并选择所需 region）：
  - mart_sailor_global.topic_ord_order_refund_d
    申请链接：https://data.keetapp.com/hetu/tableApply?applyType=external&providerType=person&refer=role&source=DW_ONESQL_DB_CONNECT_URL&database=mart_sailor_global&table=topic_ord_order_refund_d
```

> ⚠️ 申请时注意：
> - 有效期选择 **6 个月**（默认为 1 天）
> - 若该表有行权限控制（如 region），需在申请页面手动选择所需 region

## 常用表

详见 [common_tables.md](common_tables.md)
