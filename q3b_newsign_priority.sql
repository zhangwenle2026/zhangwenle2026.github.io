-- New Signing this week (6.7-6.13) and June MTD by city & priority
-- Priority from topic_supply_lead_wide_d newsign_tier
SELECT
    o.org_3_name as city,
    CASE
        WHEN l.is_musthave = 1 THEN 'MH'
        WHEN l.newsign_tier IN ('is_priority_new','is_potential') THEN 'Top'
        ELSE 'Mid'
    END as priority,
    COUNT(DISTINCT CASE
        WHEN t.first_online_time >= '2026-06-07 00:00:00' AND t.first_online_time < '2026-06-14 00:00:00'
        THEN t.shop_id END) as weekly_new_sign,
    COUNT(DISTINCT CASE
        WHEN t.first_online_time >= '2026-06-01 00:00:00' AND t.first_online_time < '2026-06-14 00:00:00'
        THEN t.shop_id END) as mtd_new_sign
FROM mart_sailor_global.topic_shop_supply_d t
JOIN mart_sailor_global.dim_sailor_aor_org_flat o
  ON t.shop_aor_id = o.aor_id AND o.region = 'BR'
JOIN mart_sailor_global.topic_supply_lead_wide_d l
  ON t.shop_id = l.shop_id AND l.dt = t.dt AND l.region = 'BR'
WHERE t.region = 'BR'
  AND t.dt = '20260613'
  AND o.org_2_name = 'Metropolitan Region'
  AND l.lead_type = 1
  AND l.visible = 1
GROUP BY o.org_3_name,
    CASE
        WHEN l.is_musthave = 1 THEN 'MH'
        WHEN l.newsign_tier IN ('is_priority_new','is_potential') THEN 'Top'
        ELSE 'Mid'
    END
ORDER BY city, priority
