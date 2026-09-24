import json

# Read data
with open('/mnt/openclaw/.openclaw/workspace/bi_raw_data.json', 'r') as f:
    raw = json.load(f)

# Parse order performance
order_data = {}
for row in raw["Last 10 Days - Order Performance"]["data"]["data"]:
    dt, priority, val = row[0], row[1], int(row[2])
    if dt not in order_data:
        order_data[dt] = {}
    order_data[dt][priority] = val

dates = sorted(order_data.keys())

# Parse operation performance
op_data = {}
for row in raw["Last 10 days - Operation Performance"]["data"]["data"]:
    dt, priority, val = row[0], row[1], float(row[2])
    if dt not in op_data:
        op_data[dt] = {}
    op_data[dt][priority] = val

# CM data
cm_rows = []
for row in raw["CM - Business Performance"]["data"]["data"]:
    region = row[1]
    city = row[2]
    orders = int(row[3]) if row[3] not in ('NaN', '') else 0
    avg_price = float(row[4]) if row[4] not in ('NaN', '') else 0.0
    gmv = float(row[5]) if row[5] not in ('NaN', '') else 0.0
    cm_rows.append((region, city, orders, gmv, avg_price))

# Sort CM by region then city
cm_rows.sort(key=lambda x: (x[0], x[1]))

# KPIs (latest date from data = 20260718, representing 2026-07-18 per task)
latest_dt = max(dates)
total_orders = sum(order_data[latest_dt].values())
top_tier_orders = order_data[latest_dt].get('Top-Tier', 0)
must_have_rate = op_data[latest_dt].get('Must-have', 0) * 100
mid_tier_rate = op_data[latest_dt].get('Mid-Tier', 0) * 100

def fmt_date(dt):
    y, m, d = dt[:4], dt[4:6], dt[6:]
    weekdays = ['周一','周二','周三','周四','周五','周六','周日']
    from datetime import datetime
    wd = datetime(int(y), int(m), int(d)).weekday()
    return f"{y}年{m}月{d}日（{weekdays[wd]}）"

def fmt_num(n):
    return f"{n:,}"

def fmt_pct(n):
    return f"{n:.1f}%"

def fmt_money(n):
    return f"{n:,.2f}"

html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Business Platform Dashboard</title>
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
}}
.header {{
  text-align: center;
  margin-bottom: 24px;
}}
.header h1 {{
  font-size: 1.5rem;
  font-weight: 700;
  margin-bottom: 4px;
}}
.header .subtitle {{
  color: var(--muted);
  font-size: 0.875rem;
}}
.kpi-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
  margin-bottom: 28px;
}}
.kpi-card {{
  background: var(--card);
  border-radius: 12px;
  padding: 20px;
  text-align: center;
  box-shadow: 0 4px 6px rgba(0,0,0,0.3);
}}
.kpi-card .label {{
  color: var(--muted);
  font-size: 0.875rem;
  margin-bottom: 8px;
}}
.kpi-card .value {{
  font-size: 1.75rem;
  font-weight: 700;
}}
.kpi-card .value.total {{ color: var(--text); }}
.kpi-card .value.toptier {{ color: var(--green); }}
.kpi-card .value.musthave {{ color: var(--cyan); }}
.kpi-card .value.midtier {{ color: var(--yellow); }}

.section {{
  margin-bottom: 28px;
}}
.section-title {{
  font-size: 1.1rem;
  font-weight: 600;
  margin-bottom: 12px;
  padding-left: 8px;
  border-left: 4px solid var(--green);
}}
.table-wrap {{
  overflow-x: auto;
  background: var(--card);
  border-radius: 12px;
  padding: 0;
  box-shadow: 0 4px 6px rgba(0,0,0,0.3);
}}
table {{
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}}
th, td {{
  padding: 10px 14px;
  text-align: right;
  border-bottom: 1px solid #334155;
}}
th {{
  background: #0f172a;
  color: var(--muted);
  font-weight: 600;
  text-align: right;
  position: sticky;
  top: 0;
}}
tr:last-child td {{ border-bottom: none; }}
td:first-child, th:first-child {{
  text-align: left;
  font-weight: 500;
}}
.toptier-val {{ color: var(--text); }}
.musthave-val {{ color: var(--cyan); }}
.midtier-val {{ color: var(--yellow); }}
.total-val {{ color: var(--green); font-weight: 600; }}
.rate-green {{ color: var(--green); }}
.rate-yellow {{ color: var(--yellow); }}
.rate-red {{ color: var(--red); }}
.region-cell {{ text-align: left !important; font-weight: 500; }}
.city-cell {{ text-align: left !important; }}
</style>
</head>
<body>
<div class="header">
  <h1>Business Platform Dashboard</h1>
  <div class="subtitle">数据日期：{fmt_date(latest_dt)} | 更新时间：2026-07-19 07:30 BRT</div>
</div>

<div class="kpi-grid">
  <div class="kpi-card">
    <div class="label">Total Orders</div>
    <div class="value total">{fmt_num(total_orders)}</div>
  </div>
  <div class="kpi-card">
    <div class="label">Top-Tier Orders</div>
    <div class="value toptier">{fmt_num(top_tier_orders)}</div>
  </div>
  <div class="kpi-card">
    <div class="label">Must-have Valid Rate</div>
    <div class="value musthave">{fmt_pct(must_have_rate)}</div>
  </div>
  <div class="kpi-card">
    <div class="label">Mid-Tier Valid Rate</div>
    <div class="value midtier">{fmt_pct(mid_tier_rate)}</div>
  </div>
</div>

<div class="section">
  <div class="section-title">订单表现（Last 10 Days）</div>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>Date</th>
          <th>Top-Tier</th>
          <th>Must-have</th>
          <th>Mid-Tier</th>
          <th>Total</th>
        </tr>
      </thead>
      <tbody>
'''

for dt in dates:
    tt = order_data[dt].get('Top-Tier', 0)
    mh = order_data[dt].get('Must-have', 0)
    mt = order_data[dt].get('Mid-Tier', 0)
    total = tt + mh + mt
    html += f'''        <tr>
          <td>{fmt_date(dt)}</td>
          <td class="toptier-val">{fmt_num(tt)}</td>
          <td class="musthave-val">{fmt_num(mh)}</td>
          <td class="midtier-val">{fmt_num(mt)}</td>
          <td class="total-val">{fmt_num(total)}</td>
        </tr>\n'''

html += '''      </tbody>
    </table>
  </div>
</div>

<div class="section">
  <div class="section-title">经营率（Last 10 Days）</div>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>Date</th>
          <th>Top-Tier</th>
          <th>Must-have</th>
          <th>Mid-Tier</th>
        </tr>
      </thead>
      <tbody>
'''

for dt in dates:
    tt = op_data[dt].get('Top-Tier', 0) * 100
    mh = op_data[dt].get('Must-have', 0) * 100
    mt = op_data[dt].get('Mid-Tier', 0) * 100

    def rate_class(v):
        if v >= 70: return 'rate-green'
        if v >= 40: return 'rate-yellow'
        return 'rate-red'

    html += f'''        <tr>
          <td>{fmt_date(dt)}</td>
          <td class="toptier-val {rate_class(tt)}">{fmt_pct(tt)}</td>
          <td class="musthave-val {rate_class(mh)}">{fmt_pct(mh)}</td>
          <td class="midtier-val {rate_class(mt)}">{fmt_pct(mt)}</td>
        </tr>\n'''

html += '''      </tbody>
    </table>
  </div>
</div>

<div class="section">
  <div class="section-title">CM Business Performance（2026-07-18）</div>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>Region</th>
          <th>City</th>
          <th>Orders</th>
          <th>GMV</th>
          <th>Avg Price</th>
        </tr>
      </thead>
      <tbody>
'''

for region, city, orders, gmv, avg_price in cm_rows:
    html += f'''        <tr>
          <td class="region-cell">{region}</td>
          <td class="city-cell">{city}</td>
          <td>{fmt_num(orders)}</td>
          <td>{fmt_money(gmv)}</td>
          <td>{fmt_money(avg_price)}</td>
        </tr>\n'''

html += '''      </tbody>
    </table>
  </div>
</div>

</body>
</html>'''

with open('/mnt/openclaw/.openclaw/workspace/bp_dashboard.html', 'w') as f:
    f.write(html)

print("Done. Generated bp_dashboard.html")
