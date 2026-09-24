import json
from datetime import datetime, timedelta

with open('/mnt/openclaw/.openclaw/workspace/dbr_data_latest.json') as f:
    d = json.load(f)

def fmt_date(ds):
    dt = datetime.strptime(ds, '%Y%m%d')
    weekdays = ['一','二','三','四','五','六','日']
    return f"{dt.year}年{dt.month:02d}月{dt.day:02d}日（星期{weekdays[dt.weekday()]}）"

def today_str():
    dt = datetime.now()
    weekdays = ['一','二','三','四','五','六','日']
    return f"{dt.year}年{dt.month:02d}月{dt.day:02d}日（星期{weekdays[dt.weekday()]}）"

def fmt_num(n):
    try:
        return f"{int(n):,}"
    except:
        return str(n)

def fmt_pct(v):
    try:
        f = float(v)
        if f < 1:
            f = f * 100
        return f"{f:.1f}%"
    except:
        return str(v)

def fmt_money(v):
    try:
        return f"R$ {float(v):,.2f}"
    except:
        return str(v)

# === Extract data ===
bp = d['results']['Business Performance']['data']['data']
ns = d['results']['New Signs']['data']['data']
op = d['results']['Operation Performance']['data']['data']
ux = d['results']['User Experience']['data']['data']
promo = d['results']['Promotion']['data']['data']

# Metro Total
metro = None
for r in bp:
    if r[2] == 'NULL' and 'Metropolitan' in str(r[1]):
        metro = r
        break

# Regions
northeast = None
santos = None
for r in bp:
    if 'Northeast' in str(r[2]):
        northeast = r
    elif 'Santos' in str(r[2]):
        santos = r

# New signs
ns_total = sum(int(r[2]) for r in ns if len(r)>2)
ns_top = sum(int(r[2]) for r in ns if len(r)>2 and r[1]=='Top-Tier')
ns_mid = sum(int(r[2]) for r in ns if len(r)>2 and r[1]=='Mid-Tier')
ns_must = sum(int(r[2]) for r in ns if len(r)>2 and r[1]=='Must-have')

# Operation
op_total = None
for r in op:
    if r[2] == 'NULL':
        op_total = r
        break

# UX
ux_total = None
for r in ux:
    if r[2] == 'NULL':
        ux_total = r
        break

# Promo
promo_total = promo[0] if promo else None

# === Generate HTML ===
html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DBR Daily Report</title>
<style>
:root {{
  --bg:#0f172a;
  --card:#1e293b;
  --text:#e2e8f0;
  --muted:#94a3b8;
  --green:#22c55e;
  --yellow:#eab308;
  --red:#ef4444;
  --blue:#3b82f6;
  --cyan:#06b6d4;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  background: var(--bg);
  color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  padding: 24px;
  line-height: 1.5;
  max-width: 780px;
  margin: 0 auto;
}}
.header {{
  text-align: center;
  margin-bottom: 24px;
}}
.header h1 {{
  font-size: 1.6rem;
  font-weight: 700;
  margin-bottom: 4px;
  color: var(--text);
}}
.header .subtitle {{
  color: var(--muted);
  font-size: 0.875rem;
}}
.kpi-grid {{
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  margin-bottom: 20px;
}}
.kpi-card {{
  background: var(--card);
  border-radius: 12px;
  padding: 16px;
  text-align: center;
}}
.kpi-card .label {{
  color: var(--muted);
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 6px;
}}
.kpi-card .value {{
  font-size: 1.6rem;
  font-weight: 700;
  margin-bottom: 2px;
}}
.kpi-card .sub {{
  font-size: 0.75rem;
  color: var(--muted);
}}
.section {{
  background: var(--card);
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 16px;
}}
.section h2 {{
  font-size: 1rem;
  font-weight: 600;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}}
.section h2::before {{
  content: '';
  display: inline-block;
  width: 4px;
  height: 16px;
  background: var(--blue);
  border-radius: 2px;
}}
.metric-row {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid #334155;
}}
.metric-row:last-child {{ border-bottom: none; }}
.metric-label {{ color: var(--muted); font-size: 0.85rem; }}
.metric-value {{ font-weight: 600; font-size: 0.95rem; }}
.region-grid {{
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}}
.region-card {{
  background: rgba(255,255,255,0.03);
  border-radius: 8px;
  padding: 12px;
  text-align: center;
}}
.region-card .name {{ font-size: 0.75rem; color: var(--muted); margin-bottom: 4px; }}
.region-card .orders {{ font-size: 1.2rem; font-weight: 700; color: var(--green); }}
.region-card .gmv {{ font-size: 0.75rem; color: var(--muted); }}
.footer {{
  text-align: center;
  color: var(--muted);
  font-size: 0.7rem;
  margin-top: 16px;
}}
</style>
</head>
<body>
<div class="header">
  <h1>📊 DBR Daily Report</h1>
  <div class="subtitle">Data Date: {fmt_date(d['date'])} BRT | Generated: {today_str()} 北京时间</div>
</div>

<div class="kpi-grid">
  <div class="kpi-card">
    <div class="label">Metro Total Orders</div>
    <div class="value" style="color:var(--green)">{fmt_num(metro[3]) if metro else '-'}</div>
    <div class="sub">AOV {fmt_money(metro[4]) if metro else '-'}</div>
  </div>
  <div class="kpi-card">
    <div class="label">Metro Total GMV</div>
    <div class="value" style="color:var(--blue)">{fmt_money(metro[5]) if metro else '-'}</div>
    <div class="sub">GTV {fmt_money(metro[7]) if metro and len(metro)>7 else '-'}</div>
  </div>
  <div class="kpi-card">
    <div class="label">New Signs (昨日)</div>
    <div class="value" style="color:var(--cyan)">{ns_total}</div>
    <div class="sub">Top {ns_top} | Mid {ns_mid} | Must {ns_must}</div>
  </div>
  <div class="kpi-card">
    <div class="label">Operation Rate</div>
    <div class="value" style="color:var(--yellow)">{fmt_pct(op_total[5]) if op_total else '-'}</div>
    <div class="sub">Online {fmt_num(op_total[3]) if op_total else '-'} / Active {fmt_num(op_total[4]) if op_total else '-'}</div>
  </div>
</div>

<div class="section">
  <h2>Regional Breakdown</h2>
  <div class="region-grid">
    <div class="region-card">
      <div class="name">Metro Total</div>
      <div class="orders">{fmt_num(metro[3]) if metro else '-'}</div>
      <div class="gmv">{fmt_money(metro[5]) if metro else '-'}</div>
    </div>
    <div class="region-card">
      <div class="name">Northeast SP</div>
      <div class="orders">{fmt_num(northeast[3]) if northeast else '-'}</div>
      <div class="gmv">{fmt_money(northeast[5]) if northeast else '-'}</div>
    </div>
    <div class="region-card">
      <div class="name">Santos City</div>
      <div class="orders">{fmt_num(santos[3]) if santos else '-'}</div>
      <div class="gmv">{fmt_money(santos[5]) if santos else '-'}</div>
    </div>
  </div>
</div>

<div class="section">
  <h2>User Experience</h2>
  <div class="metric-row">
    <span class="metric-label">Cancel Rate (昨日)</span>
    <span class="metric-value" style="color:{'var(--red)' if ux_total and float(ux_total[3]) > 0.1 else 'var(--green)'}">{fmt_pct(ux_total[3]) if ux_total else '-'}</span>
  </div>
  <div class="metric-row">
    <span class="metric-label">Cancel Rate (WoW)</span>
    <span class="metric-value" style="color:{'var(--red)' if ux_total and float(ux_total[4]) > 0 else 'var(--green)'}">{'+' if ux_total and float(ux_total[4]) > 0 else ''}{fmt_pct(ux_total[4]) if ux_total else '-'}</span>
  </div>
</div>

<div class="section">
  <h2>Promotion</h2>
  <div class="metric-row">
    <span class="metric-label">Deep Discount Rate</span>
    <span class="metric-value">{fmt_pct(promo_total[1]) if promo_total else '-'}</span>
  </div>
  <div class="metric-row">
    <span class="metric-label">Promo Rate</span>
    <span class="metric-value">{fmt_pct(promo_total[2]) if promo_total else '-'}</span>
  </div>
  <div class="metric-row">
    <span class="metric-label">Coverage</span>
    <span class="metric-value" style="color:var(--green)">{fmt_pct(promo_total[3]) if promo_total else '-'}</span>
  </div>
</div>

<div class="section">
  <h2>Key Insights</h2>
  <div style="color:var(--muted);font-size:0.85rem;line-height:1.6;">
    <p>• Metro Total orders: <strong style="color:var(--text)">{fmt_num(metro[3]) if metro else '?'}</strong> with GMV <strong style="color:var(--text)">{fmt_money(metro[5]) if metro else '?'}</strong></p>
    <p>• New signs yesterday: <strong style="color:var(--text)">{ns_total}</strong> (Top {ns_top}, Mid {ns_mid}, Must {ns_must})</p>
    <p>• Operation rate: <strong style="color:var(--text)">{fmt_pct(op_total[5]) if op_total else '?'}</strong> ({fmt_num(op_total[3]) if op_total else '?'} online / {fmt_num(op_total[4]) if op_total else '?'} active)</p>
    <p>• Cancel rate: <strong style="color:var(--text)">{fmt_pct(ux_total[3]) if ux_total else '?'}</strong> (WoW {'+' if ux_total and float(ux_total[4]) > 0 else ''}{fmt_pct(ux_total[4]) if ux_total else '?'})</p>
    <p>• Promotion coverage: <strong style="color:var(--text)">{fmt_pct(promo_total[3]) if promo_total else '?'}</strong> with deep discount at <strong style="color:var(--text)">{fmt_pct(promo_total[1]) if promo_total else '?'}</strong></p>
  </div>
</div>

<div class="footer">
  SP Metropolitan Region DBR | Data Source: BI 300001446 | Generated: {today_str()} 北京时间
</div>

</body>
</html>
'''

with open('/mnt/openclaw/.openclaw/workspace/dbr_card.html', 'w') as f:
    f.write(html)

print("DBR card generated!")
print(f"Date: {fmt_date(d['date'])}")
print(f"Orders: {fmt_num(metro[3]) if metro else '?'}")
print(f"GMV: {fmt_money(metro[5]) if metro else '?'}")
