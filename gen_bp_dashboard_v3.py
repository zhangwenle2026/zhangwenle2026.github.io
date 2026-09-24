#!/usr/bin/env python3
"""BP Dashboard generator v3 — adapted to new BI schema (Deep Discount merchant list, dt=20260920)."""
import json
from collections import defaultdict
from datetime import datetime

# Load new-schema merchant list data (from bi_all_charts.json Merchant List)
with open('/mnt/openclaw/.openclaw/workspace/bi_all_charts.json', 'r') as f:
    charts = json.load(f)

ml = charts['Merchant List']['data']
cols = ml['columns']
rows = ml['data'] if isinstance(ml['data'], list) else ml['data']['data']

COL = {name: i for i, name in enumerate(cols)}

# --- Helpers ---
def fmt_num(n):
    if isinstance(n, float):
        n = round(n, 2)
        if n == int(n):
            n = int(n)
    return f"{n:,}"

def fmt_pct(v):
    return f"{v*100:.1f}%"

def parse_date(s):
    return f"{s[:4]}-{s[4:6]}-{s[6:]}"

# --- Process Data ---
# Metrics: Deep Discount activity coverage by CM / BDM / BD, new signs, SPU pool status
cm_stats = defaultdict(lambda: {'shops': 0, 'new_sign': 0, 'active_dd': 0, 'pool_shops': 0, 'churn': 0, 'coverage_sum': 0.0})
bdm_stats = defaultdict(lambda: {'shops': 0, 'new_sign': 0, 'active_dd': 0, 'pool_shops': 0, 'churn': 0, 'coverage_sum': 0.0, 'cm': ''})
bd_stats = defaultdict(lambda: {'shops': 0, 'new_sign': 0, 'active_dd': 0, 'pool_shops': 0, 'churn': 0, 'coverage_sum': 0.0, 'bdm': '', 'cm': ''})
tier_stats = defaultdict(lambda: {'shops': 0, 'active_dd': 0})

for row in rows:
    rm = row[COL['rm']] or 'Unknown'
    cm = row[COL['cm']] if row[COL['cm']] and row[COL['cm']] != '_OTHER_' else rm
    bdm = row[COL['bdm']] if row[COL['bdm']] and row[COL['bdm']] != '_OTHER_' else cm
    bd = row[COL['bd']] if row[COL['bd']] and row[COL['bd']] != '_OTHER_' else bdm
    tier = row[COL['leadtag']] or 'Unknown'

    new_sign = int(row[COL['Is New Sign']] or 0)
    active_dd = int(row[COL['Is Active Deep Discount - 1+ Hotselling SPU Over 15']] or 0)
    coverage = float(row[COL['Active Coverage - 1+ Hotselling Deep Discount SPU Over 15']] or 0)
    is_churn = int(row[COL['Is Churn - 1+ Hotselling Deep Discounted SPU Over 15']] or 0)
    in_pool = int(row[COL['Pool Total SPUs']] or 0) > 0

    for stats, who in ((cm_stats, cm), (bdm_stats, bdm), (bd_stats, bd)):
        s = stats[who]
        s['shops'] += 1
        s['new_sign'] += new_sign
        s['active_dd'] += active_dd
        s['churn'] += is_churn
        s['coverage_sum'] += coverage
        if in_pool:
            s['pool_shops'] += 1

    tier_stats[tier]['shops'] += 1
    tier_stats[tier]['active_dd'] += active_dd

# Attach parent names
for bdm, s in bdm_stats.items():
    s['cm'] = cm if False else next((cm for key in cm_stats if False), '')
# simpler: rebuild parent mapping from rows
cm_of_bdm = {}
bdm_of_bd = {}
cm_of_bd = {}
for row in rows:
    rm = row[COL['rm']] or ''
    cm = row[COL['cm']] if row[COL['cm']] and row[COL['cm']] != '_OTHER_' else rm
    bdm = row[COL['bdm']] if row[COL['bdm']] and row[COL['bdm']] != '_OTHER_' else cm
    bd = row[COL['bd']] if row[COL['bd']] and row[COL['bd']] != '_OTHER_' else bdm
    cm_of_bdm[bdm] = cm
    bdm_of_bd[bd] = bdm
    cm_of_bd[bd] = cm
for bdm, s in bdm_stats.items():
    s['cm'] = cm_of_bdm.get(bdm, '')
for bd, s in bd_stats.items():
    s['bdm'] = bdm_of_bd.get(bd, '')
    s['cm'] = cm_of_bd.get(bd, '')

total_shops = sum(s['shops'] for s in cm_stats.values())
total_new_sign = sum(s['new_sign'] for s in cm_stats.values())
total_active_dd = sum(s['active_dd'] for s in cm_stats.values())
total_pool = sum(s['pool_shops'] for s in cm_stats.values())
total_churn = sum(s['churn'] for s in cm_stats.values())
overall_coverage = sum(s['coverage_sum'] for s in cm_stats.values()) / total_shops if total_shops else 0

cm_sorted = sorted(cm_stats.items(), key=lambda x: (-x[1]['active_dd'], x[0]))
bdm_sorted = sorted(bdm_stats.items(), key=lambda x: (-x[1]['active_dd'], x[0]))
bd_sorted = sorted(bd_stats.items(), key=lambda x: (-x[1]['active_dd'], x[0]))
tier_sorted = sorted(tier_stats.items(), key=lambda x: -x[1]['shops'])

# Use BDM-level performance chart data if available for the summary
data_date = '2026-09-20'

# --- Build HTML ---
html = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SP Metropolitan Region · Business Platform</title>
<style>
:root {
  --bg:#0f172a;
  --card:#1e293b;
  --text:#f1f5f9;
  --muted:#94a3b8;
  --green:#22c55e;
  --yellow:#eab308;
  --red:#ef4444;
  --blue:#3b82f6;
  --cyan:#06b6d4;
  --purple:#a855f7;
  --orange:#f97316;
  --border:#334155;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background: var(--bg);
  color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  padding: 16px;
  line-height: 1.5;
}
.header { text-align: center; margin-bottom: 20px; }
.header h1 { font-size: 1.4rem; font-weight: 700; margin-bottom: 4px; }
.header .subtitle { color: var(--muted); font-size: 0.85rem; }
.version-badge {
  display: inline-block;
  background: rgba(59,130,246,0.15);
  color: var(--blue);
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 0.7rem;
  margin-left: 8px;
}
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
  margin-bottom: 24px;
}
.kpi-card {
  background: var(--card);
  border-radius: 12px;
  padding: 18px 14px;
  text-align: center;
  border: 1px solid var(--border);
}
.kpi-card .label {
  color: var(--muted);
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.6px;
  margin-bottom: 8px;
}
.kpi-card .value { font-size: 1.6rem; font-weight: 700; margin-bottom: 4px; }
.kpi-card .delta { font-size: 0.8rem; color: var(--muted); }
.section {
  background: var(--card);
  border-radius: 12px;
  padding: 18px;
  margin-bottom: 18px;
  border: 1px solid var(--border);
}
.section h2 {
  font-size: 1rem;
  font-weight: 600;
  margin-bottom: 14px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.section h2::before {
  content: '';
  display: inline-block;
  width: 4px;
  height: 16px;
  background: var(--blue);
  border-radius: 2px;
}
.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 0.8rem; }
th, td { padding: 8px 10px; text-align: left; border-bottom: 1px solid var(--border); }
th {
  color: var(--muted);
  font-weight: 500;
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.4px;
  white-space: nowrap;
}
tr:hover { background: rgba(255,255,255,0.03); }
.num-col { text-align: right; font-variant-numeric: tabular-nums; }
.total-row { font-weight: 700; background: rgba(59,130,246,0.08); }
.total-row td { border-top: 2px solid var(--border); }
.bar-cell { min-width: 120px; }
.bar { height: 6px; border-radius: 3px; background: var(--blue); min-width: 2px; }
.footer {
  text-align: center;
  color: var(--muted);
  font-size: 0.7rem;
  margin-top: 16px;
  padding-bottom: 20px;
}
@media (max-width: 600px) {
  body { padding: 10px; }
  .kpi-card .value { font-size: 1.3rem; }
  th, td { padding: 6px 8px; font-size: 0.75rem; }
}
</style>
</head>
<body>
<div class="header">
  <h1>SP Metropolitan Region · Business Platform <span class="version-badge">v4 Deep Discount</span></h1>
  <div class="subtitle">Data: ''' + data_date + ''' (BRT) · SMB Dashboard · Deep Discount Coverage</div>
</div>

<div class="kpi-grid">
  <div class="kpi-card">
    <div class="label">Total Shops</div>
    <div class="value" style="color:var(--blue)">''' + fmt_num(total_shops) + '''</div>
    <div class="delta">In merchant list</div>
  </div>
  <div class="kpi-card">
    <div class="label">Active Deep Discount</div>
    <div class="value" style="color:var(--green)">''' + fmt_num(total_active_dd) + '''</div>
    <div class="delta">''' + fmt_pct(total_active_dd/total_shops if total_shops else 0) + ''' of shops</div>
  </div>
  <div class="kpi-card">
    <div class="label">New Signs</div>
    <div class="value" style="color:var(--cyan)">''' + fmt_num(total_new_sign) + '''</div>
    <div class="delta">MTD</div>
  </div>
  <div class="kpi-card">
    <div class="label">Churned (DD)</div>
    <div class="value" style="color:var(--red)">''' + fmt_num(total_churn) + '''</div>
    <div class="delta">1+ Hotselling DD Over 15</div>
  </div>
  <div class="kpi-card">
    <div class="label">Avg DD Coverage</div>
    <div class="value" style="color:var(--yellow)">''' + fmt_pct(overall_coverage) + '''</div>
    <div class="delta">1+ Hotselling Over R$15</div>
  </div>
</div>
'''

def coverage_bar(v):
    pct = max(0, min(100, v*100))
    color = 'var(--green)' if pct >= 60 else ('var(--yellow)' if pct >= 30 else 'var(--red)')
    return f'<div class="bar-cell"><div class="bar" style="width:{pct:.0f}%;background:{color}"></div></div>'

# CM Performance Section
html += '''<div class="section">
  <h2>CM Deep Discount Performance</h2>
  <div class="table-wrap">
    <table>
      <tr><th>CM</th><th class="num-col">Shops</th><th class="num-col">Active DD</th><th class="num-col">DD Rate</th><th class="num-col">Avg Coverage</th><th class="num-col">New Sign</th><th class="num-col">Churn</th></tr>
'''
for cm, s in cm_sorted:
    dd_rate = s['active_dd']/s['shops'] if s['shops'] else 0
    avg_cov = s['coverage_sum']/s['shops'] if s['shops'] else 0
    html += (f'      <tr><td>{cm}</td><td class="num-col">{fmt_num(s["shops"])}</td>'
             f'<td class="num-col">{fmt_num(s["active_dd"])}</td><td class="num-col">{fmt_pct(dd_rate)}</td>'
             f'<td class="num-col">{fmt_pct(avg_cov)}</td><td class="num-col">{fmt_num(s["new_sign"])}</td>'
             f'<td class="num-col">{fmt_num(s["churn"])}</td></tr>\n')
html += (f'      <tr class="total-row"><td>Total</td><td class="num-col">{fmt_num(total_shops)}</td>'
         f'<td class="num-col">{fmt_num(total_active_dd)}</td><td class="num-col">{fmt_pct(total_active_dd/total_shops if total_shops else 0)}</td>'
         f'<td class="num-col">{fmt_pct(overall_coverage)}</td><td class="num-col">{fmt_num(total_new_sign)}</td>'
         f'<td class="num-col">{fmt_num(total_churn)}</td></tr>\n')
html += '''    </table>
  </div>
</div>
'''

# BDM Performance Section
html += '''<div class="section">
  <h2>BDM Deep Discount Performance</h2>
  <div class="table-wrap">
    <table>
      <tr><th>BDM</th><th>CM</th><th class="num-col">Shops</th><th class="num-col">Active DD</th><th class="num-col">DD Rate</th><th class="num-col">Avg Coverage</th><th class="num-col">New Sign</th></tr>
'''
for bdm, s in bdm_sorted:
    dd_rate = s['active_dd']/s['shops'] if s['shops'] else 0
    avg_cov = s['coverage_sum']/s['shops'] if s['shops'] else 0
    html += (f'      <tr><td>{bdm}</td><td>{s["cm"]}</td><td class="num-col">{fmt_num(s["shops"])}</td>'
             f'<td class="num-col">{fmt_num(s["active_dd"])}</td><td class="num-col">{fmt_pct(dd_rate)}</td>'
             f'<td class="num-col">{fmt_pct(avg_cov)}</td><td class="num-col">{fmt_num(s["new_sign"])}</td></tr>\n')
html += '''    </table>
  </div>
</div>
'''

# BD Top 20
html += '''<div class="section">
  <h2>BD Performance (Top 20 by Active DD)</h2>
  <div class="table-wrap">
    <table>
      <tr><th>BD</th><th>BDM</th><th class="num-col">Shops</th><th class="num-col">Active DD</th><th class="num-col">DD Rate</th><th class="num-col">New Sign</th></tr>
'''
for bd, s in bd_sorted[:20]:
    dd_rate = s['active_dd']/s['shops'] if s['shops'] else 0
    html += (f'      <tr><td>{bd}</td><td>{s["bdm"]}</td><td class="num-col">{fmt_num(s["shops"])}</td>'
             f'<td class="num-col">{fmt_num(s["active_dd"])}</td><td class="num-col">{fmt_pct(dd_rate)}</td>'
             f'<td class="num-col">{fmt_num(s["new_sign"])}</td></tr>\n')
html += '''    </table>
  </div>
</div>
'''

# Tier distribution
html += '''<div class="section">
  <h2>Merchant Tier Distribution</h2>
  <div class="table-wrap">
    <table>
      <tr><th>Tier</th><th class="num-col">Shops</th><th class="num-col">Active DD</th><th class="num-col">DD Rate</th></tr>
'''
for tier, s in tier_sorted:
    dd_rate = s['active_dd']/s['shops'] if s['shops'] else 0
    html += (f'      <tr><td>{tier}</td><td class="num-col">{fmt_num(s["shops"])}</td>'
             f'<td class="num-col">{fmt_num(s["active_dd"])}</td><td class="num-col">{fmt_pct(dd_rate)}</td></tr>\n')
html += '''    </table>
  </div>
</div>
'''

html += '''<div class="footer">
  Business Platform Dashboard | Data Source: BI #300001446 (Deep Discount model) | Generated: ''' + datetime.now().strftime('%Y-%m-%d %H:%M') + ''' CST
</div>
</body>
</html>
'''

with open('/mnt/openclaw/.openclaw/workspace/bp_dashboard.html', 'w') as f:
    f.write(html)

print("Dashboard generated: bp_dashboard.html")
print(f"Total Shops: {fmt_num(total_shops)}, Active DD: {fmt_num(total_active_dd)} ({fmt_pct(total_active_dd/total_shops if total_shops else 0)})")
print(f"New Signs: {fmt_num(total_new_sign)}, Churn: {fmt_num(total_churn)}, Avg Coverage: {fmt_pct(overall_coverage)}")
print(f"CMs: {len(cm_sorted)}, BDMs: {len(bdm_sorted)}, BDs: {len(bd_sorted)}")
