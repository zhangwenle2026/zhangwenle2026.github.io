SELECT 
  CASE 
    WHEN third_city_name_en IN ('Sao Paulo - Northeast', 'Guarulhos', 'Santo Andre', 'Sao Bernardo do Campo', 'Osasco - North') THEN 'Northeast'
    WHEN third_city_name_en IN ('Sao Paulo - Western', 'Sao Paulo - Central', 'Barueri', 'Osasco - South') THEN 'Western'
    WHEN third_city_name_en IN ('Santos', 'Sao Vicente', 'Praia Grande') THEN 'Santos'
    WHEN third_city_name_en IN ('Sao Paulo - Southern', 'Sao Paulo - Eastern', 'Campinas', 'Guaruja', 'Diadema', 'Maua') THEN 'Southern'
    ELSE 'Other'
  END AS city_region,
  SUM(fin_ord_num) AS finish_orders,
  SUM(pay_cancel_ord_num) AS pay_cancel,
  SUM(fin_ord_num) + SUM(pay_cancel_ord_num) AS total_paid,
  ROUND(SUM(pay_cancel_ord_num) * 100.0 / NULLIF(SUM(fin_ord_num) + SUM(pay_cancel_ord_num), 0), 2) AS cancel_rate_pct
FROM mart_sailor_global.topic_shop_supply_d
WHERE dt BETWEEN '20260607' AND '20260613'
  AND region = 'BR'
GROUP BY 
  CASE 
    WHEN third_city_name_en IN ('Sao Paulo - Northeast', 'Guarulhos', 'Santo Andre', 'Sao Bernardo do Campo', 'Osasco - North') THEN 'Northeast'
    WHEN third_city_name_en IN ('Sao Paulo - Western', 'Sao Paulo - Central', 'Barueri', 'Osasco - South') THEN 'Western'
    WHEN third_city_name_en IN ('Santos', 'Sao Vicente', 'Praia Grande') THEN 'Santos'
    WHEN third_city_name_en IN ('Sao Paulo - Southern', 'Sao Paulo - Eastern', 'Campinas', 'Guaruja', 'Diadema', 'Maua') THEN 'Southern'
    ELSE 'Other'
  END
ORDER BY city_region
