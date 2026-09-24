-- Check is_priority and is_musthave distribution in Metro
SELECT
    l.is_musthave,
    l.is_priority,
    COUNT(DISTINCT l.shop_id) as shop_cnt
FROM mart_sailor_global.aggr_shop_lead_info_d l
WHERE l.region = 'BR'
  AND l.dt = '20260613'
GROUP BY l.is_musthave, l.is_priority
LIMIT 10
