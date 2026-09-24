#!/usr/bin/env python3
import json

with open('/mnt/openclaw/.openclaw/workspace/dbr_data_20260825.json') as f:
    data = json.load(f)

results = data['results']

# Parse Business Performance - find Metropolitan Region row
bp_rows = results['Business Performance']['data']['data']
bp_cols = results['Business Performance']['data']['columns']

# Find metro row (Metropolitan Region)
metro_row = None
for row in bp_rows:
    if row[1] == 'Metropolitan Region':
        metro_row = row
        break

# Find non-metro rows for city breakdown
city_rows = [row for row in bp_rows if row[1] != 'Metropolitan Region']

# Parse New Signs - get latest date data
ns_rows = results['New Signs']['data']['data']
ns_latest_date = ns_rows[0][0] if ns_rows else None
ns_by_priority = {}
for row in ns_rows:
    if row[0] == ns_latest_date:
        ns_by_priority[row[1]] = int(row[2])

# Parse Operation Performance - get latest date
op_rows = results['Operation Performance']['data']['data']
op_latest_date = op_rows[0][0] if op_rows else None
op_by_priority = {}
for row in op_rows:
    if row[0] == op_latest_date:
        op_by_priority[row[1]] = float(row[2])

# Parse User Experience - latest date
ux_rows = results['User Experience']['data']['data']
ux_latest = ux_rows[-1] if ux_rows else None

# Parse Promotion - latest date
promo_rows = results['Promotion']['data']['data']
promo_latest = promo_rows[-1] if promo_rows else None

# Calculate metrics
metro_orders = int(metro_row[3]) if metro_row else 0
metro_aov = float(metro_row[4]) if metro_row else 0
metro_gmv = float(metro_row[5]) if metro_row else 0
mtd_orders = float(metro_row[10]) if metro_row and len(metro_row) > 10 else 0

# WoW from the last wow column (index 11 seems to be orders wow)
orders_wow = float(metro_row[11]) if metro_row and len(metro_row) > 11 else 0
aov_wow = float(metro_row[12]) if metro_row and len(metro_row) > 12 else 0
gmv_wow = float(metro_row[13]) if metro_row and len(metro_row) > 13 else 0

# Cancel rate (from User Experience)
cancel_rate = float(ux_latest[1]) if ux_latest else 0
spill_rate = float(ux_latest[2]) if ux_latest else 0
missing_rate = float(ux_latest[3]) if ux_latest else 0

# New signings total
ns_total = sum(ns_by_priority.values())

# Op rates
op_top = op_by_priority.get('Top-Tier', 0) * 100
op_mid = op_by_priority.get('Mid-Tier', 0) * 100
op_must = op_by_priority.get('Must-have', 0) * 100

# Promotion
promo_discount = float(promo_latest[1]) * 100 if promo_latest else 0
promo_full = float(promo_latest[2]) * 100 if promo_latest else 0
promo_subsidy = float(promo_latest[3]) * 100 if promo_latest else 0

# Format date for display
data_date = "08/25"
data_date_full = "2026-08-25"

print(f"=== DBR Data Summary for {data_date} ===")
print(f"Metro Orders: {metro_orders:,}")
print(f"AOV: R$ {metro_aov:.2f}")
print(f"GMV: R$ {metro_gmv:,.2f}")
print(f"MTD Orders: {mtd_orders:,.0f}")
print(f"Orders WoW: {orders_wow*100:.1f}%")
print(f"AOV WoW: {aov_wow*100:.1f}%")
print(f"GMV WoW: {gmv_wow*100:.1f}%")
print(f"Cancel Rate: {cancel_rate*100:.1f}%")
print(f"New Signs: {ns_total} (Top:{ns_by_priority.get('Top-Tier',0)}, Mid:{ns_by_priority.get('Mid-Tier',0)}, Must:{ns_by_priority.get('Must-have',0)})")
print(f"Op Rates: Top {op_top:.1f}%, Mid {op_mid:.1f}%, Must {op_must:.1f}%")
print(f"Promo: Discount {promo_discount:.1f}%, Full {promo_full:.1f}%, Subsidy {promo_subsidy:.1f}%")
print(f"City rows: {len(city_rows)}")
for row in city_rows:
    print(f"  {row[2]}: {row[3]} orders, R$ {float(row[4]):.2f} AOV")

# Store parsed data for HTML generation
parsed = {
    "date": data_date,
    "date_full": data_date_full,
    "metro_orders": metro_orders,
    "metro_aov": metro_aov,
    "metro_gmv": metro_gmv,
    "mtd_orders": mtd_orders,
    "orders_wow": orders_wow,
    "aov_wow": aov_wow,
    "gmv_wow": gmv_wow,
    "cancel_rate": cancel_rate,
    "spill_rate": spill_rate,
    "missing_rate": missing_rate,
    "ns_total": ns_total,
    "ns_top": ns_by_priority.get('Top-Tier', 0),
    "ns_mid": ns_by_priority.get('Mid-Tier', 0),
    "ns_must": ns_by_priority.get('Must-have', 0),
    "op_top": op_top,
    "op_mid": op_mid,
    "op_must": op_must,
    "promo_discount": promo_discount,
    "promo_full": promo_full,
    "promo_subsidy": promo_subsidy,
    "city_rows": city_rows,
    "bp_cols": bp_cols,
}

with open('/mnt/openclaw/.openclaw/workspace/dbr_parsed_20260825.json', 'w') as f:
    json.dump(parsed, f, ensure_ascii=False, indent=2)

print("\nParsed data saved to dbr_parsed_20260825.json")
