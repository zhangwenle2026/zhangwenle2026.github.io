#!/usr/bin/env python3
"""Fetch BP dashboard data using CDP HTTP API only"""
import json
import urllib.request
import time
from datetime import datetime, timedelta

TARGET_CHARTS = [
    ("CM - Business Performance", "chart-6kwer-1357d"),
    ("BDM - Business Performance", "chart-stq7y-e6570"),
    ("BD - Business Performance", "dashboard-chart-container-fgaiv-e51fa"),
    ("SMB - MTD Merchant Ranking", "chart-budz2-630e8"),
    ("Last 10 Days - Order Performance", "dashboard-chart-container-7p18g-b0ef9"),
    ("Last 10 days - New Signs", "chart-e8ns5-c9347"),
    ("Last 10 days - Operation Performance", "chart-sqalg-1f515"),
    ("Last 10 days - User Experience", "chart-ltuz6-6cbdc"),
    ("Last 10 days - Promotion", "chart-iyhbp-a03a1"),
]

CDP_URL = "http://127.0.0.1:9222"
DASHBOARD_URL = "https://bi.keetapp.com/v2/dashboard/dashboard-controller?dashboardId=300001446"

def cdp_eval(page_id, expression, await_promise=False):
    url = f"{CDP_URL}/json/evaluate"
    data = json.dumps({
        "targetId": page_id,
        "expression": expression,
        "returnByValue": True,
        "awaitPromise": await_promise
    }).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        resp = urllib.request.urlopen(req, timeout=60)
        return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}

def fetch():
    print(f"[{datetime.now()}] Creating new page...")
    req = urllib.request.Request(f"{CDP_URL}/json/new?about:blank", method="PUT")
    resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
    page_id = resp["id"]
    print(f"New page: {page_id}")
    
    # Navigate
    print(f"Navigating to dashboard...")
    nav_url = f"{CDP_URL}/json/navigate"
    nav_data = json.dumps({"targetId": page_id, "url": DASHBOARD_URL}).encode()
    nav_req = urllib.request.Request(nav_url, data=nav_data, headers={"Content-Type": "application/json"}, method="POST")
    nav_resp = json.loads(urllib.request.urlopen(nav_req, timeout=30).read())
    print(f"Navigation: {nav_resp}")
    
    # Wait for load
    print("Waiting 15s for page load...")
    time.sleep(15)
    
    # Check DashboardController
    print("Checking DashboardController...")
    for i in range(20):
        result = cdp_eval(page_id, "typeof window.DashboardController !== 'undefined'")
        has_dc = result.get("result", {}).get("result", {}).get("value", False)
        if has_dc:
            print("DashboardController ready!")
            break
        time.sleep(2)
    else:
        print("DashboardController timeout")
        # Get URL
        result = cdp_eval(page_id, "window.location.href")
        print(f"Current URL: {result}")
        return {}
    
    # Set date filters
    end_date = datetime.now()
    start = (end_date - timedelta(days=9)).strftime('%Y-%m-%d')
    end = end_date.strftime('%Y-%m-%d')
    print(f"Date range: {start} ~ {end}")
    
    filters_result = cdp_eval(page_id, """
    (async () => {
        const res = await window.DashboardController.getFiltersInfo();
        return JSON.stringify(res);
    })()
    """, await_promise=True)
    filters_raw = filters_result.get("result", {}).get("result", {}).get("value", "{}")
    filters_data = json.loads(filters_raw)
    
    date_filter_updates = []
    for f in filters_data.get("data", []):
        if f.get("filterType") == "time":
            date_filter_updates.append({
                "id": f["key"],
                "userInput": {
                    "value": [start, end],
                    "granularity": "DAY"
                }
            })
    
    if date_filter_updates:
        set_result = cdp_eval(page_id, f"""
        (async () => {{
            const res = await window.DashboardController.setFiltersValues({json.dumps(date_filter_updates)});
            return JSON.stringify(res);
        }})()
        """, await_promise=True)
        set_raw = set_result.get("result", {}).get("result", {}).get("value", "{}")
        print(f"Set filters: {json.loads(set_raw).get('code', '?')}")
        time.sleep(3)
    
    results = {}
    for name, cid in TARGET_CHARTS:
        print(f"Querying: {name}")
        try:
            query_expr = f"""
            (async () => {{
                const res = await window.DashboardController.executeQueryAndGetCHNResult(['{cid}'], {{force: true}});
                return JSON.stringify(res);
            }})()
            """
            result = cdp_eval(page_id, query_expr, await_promise=True)
            data_raw = result.get("result", {}).get("result", {}).get("value", "{}")
            data = json.loads(data_raw)
            results[name] = data
            rows = len(data.get("data", {}).get("data", [])) if data.get("code") == 0 else 0
            print(f"  -> {'OK' if data.get('code')==0 else 'ERR'}, {rows} rows")
        except Exception as e:
            print(f"  -> Exception: {e}")
            results[name] = {"code": -1, "message": str(e)}
        time.sleep(1)
    
    return results

def main():
    results = fetch()
    output_path = "/mnt/openclaw/.openclaw/workspace/bi_raw_data.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nSaved to {output_path}")
    for name, data in results.items():
        status = "OK" if data.get("code") == 0 else f"ERR({data.get('code')})"
        rows = len(data.get("data", {}).get("data", [])) if data.get("code") == 0 else 0
        print(f"  {name}: {status}, {rows} rows")

if __name__ == "__main__":
    main()
