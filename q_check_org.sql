-- Check org_2_name values in dim_sailor_aor_org_flat
SELECT DISTINCT org_2_name
FROM mart_sailor_global.dim_sailor_aor_org_flat
WHERE region = 'BR'
LIMIT 20
