import json

# Use dbr_data_20260728.json which has complete data including Operation/UX
with open('/mnt/openclaw/.openclaw/workspace/dbr_data_20260728.json') as f:
    data = json.load(f)

results = data.get('results', {})

# Business Performance
bp = results.get('Business Performance', {}).get('data', {}).get('data', [])
total_row = [r for r in bp if r[2] == 'NULL'][0] if bp else None
northeast = [r for r in bp if 'Northeast' in str(r[2])][0] if bp else None
santos = [r for r in bp if 'Santos' in str(r[2])][0] if bp else None

# New Signs
ns = results.get('New Signs', {}).get('data', {}).get('data', [])
ns_total = [r for r in ns if r[2] == 'NULL'][0] if ns else None

# Operation
op = results.get('Operation Performance', {}).get('data', {}).get('data', [])
op_total = [r for r in op if r[2] == 'NULL'][0] if op else None

# UX
ux = results.get('User Experience', {}).get('data', {}).get('data', [])
ux_total = [r for r in ux if r[2] == 'NULL'][0] if ux else None

# Promo
pr = results.get('Promotion', {}).get('data', {}).get('data', [])
pr_total = [r for r in pr if r[2] == 'NULL'][0] if pr else None

print('=== SP Metropolitan Region DBR Daily Report ===')
print('Data Date: BRT 2026-07-28 (BI: 2026-07-27)')
print()

if total_row:
    orders = int(total_row[3])
    gmv = float(total_row[5])
    aov = float(total_row[4])
    mtd = float(total_row[9])
    mtd_orders = int(float(total_row[10])) if len(total_row) > 10 else 0
    print(f'📊 Business Performance (Metro Total)')
    print(f'   Orders: {orders:,} | GMV: R${gmv:,.0f} | AOV: R${aov:.2f}')
    print(f'   MTD Orders: {mtd_orders:,} | MTD Avg Daily: {mtd:.1f}')
    print()

if northeast:
    print(f'📍 Northeast São Paulo Metropolitan')
    print(f'   Orders: {int(northeast[3]):,} | GMV: R${float(northeast[5]):,.0f}')
    print()

if santos:
    print(f'📍 Santos City')
    print(f'   Orders: {int(santos[3]):,} | GMV: R${float(santos[5]):,.0f}')
    print()

if ns_total:
    top_yest = ns_total[3]
    mid_yest = ns_total[4]
    mtd_top = ns_total[5]
    mtd_mid = ns_total[6]
    print(f'🆕 New Signs (昨日)')
    print(f'   Top-Tier: {top_yest} | Mid-Tier: {mid_yest}')
    print(f'   MTD Top: {mtd_top} | MTD Mid: {mtd_mid}')
    print()

if op_total:
    op_rate = float(op_total[5])
    print(f'⚙️ Operation Performance')
    print(f'   Online: {op_total[3]} | Active: {op_total[4]} | Rate: {op_rate*100:.1f}%')
    print()

if ux_total:
    cancel = float(ux_total[3])
    cancel_wow = float(ux_total[4])
    print(f'😊 User Experience')
    print(f'   Cancel Rate: {cancel*100:.2f}% (WoW {cancel_wow*100:+.1f}%)')
    if abs(cancel_wow) > 0.20:
        print(f'   ⚠️ Cancel rate change significant!')
    print()

if pr_total:
    print(f'🎁 Promotion')
    print(f'   Deep Discount: {pr_total[3]} | Promo Rate: {pr_total[4]}')
    print()

print('Data Source: BI 300001446')
print('Note: BI data shows 2026-07-27 as latest date. BRT 07-28 data may be delayed.')
