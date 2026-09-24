-- Check org_3_name under Metropolitan Region
SELECT DISTINCT org_3_name
FROM mart_sailor_global.dim_sailor_aor_org_flat
WHERE region = 'BR'
  AND org_2_name = 'Metropolitan Region'
LIMIT 20
