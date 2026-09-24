-- Operating Rate by priority (MH/Top/Mid), city, 6.13
-- MH: is_musthave=1 in topic_supply_lead_wide_d
-- Top: newsign_tier IN ('is_priority_new','is_potential') and NOT MH
-- Mid: newsign_tier = 'is_normal' and NOT MH
SELECT
    o.org_3_name as city,
    CASE
        WHEN l.is_musthave = 1 THEN 'MH'
        WHEN l.newsign_tier IN ('is_priority_new','is_potential') THEN 'Top'
        ELSE 'Mid'
    END as priority,
    COUNT(DISTINCT CASE WHEN t.total_open_duration >= 60 THEN t.shop_id END) as open_shops,
    COUNT(DISTINCT t.shop_id) as total_shops,
    ROUND(COUNT(DISTINCT CASE WHEN t.total_open_duration >= 60 THEN t.shop_id END) * 100.0
        / NULLIF(COUNT(DISTINCT t.shop_id), 0), 1) as operating_rate
FROM mart_sailor_global.topic_shop_supply_d t
JOIN mart_sailor_global.dim_sailor_aor_org_flat o
  ON t.shop_aor_id = o.aor_id AND o.region = 'BR'
JOIN mart_sailor_global.topic_supply_lead_wide_d l
  ON t.shop_id = l.shop_id AND l.dt = t.dt AND l.region = 'BR'
WHERE t.region = 'BR'
  AND t.dt = '20260613'
  AND o.org_2_name = 'Metropolitan Region'
  AND t.is_online_shop = 1
  AND l.lead_type = 1
  AND l.visible = 1
  AND l.shop_status_id BETWEEN 3 AND 4
GROUP BY o.org_3_name,
    CASE
        WHEN l.is_musthave = 1 THEN 'MH'
        WHEN l.newsign_tier IN ('is_priority_new','is_potential') THEN 'Top'
        ELSE 'Mid'
    END
ORDER BY city, priority
