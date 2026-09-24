import json
from collections import defaultdict
from datetime import datetime

# Load data
with open('/mnt/openclaw/.openclaw/workspace/bi_raw_data.json', 'r') as f:
    data = json.load(f)

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

def priority_color(p):
    if p == 'Must-have':
        return '#06b6d4'  # cyan
    elif p == 'Mid-Tier':
        return '#eab308'  # yellow
    else:
        return '#e2e8f0'  # white/default

# --- Process Order Performance ---
order_raw = data['Last 10 Days - Order Performance']['data']['data']
orders = defaultdict(dict)
for row in order_raw:
    date, prio, val = row[0], row[1], int(row[2])
    orders[date][prio] = val

order_dates = sorted(orders.keys(), reverse=True)
order_total = sum(v for d in orders.values() for v in d.values())

latest_date = parse_date(order_dates[0]) if order_dates else 'N/A'

# --- Process New Signs ---
sign_raw = data['Last 10 days - New Signs']['data']['data']
signs = defaultdict(dict)
for row in sign_raw:
    date, prio, val = row[0], row[1], int(row[2])
    signs[date][prio] = val

sign_total = sum(v for d in signs.values() for v in d.values())

# --- Process Promotion ---
promo_raw = data['Last 10 days - Promotion']['data']['data']
promos = {}
for row in promo_raw:
    date = row[0]
    promos[date] = [float(row[1]), float(row[2]), float(row[3])]

import math

# --- Process CM Business Performance ---
cm_raw = data['CM - Business Performance']['data']['data']
cm_dates = set()
cm_rows = []
for row in cm_raw:
    cm_dates.add(row[0])
for row in cm_raw:
    def safe_float(v):
        try:
            f = float(v)
            return f if not math.isnan(f) else 0.0
        except:
            return 0.0
    cm_rows.append({
        'date': row[0],
        'region': row[1],
        'city': row[2] if row[2] != 'NULL' else 'Overall',
        'orders': int(row[3]) if row[3] else 0,
        'aov': safe_float(row[4]),
        'gmv': safe_float(row[5]),
        'store_avg': safe_float(row[6]),
    })

gmv_total = sum(r['gmv'] for r in cm_rows)
avg_aov = sum(r['aov'] * r['orders'] for r in cm_rows) / sum(r['orders'] for r in cm_rows) if cm_rows else 0

# --- Process User Experience ---
ux = {}
if 'Last 10 days - User Experience' in data:
    ux_raw = data['Last 10 days - User Experience']['data']['data']
    for row in ux_raw:
        date = row[0]
        ux[date] = [float(row[1]), float(row[2]), float(row[3])]

ux_dates = sorted(ux.keys(), reverse=True)

cm_latest_date = parse_date(max(cm_dates)) if cm_dates else 'N/A'

# --- Build HTML ---
html = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SP Metropolitan Region · Business Platform</title>
<style>
:root {
  --bg:#1a1a2e;
  --card:#16213e;
  --text:#e2e8f0;
  --muted:#94a3b8;
  --green:#22c55e;
  --yellow:#eab308;
  --red:#ef4444;
  --blue:#3b82f6;
  --cyan:#06b6d4;
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
  color: var(--text);
}
.header .subtitle {
  color: var(--muted);
  font-size: 0.85rem;
}
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
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
  font-size: 1.8rem;
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
  color: var(--text);
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
.date-col { color: var(--muted); font-size: 0.75rem; white-space: nowrap; }
.num-col { text-align: right; font-variant-numeric: tabular-nums; }
.total-row { font-weight: 700; background: rgba(59,130,246,0.08); }
.total-row td { border-top: 2px solid var(--border); }
.pill {
  display: inline-block;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 0.7rem;
  font-weight: 500;
  border: 1px solid;
}
.footer {
  text-align: center;
  color: var(--muted);
  font-size: 0.7rem;
  margin-top: 16px;
  padding-bottom: 20px;
}
@media (max-width: 600px) {
  body { padding: 10px; }
  .kpi-card .value { font-size: 1.4rem; }
  th, td { padding: 6px 8px; font-size: 0.75rem; }
}
</style>
</head>
<body>
<div class="header">
  <h1>SP Metropolitan Region · Business Platform</h1>
  <div class="subtitle">Data through ''' + latest_date + ''' (BRT)</div>
</div>

<div class="kpi-grid">
  <div class="kpi-card">
    <div class="label">Total Orders (10 Days)</div>
    <div class="value" style="color:var(--green)">''' + fmt_num(order_total) + '''</div>
    <div class="delta">Sum across all tiers</div>
  </div>
  <div class="kpi-card">
    <div class="label">Total GMV (10 Days)</div>
    <div class="value" style="color:var(--cyan)">''' + fmt_gmv(gmv_total) + '''</div>
    <div class="delta">CM Business Performance</div>
  </div>
  <div class="kpi-card">
    <div class="label">Avg AOV (Weighted)</div>
    <div class="value" style="color:var(--yellow)">''' + fmt_gmv(avg_aov) + '''</div>
    <div class="delta">Across all regions</div>
  </div>
  <div class="kpi-card">
    <div class="label">Total New Signs (10 Days)</div>
    <div class="value" style="color:var(--blue)">''' + fmt_num(sign_total) + '''</div>
    <div class="delta">Sum across all tiers</div>
  </div>
</div>
'''

# --- Order Performance Section ---
html += '''<div class="section">
  <h2>Last 10 Days — Order Performance</h2>
  <div class="table-wrap">
    <table>
      <tr><th>Date</th><th>Priority</th><th class="num-col">Orders</th></tr>
'''
for date in order_dates:
    d = orders[date]
    total = 0
    date_str = parse_date(date)
    for prio in ['Top-Tier', 'Mid-Tier', 'Must-have']:
        val = d.get(prio, 0)
        total += val
        color = priority_color(prio)
        html += f'      <tr><td class="date-col">{date_str}</td><td><span class="pill" style="color:{color};border-color:{color}">{prio}</span></td><td class="num-col">{fmt_num(val)}</td></tr>\n'
    html += f'      <tr class="total-row"><td class="date-col">{date_str}</td><td>Total</td><td class="num-col">{fmt_num(total)}</td></tr>\n'
html += '''    </table>
  </div>
</div>
'''

# --- New Signs Section ---
html += '''<div class="section">
  <h2>Last 10 Days — New Signs</h2>
  <div class="table-wrap">
    <table>
      <tr><th>Date</th><th>Priority</th><th class="num-col">New Signs</th></tr>
'''
for date in sorted(signs.keys(), reverse=True):
    d = signs[date]
    total = 0
    date_str = parse_date(date)
    for prio in ['Top-Tier', 'Mid-Tier', 'Must-have']:
        val = d.get(prio, 0)
        total += val
        color = priority_color(prio)
        html += f'      <tr><td class="date-col">{date_str}</td><td><span class="pill" style="color:{color};border-color:{color}">{prio}</span></td><td class="num-col">{fmt_num(val)}</td></tr>\n'
    html += f'      <tr class="total-row"><td class="date-col">{date_str}</td><td>Total</td><td class="num-col">{fmt_num(total)}</td></tr>\n'
html += '''    </table>
  </div>
</div>
'''

# --- CM Business Performance Section ---
html += '''<div class="section">
  <h2>CM Business Performance (''' + cm_latest_date + ''')</h2>
  <div class="table-wrap">
    <table>
      <tr><th>Region</th><th>City</th><th class="num-col">Orders</th><th class="num-col">AOV</th><th class="num-col">GMV</th><th class="num-col">Store Avg Orders</th></tr>
'''
for r in cm_rows:
    html += f'      <tr><td>{r["region"]}</td><td>{r["city"]}</td><td class="num-col">{fmt_num(r["orders"])}</td><td class="num-col">{fmt_gmv(r["aov"])}</td><td class="num-col">{fmt_gmv(r["gmv"])}</td><td class="num-col">{fmt_num(r["store_avg"])}</td></tr>\n'
html += '''    </table>
  </div>
</div>
'''

# --- Promotion Coverage Section ---
html += '''<div class="section">
  <h2>Last 10 Days — Promotion Coverage</h2>
  <div class="table-wrap">
    <table>
      <tr><th>Date</th><th class="num-col">Deep Discount</th><th class="num-col">Full Discount</th><th class="num-col">Delivery Discount</th></tr>
'''
for date in sorted(promos.keys(), reverse=True):
    p = promos[date]
    date_str = parse_date(date)
    html += f'      <tr><td class="date-col">{date_str}</td><td class="num-col">{fmt_pct(p[0])}</td><td class="num-col">{fmt_pct(p[1])}</td><td class="num-col">{fmt_pct(p[2])}</td></tr>\n'
html += '''    </table>
  </div>
</div>
'''

# --- User Experience Section ---
html += '''<div class="section">
  <h2>Last 10 Days — User Experience</h2>
  <div class="table-wrap">
    <table>
      <tr><th>Date</th><th class="num-col">Cancel Rate</th><th class="num-col">Spill/Damage</th><th class="num-col">Missing/Wrong</th></tr>
'''
for date in ux_dates:
    u = ux[date]
    date_str = parse_date(date)
    cancel = u[0]
    # Color coding for cancel rate
    if cancel > 0.08:
        cancel_style = 'color:var(--red);font-weight:700'
    elif cancel > 0.05:
        cancel_style = 'color:var(--yellow);font-weight:600'
    else:
        cancel_style = 'color:var(--green)'
    html += f'      <tr><td class="date-col">{date_str}</td><td class="num-col" style="{cancel_style}">{fmt_pct(cancel)}</td><td class="num-col">{fmt_pct(u[1])}</td><td class="num-col">{fmt_pct(u[2])}</td></tr>\n'
html += '''    </table>
  </div>
</div>
'''

html += '''<div class="footer">
  Business Platform Dashboard | Data Source: BI | Generated: ''' + datetime.now().strftime('%Y-%m-%d %H:%M') + ''' CST
</div>
</body>
</html>
'''

with open('/mnt/openclaw/.openclaw/workspace/bp_dashboard.html', 'w') as f:
    f.write(html)

print("HTML generated successfully")
print(f"Total Orders: {fmt_num(order_total)}")
print(f"Total GMV: {fmt_gmv(gmv_total)}")
print(f"Avg AOV: {fmt_gmv(avg_aov)}")
print(f"Total New Signs: {fmt_num(sign_total)}")
