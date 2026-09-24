SELECT shop_id, shop_name, shop_status,
       is_red_exclusive, is_yellow_exclusive, is_orange_exclusive,
       red_partnership_status, yellow_partnership_status, orange_partnership_status,
       is_red_online_shop, is_yellow_online_shop, is_orange_online_shop,
       red_create_time, yellow_create_time, orange_create_time,
       red_comment_cun, yellow_comment_cun
FROM mart_sailor_global.aggr_shop_info_d
WHERE shop_id = 159409596
  AND region = 'BR'
  AND dt = '20260910'
LIMIT 1
