-- Operating Rate by priority, city, 6.13
-- Use aggr_shop_lead_info_d for is_musthave and is_priority
SELECT
    o.org_3_name as city,
    CASE
        WHEN l.is_musthave = 1 THEN 'MH'
        WHEN l.is_priority = 1 THEN 'Top'
        ELSE 'Mid'
    END as priority,
    COUNT(DISTINCT CASE WHEN t.total_open_duration >= 60 THEN t.shop_id END) as open_shops,
    COUNT(DISTINCT t.shop_id) as total_shops,
    ROUND(COUNT(DISTINCT CASE WHEN t.total_open_duration >= 60 THEN t.shop_id END) * 100.0
        / NULLIF(COUNT(DISTINCT t.shop_id), 0), 1) as operating_rate
FROM mart_sailor_global.topic_shop_supply_d t
JOIN mart_sailor_global.dim_sailor_aor_org_flat o
  ON t.shop_aor_id = o.aor_id AND o.region = 'BR'
JOIN mart_sailor_global.aggr_shop_lead_info_d l
  ON t.shop_id = l.shop_id AND l.dt = t.dt AND l.region = 'BR'
WHERE t.region = 'BR'
  AND t.dt = '20260613'
  AND o.org_2_name = 'Metropolitan Region'
  AND t.is_online_shop = 1
GROUP BY o.org_3_name,
    CASE
        WHEN l.is_musthave = 1 THEN 'MH'
        WHEN l.is_priority = 1 THEN 'Top'
        ELSE 'Mid'
    END
ORDER BY city, priority
