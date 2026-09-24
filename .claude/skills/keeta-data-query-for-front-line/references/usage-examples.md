# 使用示例

## 基础命令

```bash
# 列出所有数据集
kdata-fl standard datasets

# 列出数据集指标（支持关键词过滤）
kdata-fl standard measures --dataset 60041382 --search 订单

# 列出数据集维度
kdata-fl standard dims --dataset 60041382

# 查维度可选值
kdata-fl standard dim-values global_region_code
```

## 单指标查询

```bash
kdata-fl standard query --dataset 60041382 --measures fin_ord_num \
  --date 20260609~20260609 --region SA \
  --biz-type 1278539788 --filter org_type_ids=SA_KA
```

## 带环比同比

```bash
# dod=日环比 / wow=周同比 / mom=月同比
kdata-fl standard query --dataset 60041382 --measures fin_ord_num \
  --date 20260603~20260609 --region SA \
  --biz-type 1278539788 --filter org_type_ids=SA_KA \
  --group-by dt --order-by dt=ASC --pops dod,wow
```

## 多指标查询

```bash
kdata-fl standard query --dataset 60041382 \
  --measures fin_ord_num actual_pay_no_tip_gmv \
  --date 20260609~20260609 --region SA \
  --biz-type 1278539788 --filter org_type_ids=SA_KA
```

## 多维度过滤

```bash
# ⚠️ 必须多次传 --filter，不能空格分隔
kdata-fl standard query --dataset 60041382 --measures actual_pay_no_tip_gmv \
  --date 20260609~20260609 --region SA \
  --biz-type 1278539788 --filter org_type_ids=SA_KA \
  --filter is_pickup=0 --filter shop_type_name=KA \
  --group-by brand_name --order-by actual_pay_no_tip_gmv=DESC --page-size 10
```

## 常用维度

| 维度 | 字段名（dim_code） |
|---|---|
| Region | global_region_code、global_region_name |
| 门店 | shop_id、shop_name |
| 品牌 | brand_id、brand_name |
| 日期 | dt |
| 业务城市 | op_city_id、op_city_name |
| 取餐方式 | user_get_mode_id、user_get_mode_name |
