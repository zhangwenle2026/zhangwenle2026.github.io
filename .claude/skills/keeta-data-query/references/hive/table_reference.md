# Keeta Hive 找表参考

## 前提条件

找表/查字段通过 `mtcli kdata meta datamap-table-search` 等命令执行，登录态由 mtcli 统一处理。

> ⚠️ 若报鉴权失败，先执行 `mtcli auth sso whoami`，必要时执行 `mtcli auth sso login` 后重试。

## 搜表 / 查字段

```bash
# 搜表（按关键词）
kdata table search mart_sailor_global

# 查单表字段（★=重要字段，[分区]=分区字段）
kdata table info mart_sailor_global.topic_ord_info_d
```

底层实现：`scripts/capability5_meta/table.py`

底层通过 mtcli contract 传递 `q/pageNum/pageSize/filters`，不要在 Skill 中手写 DataMap HTTP 请求。

## 常用表

详见 [common_tables.md](common_tables.md)
