#!/usr/bin/env python3
"""Fetch fresh BP data from BI via CDP and update dashboard HTML"""
import asyncio
import json
import websockets
from collections import defaultdict
from datetime import datetime
import math

PAGE_WS = "ws://localhost:9222/devtools/page/C52CA7B272E499AF948CF8AAE789FD00"

async def send_cmd(ws, cmd_id, method, params=None):
    msg = {"id": cmd_id, "method": method}
    if params:
        msg["params"] = params
    await ws.send(json.dumps(msg))
    return msg["id"]

async def recv_until(ws, cmd_id, timeout=30):
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        try:
            r = await asyncio.wait_for(ws.recv(), timeout=deadline - asyncio.get_event_loop().time())
            msg = json.loads(r)
            if msg.get("id") == cmd_id:
                return msg
        except asyncio.TimeoutError:
            break
    return None

async def fetch_bp_data():
    async with websockets.connect(PAGE_WS) as ws:
        print("Connected to BI tab")
        await send_cmd(ws, 1, "Runtime.enable")
        await send_cmd(ws, 2, "Page.enable")
        for _ in range(5):
            try:
                await asyncio.wait_for(ws.recv(), timeout=1)
            except asyncio.TimeoutError:
                break

        await send_cmd(ws, 10, "Runtime.evaluate", {"expression": "location.href", "returnByValue": True})
        resp = await recv_until(ws, 10, timeout=10)
        url = resp.get("result",{}).get("result",{}).get("value","") if resp else ""
        print(f"URL: {url}")
        if "login" in url.lower() or not url:
            print("SSO expired or page not loaded")
            return None

        for attempt in range(30):
            await send_cmd(ws, 20+attempt, "Runtime.evaluate", {
                "expression": "typeof window.DashboardController",
                "returnByValue": True
            })
            resp = await recv_until(ws, 20+attempt, timeout=5)
            dc = resp.get("result",{}).get("result",{}).get("value","") if resp else ""
            if dc == "object":
                print(f"DashboardController ready at attempt {attempt+1}")
                break
            await asyncio.sleep(1)
        else:
            print("DashboardController not ready")
            return None

        charts = [
            ("Business Performance", "chart-6kwer-1357d"),
            ("New Signs", "chart-e8ns5-c9347"),
            ("Operation Performance", "chart-sqalg-1f515"),
            ("Promotion", "chart-iyhbp-a03a1"),
            ("User Experience", "chart-ltuz6-6cbdc"),
        ]

        results = {}
        cmd_id = 100
        for name, chart_id in charts:
            print(f"Querying {name} ({chart_id})...")
            expr = f'''
                new Promise((resolve) => {{
                    try {{
                        window.DashboardController.executeQueryAndGetCHNResult("{chart_id}")
                            .then(res => resolve({{ok:true, data:JSON.stringify(res)}}))
                            .catch(err => resolve({{ok:false, error:err.message || String(err)}}));
                    }} catch(e) {{
                        resolve({{ok:false, error: "exception: " + e.message}});
                    }}
                }})
            '''
            await send_cmd(ws, cmd_id, "Runtime.evaluate", {
                "expression": expr,
                "awaitPromise": True,
                "returnByValue": True,
                "timeout": 60000
            })
            resp = await recv_until(ws, cmd_id, timeout=70)
            cmd_id += 1
            if not resp:
                print(f"  -> TIMEOUT")
                results[name] = {"error": "timeout"}
                await asyncio.sleep(2)
                continue

            result_obj = resp.get("result",{}).get("result",{})
            val = result_obj.get("value",{})

            if val and val.get("ok"):
                try:
                    data = json.loads(val["data"])
                    results[name] = data
                    if isinstance(data, dict) and data.get("code") == 0:
                        rows = data.get("data",{}).get("data",[])
                        print(f"  -> OK {len(rows)} rows")
                    else:
                        print(f"  -> Response code: {data.get('code', 'N/A')}")
                except Exception as e:
                    print(f"  -> Parse error: {e}")
                    results[name] = {"error": f"parse: {e}"}
            else:
                err = val.get("error", "unknown") if val else str(result_obj)
                print(f"  -> ERROR: {err}")
                results[name] = {"error": err}

            await asyncio.sleep(2)

        has_data = sum(1 for v in results.values() if isinstance(v, dict) and v.get("code") == 0)
        print(f"Charts with data: {has_data}/{len(charts)}")

        if has_data >= 3:
            return results
        return None

def generate_dashboard(data, output_path):
    """Generate BP dashboard HTML from data"""
    
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
            return '#06b6d4'
        elif p == 'Mid-Tier':
            return '#eab308'
        else:
            return '#e2e8f0'

    # --- Process Business Performance (city-level) ---
    bp_raw = data['Business Performance']['data']['data']
    # bp rows: [date, region, city, orders, aov, gmv, store_avg, ...]
    orders_by_date = {}
    gmv_by_date = {}
    for row in bp_raw:
        date = row[0]
        orders = int(row[3]) if row[3] and str(row[3]).isdigit() else 0
        gmv = float(row[5]) if row[5] else 0
        if date not in orders_by_date:
            orders_by_date[date] = 0
            gmv_by_date[date] = 0
        orders_by_date[date] += orders
        gmv_by_date[date] += gmv

    order_dates = sorted(orders_by_date.keys(), reverse=True)
    order_total = sum(orders_by_date.values())
    gmv_total = sum(gmv_by_date.values())
    avg_aov = gmv_total / order_total if order_total > 0 else 0
    latest_date = parse_date(order_dates[0]) if order_dates else 'N/A'

    # For Order Performance section, we need priority breakdown.
    # Business Performance doesn't have priority, so we show total orders per date
    # and create a simplified view without priority breakdown.
    # We can still show the daily totals.
    orders_daily = {d: orders_by_date[d] for d in order_dates}

    # --- Process New Signs ---
    sign_raw = data['New Signs']['data']['data']
    signs = defaultdict(dict)
    for row in sign_raw:
        date, prio, val = row[0], row[1], int(row[2])
        signs[date][prio] = val
    sign_total = sum(v for d in signs.values() for v in d.values())

    # --- Process Promotion ---
    promo_raw = data['Promotion']['data']['data']
    promos = {}
    for row in promo_raw:
        date = row[0]
        promos[date] = [float(row[1]), float(row[2]), float(row[3])]

    # --- Process User Experience ---
    ux_raw = data['User Experience']['data']['data']
    ux = {}
    for row in ux_raw:
        date = row[0]
        ux[date] = [float(row[1]), float(row[2]), float(row[3])]
    ux_dates = sorted(ux.keys(), reverse=True)

    # --- Process CM Business Performance (city-level, latest date only) ---
    cm_rows = []
    latest_bp = max(bp_raw, key=lambda r: r[0]) if bp_raw else None
    latest_bp_date = latest_bp[0] if latest_bp else None
    
    for row in bp_raw:
        if row[0] != latest_bp_date:
            continue
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
            'orders': int(row[3]) if row[3] and str(row[3]).isdigit() else 0,
            'aov': safe_float(row[4]),
            'gmv': safe_float(row[5]),
            'store_avg': safe_float(row[6]),
        })

    # Build HTML
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
    <div class="delta">Sum across all regions</div>
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

    # --- Order Performance Section (daily totals, no priority breakdown) ---
    html += '''<div class="section">
  <h2>Last 10 Days — Daily Orders</h2>
  <div class="table-wrap">
    <table>
      <tr><th>Date</th><th class="num-col">Total Orders</th></tr>
'''
    for date in order_dates:
        total = orders_daily.get(date, 0)
        date_str = parse_date(date)
        html += f'      <tr><td class="date-col">{date_str}</td><td class="num-col">{fmt_num(total)}</td></tr>\n'
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

    # --- CM Business Performance Section (latest date only) ---
    cm_date_str = parse_date(latest_bp_date) if latest_bp_date else 'N/A'
    html += f'''<div class="section">
  <h2>CM Business Performance ({cm_date_str})</h2>
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

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"Dashboard saved to {output_path}")
    print(f"Total Orders: {fmt_num(order_total)}")
    print(f"Total GMV: {fmt_gmv(gmv_total)}")
    print(f"Avg AOV: {fmt_gmv(avg_aov)}")
    print(f"Total New Signs: {fmt_num(sign_total)}")
    return True

async def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting BP data fetch...")
    
    results = await fetch_bp_data()
    if not results:
        print("Failed to fetch data from BI")
        return False
    
    # Save raw data
    raw_path = f"/mnt/openclaw/.openclaw/workspace/bi_raw_data.json"
    with open(raw_path, 'w') as f:
        json.dump({
            "Last 10 Days - Order Performance": results.get("Business Performance", {}),
            "Last 10 days - New Signs": results.get("New Signs", {}),
            "Last 10 days - Promotion": results.get("Promotion", {}),
            "Last 10 days - Operation Performance": results.get("Operation Performance", {}),
            "Last 10 days - User Experience": results.get("User Experience", {}),
        }, f, ensure_ascii=False, indent=2)
    print(f"Raw data saved to {raw_path}")
    
    # Generate dashboard
    success = generate_dashboard({
        "Business Performance": results.get("Business Performance", {}),
        "New Signs": results.get("New Signs", {}),
        "Promotion": results.get("Promotion", {}),
        "Operation Performance": results.get("Operation Performance", {}),
        "User Experience": results.get("User Experience", {}),
    }, "/mnt/openclaw/.openclaw/workspace/bp_dashboard.html")
    
    return success

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
