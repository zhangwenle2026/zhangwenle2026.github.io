import json
from collections import defaultdict
from datetime import datetime

# Load merchant list data
with open('/mnt/openclaw/.openclaw/workspace/merchant_list_data.json', 'r') as f:
    data = json.load(f)

rows = data['data']['data']

# --- Helpers ---
def fmt_num(n):
    if isinstance(n, float):
        n = round(n, 2)
        if n == int(n):
            n = int(n)
    return f"{n:,}"

def fmt_pct(v):
    return f"{v*100:.1f}%"

def fmt_gmv(v):
    return f"R$ {v:,.2f}"

def parse_date(s):
    return f"{s[:4]}-{s[4:6]}-{s[6:]}"

# --- Process Data ---
cm_stats = defaultdict(lambda: {'orders': 0, 'gmv': 0.0, 'stores': 0, 'aov_sum': 0.0, 'exposure': 0.0, 'homepage': 0.0, 'ctr_sum': 0.0})
city_stats = defaultdict(lambda: {'orders': 0, 'gmv': 0.0, 'stores': 0, 'aov_sum': 0.0})
bdm_stats = defaultdict(lambda: {'orders': 0, 'gmv': 0.0, 'stores': 0, 'cm': ''})
bd_stats = defaultdict(lambda: {'orders': 0, 'gmv': 0.0, 'stores': 0, 'bdm': '', 'cm': ''})

for row in rows:
    orders = int(row[13]) if row[13] else 0
    aov = float(row[14]) if row[14] else 0.0
    gmv = float(row[15]) if row[15] else 0.0
    exposure = float(row[17]) if row[17] else 0.0
    homepage = float(row[18]) if row[18] else 0.0
    ctr = float(row[19]) if row[19] else 0.0
    
    cm = row[6] if row[6] else 'Unknown'
    city = row[5] if row[5] != 'NULL' else 'Other'
    bdm = row[7] if row[7] else 'Unknown'
    bd = row[8] if row[8] else 'Unknown'
    
    cm_stats[cm]['orders'] += orders
    cm_stats[cm]['gmv'] += gmv
    cm_stats[cm]['stores'] += 1
    cm_stats[cm]['aov_sum'] += aov
    cm_stats[cm]['exposure'] += exposure
    cm_stats[cm]['homepage'] += homepage
    cm_stats[cm]['ctr_sum'] += ctr
    
    city_stats[city]['orders'] += orders
    city_stats[city]['gmv'] += gmv
    city_stats[city]['stores'] += 1
    city_stats[city]['aov_sum'] += aov
    
    bdm_stats[bdm]['orders'] += orders
    bdm_stats[bdm]['gmv'] += gmv
    bdm_stats[bdm]['stores'] += 1
    bdm_stats[bdm]['cm'] = cm
    
    bd_stats[bd]['orders'] += orders
    bd_stats[bd]['gmv'] += gmv
    bd_stats[bd]['stores'] += 1
    bd_stats[bd]['bdm'] = bdm
    bd_stats[bd]['cm'] = cm

# Calculate totals
total_orders = sum(s['orders'] for s in cm_stats.values())
total_gmv = sum(s['gmv'] for s in cm_stats.values())
total_stores = sum(s['stores'] for s in cm_stats.values())
weighted_aov = total_gmv / total_orders if total_orders > 0 else 0

# Sort by orders descending
cm_sorted = sorted(cm_stats.items(), key=lambda x: -x[1]['orders'])
city_sorted = sorted(city_stats.items(), key=lambda x: -x[1]['orders'])
bdm_sorted = sorted(bdm_stats.items(), key=lambda x: -x[1]['orders'])
bd_sorted = sorted(bd_stats.items(), key=lambda x: -x[1]['orders'])

data_date = parse_date(rows[0][0]) if rows else 'N/A'

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
.header {
  text-align: center;
  margin-bottom: 20px;
}
.header h1 {
  font-size: 1.4rem;
  font-weight: 700;
  margin-bottom: 4px;
}
.header .subtitle {
  color: var(--muted);
  font-size: 0.85rem;
}
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
.kpi-card .value {
  font-size: 1.6rem;
  font-weight: 700;
  margin-bottom: 4px;
}
.kpi-card .delta {
  font-size: 0.8rem;
  color: var(--muted);
}
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
.table-wrap {
  overflow-x: auto;
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8rem;
}
th, td {
  padding: 8px 10px;
  text-align: left;
  border-bottom: 1px solid var(--border);
}
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
  <h1>SP Metropolitan Region · Business Platform <span class="version-badge">v3.2</span></h1>
  <div class="subtitle">Data: ''' + data_date + ''' (BRT) · SMB Dashboard</div>
</div>

<div class="kpi-grid">
  <div class="kpi-card">
    <div class="label">Total Orders</div>
    <div class="value" style="color:var(--green)">''' + fmt_num(total_orders) + '''</div>
    <div class="delta">''' + fmt_num(total_stores) + ''' stores</div>
  </div>
  <div class="kpi-card">
    <div class="label">Total GMV</div>
    <div class="value" style="color:var(--cyan)">''' + fmt_gmv(total_gmv) + '''</div>
    <div class="delta">Daily</div>
  </div>
  <div class="kpi-card">
    <div class="label">Avg AOV</div>
    <div class="value" style="color:var(--yellow)">''' + fmt_gmv(weighted_aov) + '''</div>
    <div class="delta">Weighted average</div>
  </div>
  <div class="kpi-card">
    <div class="label">Store Avg Orders</div>
    <div class="value" style="color:var(--blue)">''' + fmt_num(round(total_orders/total_stores, 1)) + '''</div>
    <div class="delta">Per store</div>
  </div>
</div>
'''

# CM Performance Section
html += '''<div class="section">
  <h2>CM Business Performance</h2>
  <div class="table-wrap">
    <table>
      <tr><th>CM</th><th class="num-col">Orders</th><th class="num-col">GMV</th><th class="num-col">Stores</th><th class="num-col">Avg AOV</th><th class="num-col">Store Avg</th></tr>
'''
for cm, s in cm_sorted:
    avg_aov = s['aov_sum'] / s['stores'] if s['stores'] > 0 else 0
    store_avg = s['orders'] / s['stores'] if s['stores'] > 0 else 0
    html += f'      <tr><td>{cm}</td><td class="num-col">{fmt_num(s["orders"])}</td><td class="num-col">{fmt_gmv(s["gmv"])}</td><td class="num-col">{fmt_num(s["stores"])}</td><td class="num-col">{fmt_gmv(avg_aov)}</td><td class="num-col">{fmt_num(round(store_avg,1))}</td></tr>\n'
html += f'      <tr class="total-row"><td>Total</td><td class="num-col">{fmt_num(total_orders)}</td><td class="num-col">{fmt_gmv(total_gmv)}</td><td class="num-col">{fmt_num(total_stores)}</td><td class="num-col">{fmt_gmv(weighted_aov)}</td><td class="num-col">{fmt_num(round(total_orders/total_stores,1))}</td></tr>\n'
html += '''    </table>
  </div>
</div>
'''

# City Performance Section
html += '''<div class="section">
  <h2>City Performance</h2>
  <div class="table-wrap">
    <table>
      <tr><th>City</th><th class="num-col">Orders</th><th class="num-col">GMV</th><th class="num-col">Stores</th><th class="num-col">Avg AOV</th><th class="num-col">Store Avg</th></tr>
'''
for city, s in city_sorted:
    avg_aov = s['aov_sum'] / s['stores'] if s['stores'] > 0 else 0
    store_avg = s['orders'] / s['stores'] if s['stores'] > 0 else 0
    html += f'      <tr><td>{city}</td><td class="num-col">{fmt_num(s["orders"])}</td><td class="num-col">{fmt_gmv(s["gmv"])}</td><td class="num-col">{fmt_num(s["stores"])}</td><td class="num-col">{fmt_gmv(avg_aov)}</td><td class="num-col">{fmt_num(round(store_avg,1))}</td></tr>\n'
html += '''    </table>
  </div>
</div>
'''

# BDM Performance Section (top 15)
html += '''<div class="section">
  <h2>BDM Performance (Top 15)</h2>
  <div class="table-wrap">
    <table>
      <tr><th>BDM</th><th>CM</th><th class="num-col">Orders</th><th class="num-col">GMV</th><th class="num-col">Stores</th><th class="num-col">Store Avg</th></tr>
'''
for bdm, s in bdm_sorted[:15]:
    store_avg = s['orders'] / s['stores'] if s['stores'] > 0 else 0
    html += f'      <tr><td>{bdm}</td><td>{s["cm"]}</td><td class="num-col">{fmt_num(s["orders"])}</td><td class="num-col">{fmt_gmv(s["gmv"])}</td><td class="num-col">{fmt_num(s["stores"])}</td><td class="num-col">{fmt_num(round(store_avg,1))}</td></tr>\n'
html += '''    </table>
  </div>
</div>
'''

# BD Performance Section (top 20)
html += '''<div class="section">
  <h2>BD Performance (Top 20)</h2>
  <div class="table-wrap">
    <table>
      <tr><th>BD</th><th>BDM</th><th>CM</th><th class="num-col">Orders</th><th class="num-col">GMV</th><th class="num-col">Stores</th><th class="num-col">Store Avg</th></tr>
'''
for bd, s in bd_sorted[:20]:
    store_avg = s['orders'] / s['stores'] if s['stores'] > 0 else 0
    html += f'      <tr><td>{bd}</td><td>{s["bdm"]}</td><td>{s["cm"]}</td><td class="num-col">{fmt_num(s["orders"])}</td><td class="num-col">{fmt_gmv(s["gmv"])}</td><td class="num-col">{fmt_num(s["stores"])}</td><td class="num-col">{fmt_num(round(store_avg,1))}</td></tr>\n'
html += '''    </table>
  </div>
</div>
'''

html += '''<div class="footer">
  Business Platform Dashboard | Data Source: BI #300001446 | Generated: ''' + datetime.now().strftime('%Y-%m-%d %H:%M') + ''' CST
</div>
</body>
</html>
'''

with open('/mnt/openclaw/.openclaw/workspace/bp_dashboard.html', 'w') as f:
    f.write(html)

print("Dashboard generated: bp_dashboard.html")
print(f"Total Orders: {fmt_num(total_orders)}")
print(f"Total GMV: {fmt_gmv(total_gmv)}")
print(f"Stores: {fmt_num(total_stores)}")
