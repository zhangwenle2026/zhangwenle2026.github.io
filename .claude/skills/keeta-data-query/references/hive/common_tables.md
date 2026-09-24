# Keeta 境外常用 Hive 表

> 支持地区：SA=沙特、HK=香港、AE=阿联酋、QA=卡塔尔、KW=科威特、BR=巴西、BH=巴林、OM=阿曼

## mart_sailor_global（主要数仓）

| 表名 | 分区 | 描述 |
|------|------|------|
| fact_ord_submitted_h | dt_hour（小时） | 订单明细宽表，含 region/status/order_time/actual_pay |
| topic_ord_info_d | dt | 订单宽表（天），含更多扩展字段 |
| fact_act_coupon_use_record_d | dt | 优惠券使用记录 |
| fact_shop_marketing_d | dt | 商家营销数据 |
| fact_settle_marketing_credit_rebate_d | dt | 破独商户运费补贴结算明细 |
| fact_settle_merchant_charge_d | dt | 商家收费结算 |
| fact_settle_task_cost_d | dt | 任务成本结算 |
| fact_settle_courier_task_settle_record_d | dt | 骑手任务结算记录 |
| fact_delivery_waybill_task_base_d | dt | 配送任务基础数据 |
| fact_settle_3pl_courier_d | dt | 3PL 骑手结算数据 |
| dim_city_region | 无 | 城市-地区映射维表 |
| dim_date | 无 | 日期维表 |

## mart_sailor_finance_global（财务）

| 表名 | 分区 | 描述 |
|------|------|------|
| fact_sailorsettle_sailor_settle_rebate__bill_summary_d | dt | 返利账单汇总 |
| fact_sailorsettle_sailor_settle_rebate__bill_detail_d | dt | 返利账单明细 |

## 核心字段说明

### fact_ord_submitted_h

| 字段 | 类型 | 说明 |
|------|------|------|
| view_id | bigint | 订单 ID |
| region | string | 地区（SA/HK/AE/QA/KW/BR/BH） |
| status | int | 状态：10=提交 20=支付 30=履约 40=完成 50=取消 |
| order_time | bigint | 下单时间（毫秒） |
| actual_pay | bigint | 实付金额（最小辅币） |
| dt_hour | string | 分区，格式 yyyymmddhh |
| user_get_mode | string | delivery / pickup |
| city_id | bigint | 城市 ID |

### fact_settle_marketing_credit_rebate_d

| 字段 | 类型 | 说明 |
|------|------|------|
| rebate_id | - | 返利补贴 ID |
| entry_id | - | 单据 ID（外卖订单 ID） |
| entry_type | - | 单据类型，103=wm_order |
| scene_code | - | 返佣场景编码 |
| biz_code | - | 业务编码 |
| amount | - | 金额（最小辅币） |
| currency | - | 币种 |
| account_id | - | 结算用户 ID |
| region | - | 地区 |
| dt | - | 日期分区，格式 yyyymmdd |
