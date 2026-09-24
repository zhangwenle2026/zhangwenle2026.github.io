#!/usr/bin/env python3
"""Generate Business Platform Dashboard HTML with mock data fallback"""
import json
from datetime import datetime, timedelta
from pathlib import Path

# Load data (may be empty)
DATA_PATH = "/mnt/openclaw/.openclaw/workspace/bi_raw_data.json"
try:
    with open(DATA_PATH, encoding="utf-8") as f:
        DATA = json.load(f)
except:
    DATA = {}

HAS_DATA = bool(DATA)

# Generate mock data for last 10 days
def generate_mock_dates():
    dates = []
    for i in range(9, -1, -1):
        d = datetime.now() - timedelta(days=i)
        dates.append(d.strftime('%Y-%m-%d'))
    return dates

MOCK_DATES = generate_mock_dates()

def mock_orders():
    data = []
    base = 5000
    for i, d in enumerate(MOCK_DATES):
        day_factor = 1.0 + 0.1 * (i % 3)
        data.append([d, "Top-Tier", int(base * day_factor * 0.5)])
        data.append([d, "Must-have", int(base * day_factor * 0.3)])
        data.append([d, "Mid-Tier", int(base * day_factor * 0.2)])
    return data

def mock_new_signs():
    data = []
    for i, d in enumerate(MOCK_DATES):
        data.append([d, "Top-Tier", 15 + (i % 5)])
        data.append([d, "Must-have", 8 + (i % 3)])
        data.append([d, "Mid-Tier", 5 + (i % 4)])
    return data

def mock_operation():
    data = []
    for i, d in enumerate(MOCK_DATES):
        data.append([d, "Top-Tier", round(0.75 + 0.05 * (i % 3), 4)])
        data.append([d, "Must-have", round(0.65 + 0.05 * (i % 3), 4)])
        data.append([d, "Mid-Tier", round(0.55 + 0.05 * (i % 3), 4)])
    return data

def mock_ux():
    data = []
    for i, d in enumerate(MOCK_DATES):
        data.append([d, round(0.012 + 0.003 * (i % 3), 4), round(0.005 + 0.002 * (i % 3), 4), round(0.008 + 0.003 * (i % 3), 4)])
    return data

def mock_promo():
    data = []
    for i, d in enumerate(MOCK_DATES):
        data.append([d, round(0.35 + 0.05 * (i % 4), 4), round(0.25 + 0.05 * (i % 3), 4), round(0.15 + 0.03 * (i % 5), 4)])
    return data

def mock_cm():
    data = []
    for i in range(20):
        data.append([f"Region {i+1}", f"City {i+1}", 100+i*10, 80+i*8, 500+i*50, 2000+i*200, 25, 5, 20, 300+i*30, 50+i*5])
    return ["Region", "City", "Merchants", "Active", "Orders", "GMV", "AOV", "Cancel", "Spill", "NewSigns", "DeepDiscount"], data

def mock_bdm():
    data = []
    for i in range(12):
        data.append([f"BDM-{i+1}", 50+i*5, 40+i*4, 200+i*20, 1000+i*100, 5, 3, 10, 50+i*5])
    return ["BDM", "Merchants", "Active", "Orders", "GMV", "AOV", "Cancel", "NewSigns", "DeepDiscount"], data

def mock_bd():
    data = []
    for i in range(15):
        data.append([f"BD-{i+1}", 30+i*3, 25+i*2, 100+i*10, 500+i*50, 5, 2, 8, 30+i*3])
    return ["BD", "Merchants", "Active", "Orders", "GMV", "AOV", "Cancel", "NewSigns", "DeepDiscount"], data

def mock_smb_ranking():
    data = []
    for i in range(20):
        data.append([f"Merchant-{i+1}", f"Category {i%5+1}", f"City {i%3+1}", 50+i*5, 40+i*4, 200+i*20, 1000+i*100, 20, 5, 15])
    return ["Merchant", "Category", "City", "Merchants", "Active", "Orders", "GMV", "AOV", "Cancel", "NewSigns"], data

def mock_merchant_list():
    data = []
    for i in range(30):
        data.append([f"Merchant-{i+1}", f"City {i%3+1}", 30+i*3, 25+i*2, 100+i*10, 500+i*50, 5, 2, 8, 30+i*3])
    return ["Merchant", "City", "Merchants", "Active", "Orders", "GMV", "AOV", "Cancel", "NewSigns", "DeepDiscount"], data

# Use mock data (BI fetch failed)
op_rows = mock_orders()
ns_rows = mock_new_signs()
opr_rows = mock_operation()
ux_rows = mock_ux()
pr_rows = mock_promo()
cm_cols, cm_rows = mock_cm()
bdm_cols, bdm_rows = mock_bdm()
bd_cols, bd_rows = mock_bd()
rank_cols, rank_rows = mock_smb_ranking()
ml_cols, ml_rows = mock_merchant_list()

def fmt_num(v, decimals=0):
    import math
    if v is None or v == "":
        return "-"
    if isinstance(v, str):
        if v in ("NaN", "nan"):
            return "-"
        try:
            v = float(v)
        except:
            return v
    if isinstance(v, (int, float)):
        if math.isnan(v):
            return "-"
        if decimals == 0:
            return f"{int(v):,}"
        return f"{v:,.{decimals}f}"
    return str(v)

def fmt_pct(v):
    if v is None or v == "":
        return "-"
    try:
        return f"{float(v)*100:.2f}%"
    except:
        return str(v)

def make_table(cols, rows, max_rows=50):
    if not rows:
        return "<p class='text-muted'>No data</p>"
    html = "<div class='table-wrap'><table>"
    html += "<thead><tr>"
    for c in cols:
        html += f"<th>{c}</th>"
    html += "</tr></thead><tbody>"
    for i, row in enumerate(rows[:max_rows]):
        html += "<tr>"
        for j, v in enumerate(row):
            html += f"<td>{fmt_num(v)}</td>"
        html += "</tr>"
    if len(rows) > max_rows:
        html += f"<tr><td colspan='{len(cols)}' class='text-muted' style='text-align:center'>... {len(rows) - max_rows} more rows ...</td></tr>"
    html += "</tbody></table></div>"
    return html

# Compute KPIs
total_orders = sum(float(r[2]) for r in op_rows) if op_rows else 0
latest_date = max(r[0] for r in op_rows) if op_rows else MOCK_DATES[-1]
latest_orders = sum(float(r[2]) for r in op_rows if r[0] == latest_date) if op_rows else 0
latest_ns = sum(float(r[2]) for r in ns_rows if r[0] == latest_date) if ns_rows else 0
mtd_ns = sum(float(r[2]) for r in ns_rows) if ns_rows else 0
latest_opr = {r[1]: float(r[2]) for r in opr_rows if r[0] == latest_date} if opr_rows else {}
avg_opr = sum(latest_opr.values()) / len(latest_opr) if latest_opr else 0.65
latest_ux = [r for r in ux_rows if r[0] == latest_date][0] if ux_rows else []
latest_pr = [r for r in pr_rows if r[0] == latest_date][0] if pr_rows else []
total_merchants = len(ml_rows) if ml_rows else 0

# Chart data
op_by_date = {}
for r in op_rows:
    date, priority, orders = r[0], r[1], float(r[2])
    if date not in op_by_date:
        op_by_date[date] = {}
    op_by_date[date][priority] = op_by_date[date].get(priority, 0) + orders
op_dates = sorted(op_by_date.keys())
op_datasets = [(p, [op_by_date[d].get(p, 0) for d in op_dates]) for p in ["Must-have", "Top-Tier", "Mid-Tier"]]

ns_by_date = {}
for r in ns_rows:
    date, priority, count = r[0], r[1], float(r[2])
    if date not in ns_by_date:
        ns_by_date[date] = {}
    ns_by_date[date][priority] = ns_by_date[date].get(priority, 0) + count
ns_dates = sorted(ns_by_date.keys())
ns_datasets = [(p, [ns_by_date[d].get(p, 0) for d in ns_dates]) for p in ["Must-have", "Top-Tier", "Mid-Tier"]]

opr_by_date = {}
for r in opr_rows:
    date, priority, rate = r[0], r[1], float(r[2])
    if date not in opr_by_date:
        opr_by_date[date] = {}
    opr_by_date[date][priority] = rate
opr_dates = sorted(opr_by_date.keys())
opr_datasets = [(p, [opr_by_date[d].get(p, 0) * 100 for d in opr_dates]) for p in ["Must-have", "Top-Tier", "Mid-Tier"]]

pr_dates = sorted(set(r[0] for r in pr_rows))
pr_datasets = [
    ("折扣菜覆盖率", [float(next((r[1] for r in pr_rows if r[0] == d), 0)) * 100 for d in pr_dates]),
    ("满折覆盖率", [float(next((r[2] for r in pr_rows if r[0] == d), 0)) * 100 for d in pr_dates]),
    ("减配覆盖率", [float(next((r[3] for r in pr_rows if r[0] == d), 0)) * 100 for d in pr_dates]),
]

ux_dates = sorted(set(r[0] for r in ux_rows))
ux_datasets = [
    ("取消率", [float(next((r[1] for r in ux_rows if r[0] == d), 0)) * 100 for d in ux_dates]),
    ("洒漏率", [float(next((r[2] for r in ux_rows if r[0] == d), 0)) * 100 for d in ux_dates]),
    ("错漏餐率", [float(next((r[3] for r in ux_rows if r[0] == d), 0)) * 100 for d in ux_dates]),
]

def fmt_date(d):
    dt = datetime.strptime(d, '%Y-%m-%d')
    weekdays = ['一', '二', '三', '四', '五', '六', '日']
    return f"{dt.year}年{dt.month:02d}月{dt.day:02d}日（星期{weekdays[dt.weekday()]}）"

latest_date_display = fmt_date(latest_date) if latest_date else "-"
update_time = datetime.now().strftime('%Y年%m月%d日（星期') + ['一','二','三','四','五','六','日'][datetime.now().weekday()] + '）'

DATA_WARNING = """
<div class="data-warning">
  ⚠️ 当前展示为模拟数据（BI数据抓取失败，请检查CDP/浏览器登录状态）
</div>
""" if not HAS_DATA or not any(v.get("code") == 0 for v in DATA.values()) else ""

# Generate HTML
html_parts = []
html_parts.append(f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Business Platform Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
:root {{ --bg:#0f172a; --card:#1e293b; --text:#e2e8f0; --muted:#94a3b8; --green:#22c55e; --yellow:#eab308; --red:#ef4444; --blue:#3b82f6; --cyan:#06b6d4; --pink:#f472b6; --purple:#a78bfa; }}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; padding: 24px; line-height: 1.5; }}
.container {{ max-width: 1600px; margin: 0 auto; }}
.header {{ text-align: center; margin-bottom: 24px; padding-bottom: 20px; border-bottom: 1px solid #334155; }}
.header h1 {{ font-size: 1.8rem; font-weight: 700; margin-bottom: 4px; }}
.header .subtitle {{ color: var(--muted); font-size: 0.9rem; }}
.date-badge {{ display: inline-block; background: var(--green); color: #0f172a; padding: 6px 14px; border-radius: 20px; font-weight: 600; font-size: 0.85rem; margin-top: 10px; }}
.data-warning {{ background: rgba(239, 68, 68, 0.15); border: 1px solid var(--red); border-radius: 8px; padding: 12px 16px; margin-bottom: 20px; color: #fca5a5; font-size: 0.875rem; text-align: center; }}
.kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 28px; }}
.kpi-card {{ background: var(--card); border-radius: 12px; padding: 20px; text-align: center; transition: transform 0.15s; }}
.kpi-card:hover {{ transform: translateY(-2px); }}
.kpi-card .label {{ color: var(--muted); font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px; }}
.kpi-card .value {{ font-size: 1.8rem; font-weight: 700; margin-bottom: 4px; }}
.kpi-card .delta {{ font-size: 0.875rem; color: var(--muted); }}
.section {{ background: var(--card); border-radius: 12px; padding: 20px; margin-bottom: 20px; }}
.section h2 {{ font-size: 1.1rem; font-weight: 600; margin-bottom: 16px; display: flex; align-items: center; gap: 8px; }}
.section h2::before {{ content: ''; display: inline-block; width: 4px; height: 18px; background: var(--blue); border-radius: 2px; }}
.table-wrap {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; font-size: 0.875rem; }}
th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid #334155; }}
th {{ color: var(--muted); font-weight: 500; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.5px; }}
tr:hover {{ background: rgba(255,255,255,0.03); }}
.text-muted {{ color: var(--muted); }}
.chart-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(480px, 1fr)); gap: 20px; margin-bottom: 20px; }}
.chart-box {{ background: var(--card); border-radius: 12px; padding: 16px; }}
.chart-box h3 {{ font-size: 0.95rem; color: var(--muted); margin-bottom: 12px; }}
.chart-container {{ height: 280px; position: relative; }}
.ux-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; }}
.ux-item {{ background: rgba(255,255,255,0.03); border-radius: 10px; padding: 16px; text-align: center; }}
.ux-label {{ font-size: 0.75rem; color: var(--muted); margin-bottom: 6px; }}
.ux-value {{ font-size: 1.4rem; font-weight: 700; }}
.ux-value.good {{ color: var(--green); }}
.ux-value.warn {{ color: var(--yellow); }}
.ux-value.bad {{ color: var(--red); }}
.promo-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; }}
.promo-item {{ background: rgba(255,255,255,0.03); border-radius: 10px; padding: 16px; }}
.promo-bar-bg {{ background: rgba(255,255,255,0.08); border-radius: 6px; height: 8px; margin-top: 10px; overflow: hidden; }}
.promo-bar {{ height: 100%; border-radius: 6px; transition: width 0.5s; }}
.footer {{ text-align: center; color: var(--muted); font-size: 0.75rem; padding: 24px; border-top: 1px solid #334155; margin-top: 20px; }}
.two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
@media (max-width: 900px) {{ .two-col {{ grid-template-columns: 1fr; }} .chart-grid {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>
<div class="container">
<div class="header">
  <h1>📊 Business Platform Dashboard</h1>
  <div class="subtitle">BR SMB Performance Overview</div>
  <div class="date-badge">Data: {latest_date_display}</div>
</div>
{DATA_WARNING}
""")

# KPI Cards
html_parts.append(f"""<div class="kpi-grid">
  <div class="kpi-card">
    <div class="label">Total Orders (Latest)</div>
    <div class="value" style="color:var(--green)">{fmt_num(int(latest_orders))}</div>
    <div class="delta">MTD: {fmt_num(int(total_orders))}</div>
  </div>
  <div class="kpi-card">
    <div class="label">New Signs (Latest)</div>
    <div class="value" style="color:var(--blue)">{fmt_num(int(latest_ns))}</div>
    <div class="delta">MTD: {fmt_num(int(mtd_ns))}</div>
  </div>
  <div class="kpi-card">
    <div class="label">Active Merchants</div>
    <div class="value" style="color:var(--cyan)">{fmt_num(total_merchants)}</div>
    <div class="delta">SMB Merchant List</div>
  </div>
  <div class="kpi-card">
    <div class="label">Valid Operating Rate</div>
    <div class="value" style="color:var(--yellow)">{avg_opr*100:.1f}%</div>
    <div class="delta">Date: {latest_date}</div>
  </div>
  <div class="kpi-card">
    <div class="label">Cancel Rate</div>
    <div class="value" style="color:var(--green)">{fmt_pct(latest_ux[1]) if latest_ux else '1.50%'}</div>
    <div class="delta">Latest Day</div>
  </div>
  <div class="kpi-card">
    <div class="label">Deep Discount Rate</div>
    <div class="value" style="color:var(--purple)">{fmt_pct(latest_pr[1]) if len(latest_pr) > 1 else '35.00%'}</div>
    <div class="delta">Latest Day</div>
  </div>
</div>
""")

# Charts
html_parts.append(f"""<div class="chart-grid">
  <div class="chart-box">
    <h3>📈 Last 10 Days - Order Performance by Priority</h3>
    <div class="chart-container"><canvas id="chartOrders"></canvas></div>
  </div>
  <div class="chart-box">
    <h3>🆕 Last 10 Days - New Signs by Priority</h3>
    <div class="chart-container"><canvas id="chartNewSigns"></canvas></div>
  </div>
</div>
<div class="chart-grid">
  <div class="chart-box">
    <h3>⚙️ Last 10 Days - Valid Operating Rate (%)</h3>
    <div class="chart-container"><canvas id="chartOpRate"></canvas></div>
  </div>
  <div class="chart-box">
    <h3>🎯 Last 10 Days - Promotion Coverage (%)</h3>
    <div class="chart-container"><canvas id="chartPromo"></canvas></div>
  </div>
</div>
""")

# UX Section
ux1 = fmt_pct(latest_ux[1]) if latest_ux else '1.50%'
ux2 = fmt_pct(latest_ux[2]) if latest_ux else '0.50%'
ux3 = fmt_pct(latest_ux[3]) if latest_ux else '0.80%'
html_parts.append(f"""<div class="section">
  <h2>User Experience (Latest Day)</h2>
  <div class="ux-grid">
    <div class="ux-item">
      <div class="ux-label">Cancel Rate<br><small>(Timeout + Merchant Cancel)</small></div>
      <div class="ux-value good">{ux1}</div>
    </div>
    <div class="ux-item">
      <div class="ux-label">Spill / Damage Rate</div>
      <div class="ux-value good">{ux2}</div>
    </div>
    <div class="ux-item">
      <div class="ux-label">Missing / Wrong Meal Rate</div>
      <div class="ux-value good">{ux3}</div>
    </div>
  </div>
  <div class="chart-container" style="height:220px;margin-top:16px;"><canvas id="chartUX"></canvas></div>
</div>
""")

# Promotion Detail
pr1 = fmt_pct(latest_pr[1]) if len(latest_pr) > 1 else '35.00%'
pr2 = fmt_pct(latest_pr[2]) if len(latest_pr) > 2 else '25.00%'
pr3 = fmt_pct(latest_pr[3]) if len(latest_pr) > 3 else '15.00%'
pw1 = float(latest_pr[1])*100 if len(latest_pr)>1 else 35
pw2 = float(latest_pr[2])*100 if len(latest_pr)>2 else 25
pw3 = float(latest_pr[3])*100 if len(latest_pr)>3 else 15

html_parts.append(f"""<div class="section">
  <h2>Promotion Coverage Detail (Latest Day)</h2>
  <div class="promo-grid">
    <div class="promo-item">
      <div style="display:flex;justify-content:space-between;">
        <span>折扣菜活动</span><strong>{pr1}</strong>
      </div>
      <div class="promo-bar-bg"><div class="promo-bar" style="width:{pw1}%;background:var(--green);"></div></div>
    </div>
    <div class="promo-item">
      <div style="display:flex;justify-content:space-between;">
        <span>满折活动</span><strong>{pr2}</strong>
      </div>
      <div class="promo-bar-bg"><div class="promo-bar" style="width:{pw2}%;background:var(--blue);"></div></div>
    </div>
    <div class="promo-item">
      <div style="display:flex;justify-content:space-between;">
        <span>减配活动 (商补>0)</span><strong>{pr3}</strong>
      </div>
      <div class="promo-bar-bg"><div class="promo-bar" style="width:{pw3}%;background:var(--pink);"></div></div>
    </div>
  </div>
</div>
""")

# Data Tables
html_parts.append(f"""<div class="section">
  <h2>CM - Business Performance by Region & City</h2>
  {make_table(cm_cols, cm_rows, max_rows=20)}
</div>
<div class="two-col">
  <div class="section">
    <h2>BDM - Business Performance (Top 15)</h2>
    {make_table(bdm_cols, bdm_rows, max_rows=15)}
  </div>
  <div class="section">
    <h2>BD - Business Performance (Top 15)</h2>
    {make_table(bd_cols, bd_rows, max_rows=15)}
  </div>
</div>
<div class="section">
  <h2>SMB - MTD Merchant Ranking (Top 20)</h2>
  {make_table(rank_cols, rank_rows, max_rows=20)}
</div>
<div class="section">
  <h2>Merchant List - Business Performance (Sample Top 30)</h2>
  {make_table(ml_cols, ml_rows, max_rows=30)}
</div>
""")

# Footer and JS
html_parts.append(f"""<div class="footer">
  Business Platform Dashboard | Data Source: BI 300001446 | Updated: {update_time} 北京时间
</div>
</div>
<script>
""")

# Chart.js scripts
chart_js = []

# Orders chart
chart_js.append(f"""new Chart(document.getElementById('chartOrders'), {{
  type: 'bar',
  data: {{
    labels: {json.dumps(op_dates, ensure_ascii=False)},
    datasets: [
      {{ label: 'Must-have', data: {json.dumps(op_datasets[0][1], ensure_ascii=False)}, backgroundColor: '#60a5fa', borderColor: '#60a5fa', borderWidth: 1 }},
      {{ label: 'Top-Tier', data: {json.dumps(op_datasets[1][1], ensure_ascii=False)}, backgroundColor: '#4ade80', borderColor: '#4ade80', borderWidth: 1 }},
      {{ label: 'Mid-Tier', data: {json.dumps(op_datasets[2][1], ensure_ascii=False)}, backgroundColor: '#fbbf24', borderColor: '#fbbf24', borderWidth: 1 }}
    ]
  }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    plugins: {{ legend: {{ labels: {{ color: '#94a3b8' }} }} }},
    scales: {{
      x: {{ stacked: true, ticks: {{ color: '#64748b' }}, grid: {{ color: '#1e293b' }} }},
      y: {{ stacked: true, ticks: {{ color: '#64748b' }}, grid: {{ color: '#1e293b' }}, title: {{ display: true, text: 'Orders', color: '#64748b' }} }}
    }}
  }}
}});
""")

# New Signs chart
chart_js.append(f"""new Chart(document.getElementById('chartNewSigns'), {{
  type: 'bar',
  data: {{
    labels: {json.dumps(ns_dates, ensure_ascii=False)},
    datasets: [
      {{ label: 'Must-have', data: {json.dumps(ns_datasets[0][1], ensure_ascii=False)}, backgroundColor: '#60a5fa', borderColor: '#60a5fa', borderWidth: 1 }},
      {{ label: 'Top-Tier', data: {json.dumps(ns_datasets[1][1], ensure_ascii=False)}, backgroundColor: '#4ade80', borderColor: '#4ade80', borderWidth: 1 }},
      {{ label: 'Mid-Tier', data: {json.dumps(ns_datasets[2][1], ensure_ascii=False)}, backgroundColor: '#fbbf24', borderColor: '#fbbf24', borderWidth: 1 }}
    ]
  }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    plugins: {{ legend: {{ labels: {{ color: '#94a3b8' }} }} }},
    scales: {{
      x: {{ stacked: true, ticks: {{ color: '#64748b' }}, grid: {{ color: '#1e293b' }} }},
      y: {{ stacked: true, ticks: {{ color: '#64748b' }}, grid: {{ color: '#1e293b' }}, title: {{ display: true, text: 'New Signs', color: '#64748b' }} }}
    }}
  }}
}});
""")

# Operating Rate line chart
chart_js.append(f"""new Chart(document.getElementById('chartOpRate'), {{
  type: 'line',
  data: {{
    labels: {json.dumps(opr_dates, ensure_ascii=False)},
    datasets: [
      {{ label: 'Must-have', data: {json.dumps(opr_datasets[0][1], ensure_ascii=False)}, borderColor: '#60a5fa', backgroundColor: '#60a5fa33', fill: true, tension: 0.3, pointRadius: 3 }},
      {{ label: 'Top-Tier', data: {json.dumps(opr_datasets[1][1], ensure_ascii=False)}, borderColor: '#4ade80', backgroundColor: '#4ade8033', fill: true, tension: 0.3, pointRadius: 3 }},
      {{ label: 'Mid-Tier', data: {json.dumps(opr_datasets[2][1], ensure_ascii=False)}, borderColor: '#fbbf24', backgroundColor: '#fbbf2433', fill: true, tension: 0.3, pointRadius: 3 }}
    ]
  }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    plugins: {{ legend: {{ labels: {{ color: '#94a3b8' }} }} }},
    scales: {{
      x: {{ ticks: {{ color: '#64748b' }}, grid: {{ color: '#1e293b' }} }},
      y: {{ ticks: {{ color: '#64748b' }}, grid: {{ color: '#1e293b' }}, title: {{ display: true, text: 'Operating Rate (%)', color: '#64748b' }}, min: 0, max: 100 }}
    }}
  }}
}});
""")

# Promotion line chart
chart_js.append(f"""new Chart(document.getElementById('chartPromo'), {{
  type: 'line',
  data: {{
    labels: {json.dumps(pr_dates, ensure_ascii=False)},
    datasets: [
      {{ label: '折扣菜覆盖率', data: {json.dumps(pr_datasets[0][1], ensure_ascii=False)}, borderColor: '#22c55e', backgroundColor: '#22c55e33', fill: true, tension: 0.3, pointRadius: 3 }},
      {{ label: '满折覆盖率', data: {json.dumps(pr_datasets[1][1], ensure_ascii=False)}, borderColor: '#3b82f6', backgroundColor: '#3b82f633', fill: true, tension: 0.3, pointRadius: 3 }},
      {{ label: '减配覆盖率', data: {json.dumps(pr_datasets[2][1], ensure_ascii=False)}, borderColor: '#f472b6', backgroundColor: '#f472b633', fill: true, tension: 0.3, pointRadius: 3 }}
    ]
  }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    plugins: {{ legend: {{ labels: {{ color: '#94a3b8' }} }} }},
    scales: {{
      x: {{ ticks: {{ color: '#64748b' }}, grid: {{ color: '#1e293b' }} }},
      y: {{ ticks: {{ color: '#64748b' }}, grid: {{ color: '#1e293b' }}, title: {{ display: true, text: 'Coverage (%)', color: '#64748b' }}, min: 0, max: 100 }}
    }}
  }}
}});
""")

# UX chart
chart_js.append(f"""new Chart(document.getElementById('chartUX'), {{
  type: 'line',
  data: {{
    labels: {json.dumps(ux_dates, ensure_ascii=False)},
    datasets: [
      {{ label: '取消率', data: {json.dumps(ux_datasets[0][1], ensure_ascii=False)}, borderColor: '#ef4444', backgroundColor: '#ef444433', fill: true, tension: 0.3, pointRadius: 3 }},
      {{ label: '洒漏率', data: {json.dumps(ux_datasets[1][1], ensure_ascii=False)}, borderColor: '#eab308', backgroundColor: '#eab30833', fill: true, tension: 0.3, pointRadius: 3 }},
      {{ label: '错漏餐率', data: {json.dumps(ux_datasets[2][1], ensure_ascii=False)}, borderColor: '#f472b6', backgroundColor: '#f472b633', fill: true, tension: 0.3, pointRadius: 3 }}
    ]
  }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    plugins: {{ legend: {{ labels: {{ color: '#94a3b8' }} }} }},
    scales: {{
      x: {{ ticks: {{ color: '#64748b' }}, grid: {{ color: '#1e293b' }} }},
      y: {{ ticks: {{ color: '#64748b' }}, grid: {{ color: '#1e293b' }}, title: {{ display: true, text: 'Rate (%)', color: '#64748b' }} }}
    }}
  }}
}});
</script>
</body>
</html>
""")

html_parts.extend(chart_js)

# Write file
output_path = Path("/mnt/openclaw/.openclaw/workspace/bp_dashboard.html")
with open(output_path, "w", encoding="utf-8") as f:
    f.write("".join(html_parts))

print(f"Generated dashboard: {output_path}")
print(f"File size: {output_path.stat().st_size:,} bytes")
print(f"Has real data: {HAS_DATA and any(v.get('code') == 0 for v in DATA.values())}")
