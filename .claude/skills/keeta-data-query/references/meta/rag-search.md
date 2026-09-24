# 模式② 语义检索 - RAG 找表

## 推荐调用方式

```bash
kdata meta table rag "骑手上线时长相关的 Hive 表" --json
kdata meta rag "骑手上线时长相关的 Hive 表" --type table --json
```

底层业务调用统一走 `mtcli kdata meta rag-table-search`，由 mtcli 处理 SSO 登录态。不要从浏览器 CDP 读取 Cookie，也不要在脚本里直接请求 RAG HTTP 接口。

## 查询类型

| type | 用途 |
|------|------|
| `table` | 找表，默认主场景 |
| `business` | 业务知识查询 |
| `metric` | 指标定义和口径 |

## 使用策略

- 用户描述偏自然语言、业务概念不明确时，优先用 RAG 扩展候选表。
- RAG 返回自然语言内容，需要结合表名、字段、推荐理由做二次判断。
- 最终落到 SQL 前，必须用 DataMap 表信息或 Hive `DESCRIBE` 复核字段和分区。

## 错误处理

| 错误 | 处理 |
|------|------|
| `mtcli 命令失败` | 执行 `mtcli auth sso whoami`，必要时执行 `mtcli auth sso login` 后重试 |
| 超时 | 放弃本轮 RAG，改用关键词检索和常用表参考 |
| 结果泛化 | 换更具体的业务词、地区、实体或指标词重试 |
