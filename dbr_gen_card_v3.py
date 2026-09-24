#!/usr/bin/env python3
"""Generate DBR daily report card - v3 with correct column indices."""
import json
import os
import subprocess
from datetime import datetime

# Load data
with open("/mnt/openclaw/.openclaw/workspace/dbr_data_20260828.json", "r") as f:
    dbr_data = json.load(f)

results = dbr_data.get("results", {})

# --- Parse Business Performance ---
bp_rows = results.get("Business Performance", {}).get("data", {}).get("data", [])
city_data = []
metro_orders = 0
metro_gmv = 0
metro_aov = 0
metro_cancel_rate = 0
metro_mtd = 0
metro_order_wow = 0

for row in bp_rows:
    city = row[2]
    orders = float(row[3]) if row[3] not in ["NaN", "", "NULL"] else 0   # col 3 = 订单量
    aov = float(row[4]) if row[4] not in ["NaN", "", "NULL"] else 0      # col 4 = 实付单均价
    gmv = float(row[5]) if row[5] not in ["NaN", "", "NULL"] else 0      # col 5 = 实付交易额
    cancel_rate = float(row[9]) if row[9] not in ["NaN", "", "NULL"] else 0  # col 9 = CTR(Avg)
    mtd_orders = float(row[10]) if row[10] not in ["NaN", "", "NULL"] else 0  # col 10 = MTD Orders
    order_wow = float(row[11]) if row[11] not in ["NaN", "", "NULL"] else 0   # col 11 = WoW

    if city == "NULL":
        metro_orders = orders
        metro_gmv = gmv
        metro_aov = aov
        metro_cancel_rate = cancel_rate
        metro_mtd = mtd_orders
        metro_order_wow = order_wow
    else:
        city_data.append({
            "city": city,
            "orders": orders,
            "gmv": gmv,
            "aov": aov,
            "cancel_rate": cancel_rate,
        })

city_data.sort(key=lambda x: x["orders"], reverse=True)

# --- Parse New Signs ---
ns_rows = results.get("New Signs", {}).get("data", {}).get("data", [])
ns_by_date = {}
for row in ns_rows:
    date, tier, val = row[0], row[1], int(row[2])
    if date not in ns_by_date:
        ns_by_date[date] = {}
    ns_by_date[date][tier] = val

latest_date = "20260828"
latest_ns = sum(ns_by_date.get(latest_date, {}).values())
mtd_ns = sum(sum(ns_by_date[d].values()) for d in ns_by_date if d.startswith("202608"))

# --- Parse Operation Performance ---
op_rows = results.get("Operation Performance", {}).get("data", {}).get("data", [])
op_by_date = {}
for row in op_rows:
    date, tier, val = row[0], row[1], float(row[2])
    if date not in op_by_date:
        op_by_date[date] = {}
    op_by_date[date][tier] = val

latest_op = op_by_date.get(latest_date, {})

# --- Parse User Experience ---
ux_rows = results.get("User Experience", {}).get("data", {}).get("data", [])
latest_ux = None
for row in ux_rows:
    if row[0] == latest_date:
        latest_ux = row
        break
if not latest_ux:
    latest_ux = ux_rows[-1] if ux_rows else ["", "0", "0", "0"]

ux_date = latest_ux[0]
ux_total = float(latest_ux[1])
ux_spill = float(latest_ux[2])
ux_missing = float(latest_ux[3])

# --- Parse Promotion ---
promo_rows = results.get("Promotion", {}).get("data", {}).get("data", [])
latest_promo = None
for row in promo_rows:
    if row[0] == latest_date:
        latest_promo = row
        break
if not latest_promo:
    latest_promo = promo_rows[-1] if promo_rows else ["", "0", "0", "0"]

promo_discount = float(latest_promo[1])
promo_full = float(latest_promo[2])
promo_subsidy = float(latest_promo[3])

# Format helpers
def fmt_num(n):
    return f"{n:,.0f}" if abs(n) >= 1000 else f"{n:.0f}"

def fmt_pct(p):
    return f"{p*100:.1f}%"

def fmt_date(d):
    return f"{d[4:6]}/{d[6:8]}"

def wow_color(val):
    return "wow-up" if val >= 0 else "wow-down"

def wow_arrow(val):
    return "↑" if val >= 0 else "↓"

# Build HTML
date_display = fmt_date(latest_date)
year = latest_date[:4]

html = f'''<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f0f2f5; padding: 20px; }}
.card {{ width: 780px; background: white; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); overflow: hidden; margin: 0 auto; }}
.header {{ background: linear-gradient(135deg, #1565c0 0%, #0d47a1 100%); color: white; padding: 24px 28px; }}
.header h1 {{ font-size: 22px; font-weight: 600; margin-bottom: 4px; }}
.header .subtitle {{ font-size: 13px; opacity: 0.85; }}
.section {{ padding: 18px 28px; border-bottom: 1px solid #f0f0f0; }}
.section:last-child {{ border-bottom: none; }}
.section-title {{ font-size: 13px; font-weight: 600; color: #1565c0; margin-bottom: 12px; text-transform: uppercase; letter-spacing: 0.5px; }}
.metrics-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }}
.metric {{ text-align: center; padding: 10px; background: #f8f9fa; border-radius: 8px; }}
.metric-value {{ font-size: 22px; font-weight: 700; color: #1565c0; margin-bottom: 3px; }}
.metric-label {{ font-size: 11px; color: #666; }}
.metric-sub {{ font-size: 10px; color: #999; margin-top: 2px; }}
.table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
.table th {{ background: #f5f7fa; color: #666; font-weight: 500; padding: 7px 10px; text-align: left; }}
.table td {{ padding: 7px 10px; border-bottom: 1px solid #f0f0f0; }}
.table tr:last-child td {{ border-bottom: none; }}
.table .total {{ font-weight: 600; background: #f5f7fa; }}
.insights {{ background: #e3f2fd; padding: 12px 16px; border-radius: 8px; margin-top: 6px; }}
.insights-title {{ font-size: 12px; font-weight: 600; color: #1565c0; margin-bottom: 5px; }}
.insights-text {{ font-size: 11px; color: #333; line-height: 1.5; }}
.footer {{ padding: 12px 28px; background: #f5f7fa; font-size: 10px; color: #999; text-align: center; }}
.wow-up {{ color: #2e7d32; }}
.wow-down {{ color: #c62828; }}
.alert {{ background: #fff3e0; border-left: 3px solid #f57c00; padding: 8px 12px; margin-top: 8px; font-size: 11px; color: #e65100; }}
</style>
</head>
<body>
<div class="card">
  <div class="header">
    <h1>📊 SP Metropolitan Region Daily Report</h1>
    <div class="subtitle">DBR Daily Business Report · {date_display}, {year} (BRT) · Data Date: {latest_date}</div>
  </div>

  <div class="section">
    <div class="section-title">Orders Overview</div>
    <div class="metrics-grid">
      <div class="metric">
        <div class="metric-value">{fmt_num(metro_orders)}</div>
        <div class="metric-label">Orders Yesterday</div>
        <div class="metric-sub {wow_color(metro_order_wow)}">WoW: {wow_arrow(metro_order_wow)} {abs(metro_order_wow)*100:.1f}%</div>
      </div>
      <div class="metric">
        <div class="metric-value">R$ {fmt_num(metro_gmv)}</div>
        <div class="metric-label">GMV (R$)</div>
        <div class="metric-sub">AOV: R$ {metro_aov:.2f}</div>
      </div>
      <div class="metric">
        <div class="metric-value">{fmt_pct(ux_total)}</div>
        <div class="metric-label">Cancel Rate</div>
        <div class="metric-sub">Total</div>
      </div>
    </div>
  </div>

  <div class="section">
    <div class="section-title">City Breakdown ({date_display})</div>
    <table class="table">
      <tr><th>City</th><th>Orders</th><th>GMV (R$)</th><th>AOV</th></tr>
'''

for c in city_data:
    html += f'''      <tr><td>{c["city"]}</td><td>{fmt_num(c["orders"])}</td><td>{fmt_num(c["gmv"])}</td><td>R$ {c["aov"]:.2f}</td></tr>
'''

html += f'''      <tr class="total"><td>Metro Total</td><td>{fmt_num(metro_orders)}</td><td>{fmt_num(metro_gmv)}</td><td>R$ {metro_aov:.2f}</td></tr>
    </table>
  </div>

  <div class="section">
    <div class="section-title">New Signings ({date_display})</div>
    <div class="metrics-grid">
      <div class="metric">
        <div class="metric-value">{ns_by_date.get(latest_date, {}).get("Top-Tier", 0)}</div>
        <div class="metric-label">Top-Tier</div>
      </div>
      <div class="metric">
        <div class="metric-value">{ns_by_date.get(latest_date, {}).get("Mid-Tier", 0)}</div>
        <div class="metric-label">Mid-Tier</div>
      </div>
      <div class="metric">
        <div class="metric-value">{ns_by_date.get(latest_date, {}).get("Must-have", 0)}</div>
        <div class="metric-label">Must-have</div>
      </div>
    </div>
    <div class="metric-sub" style="text-align:center;margin-top:8px;">Total: <strong>{latest_ns}</strong> | MTD Aug: <strong>{mtd_ns}</strong></div>
  </div>

  <div class="section">
    <div class="section-title">Operating Performance ({date_display})</div>
    <div class="metrics-grid">
      <div class="metric">
        <div class="metric-value">{fmt_pct(latest_op.get("Top-Tier", 0))}</div>
        <div class="metric-label">Top-Tier</div>
      </div>
      <div class="metric">
        <div class="metric-value">{fmt_pct(latest_op.get("Mid-Tier", 0))}</div>
        <div class="metric-label">Mid-Tier</div>
      </div>
      <div class="metric">
        <div class="metric-value">{fmt_pct(latest_op.get("Must-have", 0))}</div>
        <div class="metric-label">Must-have</div>
      </div>
    </div>
  </div>

  <div class="section">
    <div class="section-title">Promotion Coverage ({fmt_date(latest_promo[0])})</div>
    <div class="metrics-grid">
      <div class="metric">
        <div class="metric-value">{fmt_pct(promo_discount)}</div>
        <div class="metric-label">Discount Rate</div>
      </div>
      <div class="metric">
        <div class="metric-value">{fmt_pct(promo_full)}</div>
        <div class="metric-label">Full Discount</div>
      </div>
      <div class="metric">
        <div class="metric-value">{fmt_pct(promo_subsidy)}</div>
        <div class="metric-label">Subsidy</div>
      </div>
    </div>
  </div>

  <div class="section">
    <div class="section-title">User Experience ({fmt_date(ux_date)})</div>
    <div class="metrics-grid">
      <div class="metric">
        <div class="metric-value">{fmt_pct(ux_total)}</div>
        <div class="metric-label">Total Cancel</div>
      </div>
      <div class="metric">
        <div class="metric-value">{fmt_pct(ux_spill)}</div>
        <div class="metric-label">Spill/Damage</div>
      </div>
      <div class="metric">
        <div class="metric-value">{fmt_pct(ux_missing)}</div>
        <div class="metric-label">Missing/Wrong</div>
      </div>
    </div>
  </div>

  <div class="section">
    <div class="insights">
      <div class="insights-title">Key Insights</div>
      <div class="insights-text">
        Metro Region processed <strong>{fmt_num(metro_orders)}</strong> orders on {date_display}
        ({wow_arrow(metro_order_wow)} {abs(metro_order_wow)*100:.1f}% vs prior day).
        GMV: <strong>R$ {fmt_num(metro_gmv)}</strong> (AOV: R$ {metro_aov:.2f}).
        New signings: <strong>{latest_ns}</strong> merchants ({date_display}).
        Operating rates: Top-Tier {fmt_pct(latest_op.get("Top-Tier",0))}, Mid-Tier {fmt_pct(latest_op.get("Mid-Tier",0))}, Must-have {fmt_pct(latest_op.get("Must-have",0))}.
        Cancel rate: <strong>{fmt_pct(ux_total)}</strong> (Spill {fmt_pct(ux_spill)}, Missing {fmt_pct(ux_missing)}).
        Promotion coverage: Discount {fmt_pct(promo_discount)}, Subsidy {fmt_pct(promo_subsidy)}.
      </div>
    </div>
  </div>

  <div class="footer">
    Data source: BI Dashboard · Generated {datetime.now().strftime("%Y-%m-%d %H:%M")} · SP Metropolitan CM
  </div>
</div>
</body>
</html>'''

html_path = "/mnt/openclaw/.openclaw/workspace/dbr_card_20260828.html"
with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)

print(f"HTML saved to {html_path}")

# Screenshot
img_path = "/mnt/openclaw/.openclaw/workspace/dbr_card_20260828.png"

result = subprocess.run([
    "chromium-browser", "--headless", "--disable-gpu", "--no-sandbox",
    "--window-size=780,1400", "--screenshot=" + img_path,
    "--hide-scrollbars", html_path
], capture_output=True, text=True, timeout=60)

if os.path.exists(img_path):
    size = os.path.getsize(img_path)
    print(f"Screenshot: {img_path} ({size} bytes)")
else:
    print("Screenshot failed")
    print(f"stderr: {result.stderr[:500]}")
