# 模式① 关键词检索 - DataMap/BI 找表

## 推荐调用方式

```bash
kdata table search "dim_shop_info" --limit 20
kdata meta table bi "骑手配送" --limit 20 --json
```

底层业务调用统一走 `mtcli kdata meta datamap-table-search`，由 mtcli 处理 SSO 登录态。

## 参数建议

- 每次 BI/DataMap 检索生成 3-5 个关键词，覆盖中文、英文缩写、表名前缀。
- 优先保留 `mart_sailor_global.*`、`sailor_analysis_global.*` 等 Keeta 可查询表；`mart_sailor_etl.*` 当前不可用，找表结果会剔除。
- 需要字段时启用包含字段的查询路径；最终以 `kdata table info <db.table>` 或 Hive `DESCRIBE` 复核。

| 业务概念 | 关键词候选 |
|---------|-------------|
| 客服/进线 | `csc`、`call`、`chat`、`cs_service` |
| 订单 | `order`、`ord` |
| 用户 | `user`、`uid` |
| 优惠券/券 | `coupon`、`voucher` |
| 兑换码/促销码 | `promo`、`promocode`、`exchange` |
| 骑手/配送 | `rider`、`delivery`、`dispatch` |
| 商家/餐厅 | `merchant`、`restaurant`、`poi` |
| 活动/营销 | `act`、`campaign`、`marketing` |
| 流量/点击 | `flow`、`click`、`pv`、`uv` |
| 支付/交易 | `pay`、`trade`、`settle` |
| 补贴/折扣 | `subsidy`、`discount` |
| 地理/城市 | `city`、`region`、`geo` |
| 退款/取消 | `refund`、`cancel` |
| 评价/评分 | `rating`、`review`、`evaluate` |
| 实验/AB | `exp`、`experiment`、`abtest` |
| 进线/工单 | `ticket`、`case`、`incoming` |

2 字符以下关键词（如 `cs`）命中质量差，尽量不要单独使用。

## 错误处理

| 错误 | 原因 | 处理 |
|------|------|------|
| `mtcli 命令失败` | mtcli 登录态缺失、权限不足或服务异常 | 先执行 `mtcli auth sso whoami`，必要时执行 `mtcli auth sso login` |
| 无匹配结果 | 关键词过窄或表不在 DataMap 覆盖范围 | 换更短/更宽泛的关键词，或结合 RAG 语义找表 |
| 字段信息不足 | 搜索结果摘要不完整 | 用 `kdata table info`、`kdata meta lineage columns` 或 Hive `DESCRIBE` 复核 |
