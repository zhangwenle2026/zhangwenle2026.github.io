-- Check priority_label values in aggr_shop_lead_info_all_d for Metro
SELECT
    a.priority_label,
    COUNT(DISTINCT a.lead_id) as cnt
FROM mart_sailor_global.aggr_shop_lead_info_all_d a
WHERE a.region = 'BR'
  AND a.valid = 1
  AND a.dt = '20260613'
GROUP BY a.priority_label
LIMIT 20
