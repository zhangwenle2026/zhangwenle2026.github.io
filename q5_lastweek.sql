-- Last week orders & GMV by city (5.31-6.6) for WoW comparison
SELECT
    o.org_3_name as city,
    SUM(t.fin_ord_num) as orders,
    SUM(t.fin_orig_amt_no_tip) / 100.0 as gmv_brl,
    SUM(t.cancel_ord_num) as cancel_orders
FROM mart_sailor_global.topic_shop_supply_d t
JOIN mart_sailor_global.dim_sailor_aor_org_flat o
  ON t.shop_aor_id = o.aor_id AND o.region = 'BR'
WHERE t.region = 'BR'
  AND t.dt >= '20260531' AND t.dt <= '20260606'
  AND o.org_2_name = 'Metropolitan Region'
GROUP BY o.org_3_name
ORDER BY city
