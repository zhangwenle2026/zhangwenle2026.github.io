import json

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

print('=== DBR Daily Summary (BRT 2026-07-28) ===')
print()
if total_row:
    orders = int(total_row[3])
    gmv = float(total_row[5])
    aov = float(total_row[4])
    mtd = float(total_row[9])
    print(f'Orders: {orders:,} | GMV: R${gmv:,.0f} | AOV: R${aov:.2f} | MTD Rate: {mtd*100:.1f}%')
if northeast:
    print(f'Northeast: Orders={int(northeast[3]):,}, GMV=R${float(northeast[5]):,.0f}')
if santos:
    print(f'Santos: Orders={int(santos[3]):,}, GMV=R${float(santos[5]):,.0f}')
if ns_total:
    print(f'New Signs: Top={ns_total[3]}, Mid={ns_total[4]}, Must-have={ns_total[5] if len(ns_total)>5 else 0}')
if op_total:
    op_rate = float(op_total[5])
    print(f'Operation: Online={op_total[3]}, Active={op_total[4]}, Rate={op_rate*100:.1f}%')
if ux_total:
    cancel = float(ux_total[3])
    cancel_wow = float(ux_total[4])
    print(f'UX: Cancel Rate={cancel*100:.2f}% (WoW {cancel_wow*100:+.1f}%)')
if pr_total:
    print(f'Promo: Deep Disc={pr_total[3]}, Promo Rate={pr_total[4]}')
