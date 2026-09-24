-- Deep Discount coverage by city, 6.13
-- DD SPU = best seller (is_popular_spu=1) with discount >= 30% and price >= R$15
SELECT
    o.org_3_name as city,
    COUNT(DISTINCT t.shop_id) as pool_size,
    COUNT(DISTINCT CASE WHEN dd.dd_spu_cnt >= 1 THEN t.shop_id END) as dd_1plus_shops,
    COUNT(DISTINCT CASE WHEN dd.dd_spu_cnt >= 3 THEN t.shop_id END) as dd_3plus_shops,
    ROUND(COUNT(DISTINCT CASE WHEN dd.dd_spu_cnt >= 1 THEN t.shop_id END) * 100.0
        / NULLIF(COUNT(DISTINCT t.shop_id), 0), 1) as dd_1plus_rate,
    ROUND(COUNT(DISTINCT CASE WHEN dd.dd_spu_cnt >= 3 THEN t.shop_id END) * 100.0
        / NULLIF(COUNT(DISTINCT t.shop_id), 0), 1) as dd_3plus_rate
FROM mart_sailor_global.topic_shop_supply_d t
JOIN mart_sailor_global.dim_sailor_aor_org_flat o
  ON t.shop_aor_id = o.aor_id AND o.region = 'BR'
LEFT JOIN (
    SELECT k.shop_id, COUNT(DISTINCT k.spu_id) as dd_spu_cnt
    FROM mart_sailor_global.aggr_product_sku_info_d k
    JOIN mart_sailor_global.aggr_product_spu_info_d s
      ON k.shop_id = s.shop_id AND k.spu_id = s.spu_id AND k.dt = s.dt AND s.region = 'BR'
    WHERE k.region = 'BR'
      AND k.dt = '20260613'
      AND s.is_popular_spu = 1
      AND k.price >= 1500
      AND k.discount_product_benefitvalue * 1.0 / k.price >= 0.30
      AND k.spu_status = 1
      AND k.price > 0
    GROUP BY k.shop_id
) dd ON t.shop_id = dd.shop_id
WHERE t.region = 'BR'
  AND t.dt = '20260613'
  AND o.org_2_name = 'Metropolitan Region'
  AND t.is_online_shop = 1
  AND t.total_open_duration >= 60
GROUP BY o.org_3_name
ORDER BY city
