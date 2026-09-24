#!/usr/bin/env python3
"""Quick DBR data fetch via CDP browser-level WS"""
import asyncio
import json
import urllib.request
from datetime import datetime, timedelta
import websockets

CDP_URL = "http://127.0.0.1:9222"
DASHBOARD_URL = "https://bi.keetapp.com/v2/dashboard/dashboard-controller?dashboardId=300001446"

async def cdp_send(ws, session_id, method, params=None):
    cmd_id = int(datetime.now().timestamp() * 1000) % 100000
    cmd = {"id": cmd_id, "method": method, "params": params or {}}
    if session_id:
        cmd["sessionId"] = session_id
    await ws.send(json.dumps(cmd))
    # Wait for response matching our id
    while True:
        raw = await ws.recv()
        resp = json.loads(raw)
        if resp.get("id") == cmd_id:
            return resp
        # else it's an event, log and continue
        print(f"  [Event] {resp.get('method', 'unknown')}")

async def eval_js(ws, session_id, js):
    resp = await cdp_send(ws, session_id, "Runtime.evaluate", {
        "expression": js, "returnByValue": True, "awaitPromise": True
    })
    return resp.get("result", {}).get("result", {}).get("value")

async def main():
    info = json.loads(urllib.request.urlopen(f"{CDP_URL}/json/version", timeout=5).read())
    ws_url = info["webSocketDebuggerUrl"]
    print(f"Browser WS: {ws_url[:70]}...")

    async with websockets.connect(ws_url) as ws:
        # Get targets
        resp = await cdp_send(ws, None, "Target.getTargets")
        print(f"getTargets resp keys: {list(resp.keys())}")
        if "result" not in resp:
            print(f"ERROR: {resp}")
            return
        targets = resp["result"]["targetInfos"]
        bi_target = next((t for t in targets if "bi.keetapp" in t["url"] and "300001446" in t["url"]), None)

        if not bi_target:
            print("No BI dashboard tab found!")
            for t in targets:
                if "bi.keetapp" in t["url"]:
                    print(f"  Found bi tab: {t['url'][:80]}")
            return

        target_id = bi_target["targetId"]
        print(f"Found BI tab: {target_id}")

        # Attach to target
        resp = await cdp_send(ws, None, "Target.attachToTarget", {"targetId": target_id, "flatten": True})
        print(f"attach resp keys: {list(resp.keys())}")
        if "result" not in resp:
            print(f"attach error: {resp}")
            return
        session_id = resp["result"]["sessionId"]
        print(f"Session: {session_id[:20]}...")

        # Enable runtime
        await cdp_send(ws, session_id, "Runtime.enable")
        await asyncio.sleep(1)

        # Navigate to dashboard
        await cdp_send(ws, session_id, "Page.navigate", {"url": DASHBOARD_URL})
        await asyncio.sleep(8)

        # Wait for DashboardController
        for i in range(15):
            ready = await eval_js(ws, session_id, "typeof window.DashboardController !== 'undefined'")
            if ready:
                print("DashboardController ready!")
                break
            await asyncio.sleep(1)
        else:
            print("Timeout waiting for DashboardController")
            current_url = await eval_js(ws, session_id, "window.location.href")
            print(f"Current URL: {current_url}")
            return

        # Set date filter: last 10 days
        end = datetime.now()
        start = (end - timedelta(days=9)).strftime('%Y-%m-%d')
        end_str = end.strftime('%Y-%m-%d')
        print(f"Date range: {start} ~ {end_str}")

        # Get filters
        filters_raw = await eval_js(ws, session_id, """
        (async () => {
            const res = await window.DashboardController.getFiltersInfo();
            return JSON.stringify(res);
        })()
        """)
        filters = json.loads(filters_raw or '{}')

        date_updates = []
        for f in filters.get('data', []):
            if f.get('filterType') == 'time':
                date_updates.append({
                    "id": f["key"],
                    "userInput": {"value": [start, end_str], "granularity": "DAY"}
                })

        if date_updates:
            set_res = await eval_js(ws, session_id, f"""
            (async () => {{
                const res = await window.DashboardController.setFiltersValues({json.dumps(date_updates)});
                return JSON.stringify(res);
            }})()
            """)
            print(f"Set filters: {json.loads(set_res or '{{}}').get('code', '?')}")
            await asyncio.sleep(3)

        # Get components
        comps_raw = await eval_js(ws, session_id, """
        (async () => {
            const res = await window.DashboardController.getComponents();
            return JSON.stringify(res);
        })()
        """)
        comps = json.loads(comps_raw or '{}')

        tab_map = {}
        chart_map = {}
        for c in comps.get('data', []):
            if c['componentType'] == 'tab':
                tab_map[c['componentName']] = c['componentId']
            elif c['componentType'] == 'chart':
                chart_map[c['componentName']] = c['componentId']

        print(f"Tabs: {list(tab_map.keys())}")
        print(f"Charts: {len(chart_map)}")

        # Activate all tabs
        for tab_name in tab_map:
            clicked = await eval_js(ws, session_id, f"""
            (() => {{
                const tabs = document.querySelectorAll('.tab-nav-item');
                for (const t of tabs) {{
                    const title = t.querySelector('.tab-title')?.textContent?.trim();
                    if (title === '{tab_name}') {{ t.click(); return true; }}
                }}
                return false;
            }})()
            """)
            print(f"Clicked tab '{tab_name}': {clicked}")
            await asyncio.sleep(1)

        # Target charts
        target_names = [
            "Last 10 Days - Order Performance",
            "Last 10 days - New Signs",
            "Last 10 days - Operation Performance",
            "Last 10 days - User Experience",
            "Last 10 days - Promotion",
        ]

        results = {}
        for name in target_names:
            cid = chart_map.get(name)
            if not cid:
                print(f"Chart not found: {name}")
                continue
            print(f"Querying: {name} ({cid})")
            try:
                res = await eval_js(ws, session_id, f"""
                (async () => {{
                    const res = await window.DashboardController.executeQueryAndGetCHNResult(['{cid}'], {{force: true}});
                    return JSON.stringify(res);
                }})()
                """)
                data = json.loads(res or '{}')
                results[name] = data
                rows = len(data.get('data', {}).get('data', [])) if data.get('code') == 0 else 0
                print(f"  -> code={data.get('code')}, rows={rows}")
            except Exception as e:
                print(f"  -> ERROR: {e}")
                results[name] = {"code": -1, "message": str(e)}
            await asyncio.sleep(1)

        # Save results
        output = {
            "date": end.strftime('%Y%m%d'),
            "data_source": "bi_raw_data_fallback",
            "notes": f"BRT {end.strftime('%Y-%m-%d')}. BI tab data latest date.",
            "results": results,
            "fetch_date": datetime.now().isoformat(),
        }

        with open('/mnt/openclaw/.openclaw/workspace/dbr_data_latest.json', 'w') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"\nSaved to dbr_data_latest.json")

        # Also save raw
        with open('/mnt/openclaw/.openclaw/workspace/bi_raw_data.json', 'w') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    asyncio.run(main())
