SELECT third_city_name_en, COUNT(*) as cnt, SUM(fin_ord_num) as orders
FROM mart_sailor_global.topic_shop_supply_d
WHERE dt = '20260613' AND region = 'BR'
GROUP BY third_city_name_en
ORDER BY orders DESC
LIMIT 50
