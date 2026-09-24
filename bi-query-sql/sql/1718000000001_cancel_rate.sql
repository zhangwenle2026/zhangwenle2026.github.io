SELECT 
  CASE 
    WHEN city_name IN ('São Paulo - Northeast', 'Guarulhos', 'Santo André', 'São Bernardo do Campo', 'Osasco - North') THEN 'Northeast'
    WHEN city_name IN ('São Paulo - Western', 'São Paulo - Central', 'Barueri', 'Osasco - South') THEN 'Western'
    WHEN city_name IN ('Santos', 'São Vicente', 'Praia Grande') THEN 'Santos'
    WHEN city_name IN ('São Paulo - Southern', 'São Paulo - Eastern', 'Campinas', 'Guarujá', 'Diadema', 'Mauá') THEN 'Southern'
    ELSE 'Other'
  END AS region,
  SUM(finish_ord_num) AS finish_orders,
  SUM(refund_after_pay_ord_num) AS cancel_after_pay,
  ROUND(SUM(refund_after_pay_ord_num) * 100.0 / NULLIF(SUM(finish_ord_num + refund_after_pay_ord_num), 0), 2) AS cancel_rate_pct
FROM mart_sailor_global.topic_shop_supply_d
WHERE dt BETWEEN '20260607' AND '20260613'
  AND country_code = 'BR'
GROUP BY 
  CASE 
    WHEN city_name IN ('São Paulo - Northeast', 'Guarulhos', 'Santo André', 'São Bernardo do Campo', 'Osasco - North') THEN 'Northeast'
    WHEN city_name IN ('São Paulo - Western', 'São Paulo - Central', 'Barueri', 'Osasco - South') THEN 'Western'
    WHEN city_name IN ('Santos', 'São Vicente', 'Praia Grande') THEN 'Santos'
    WHEN city_name IN ('São Paulo - Southern', 'São Paulo - Eastern', 'Campinas', 'Guarujá', 'Diadema', 'Mauá') THEN 'Southern'
    ELSE 'Other'
  END
HAVING region != 'Other'
ORDER BY region
