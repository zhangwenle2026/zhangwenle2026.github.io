#!/usr/bin/env python3
"""Fetch BP dashboard data using existing BI tab via CDP WebSocket"""
import json
import asyncio
import websockets
import urllib.request
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

CDP_HTTP = "http://127.0.0.1:9222"
BI_TAB_ID = "580D7CD6BACD984F10EC713527371E4D"

async def send_cmd(ws, method, params=None):
    msg_id = int(datetime.now().timestamp() * 1000) % 100000
    cmd = {"id": msg_id, "method": method, "params": params or {}}
    await ws.send(json.dumps(cmd))
    resp = await ws.recv()
    return json.loads(resp)

async def evaluate(ws, expression, await_promise=False, timeout=30):
    result = await send_cmd(ws, "Runtime.evaluate", {
        "expression": expression,
        "returnByValue": True,
        "awaitPromise": await_promise,
        "timeout": timeout * 1000
    })
    return result

async def fetch():
    print(f"[{datetime.now()}] Connecting to existing BI tab: {BI_TAB_ID}")
    
    # Get WebSocket URL for the existing tab
    ws_url = f"ws://127.0.0.1:9222/devtools/page/{BI_TAB_ID}"
    
    async with websockets.connect(ws_url) as ws:
        # Enable runtime
        await send_cmd(ws, "Runtime.enable")
        await asyncio.sleep(0.5)
        
        # Check if DashboardController exists
        print("Checking DashboardController...")
        for i in range(10):
            result = await evaluate(ws, "typeof window.DashboardController !== 'undefined'")
            val = result.get("result", {}).get("result", {}).get("value", False)
            if val:
                print("DashboardController ready!")
                break
            await asyncio.sleep(1)
        else:
            print("DashboardController NOT found on existing tab")
            # Check what's on the page
            url_res = await evaluate(ws, "window.location.href")
            print(f"URL: {url_res}")
            dc_res = await evaluate(ws, "typeof window.DashboardController")
            print(f"DashboardController type: {dc_res}")
            return {}
        
        # Get all components
        print("Getting components...")
        comps_res = await evaluate(ws, """
        (async () => {
            const res = await window.DashboardController.getComponents();
            return JSON.stringify(res);
        })()
        """, await_promise=True)
        
        comps_raw = comps_res.get("result", {}).get("result", {}).get("value", "{}")
        comps_data = json.loads(comps_raw)
        
        if comps_data.get("code") != 0:
            print(f"getComponents failed: {comps_data}")
            return {}
        
        components = {}
        tab_components = {}
        for c in comps_data.get("data", []):
            components[c.get("componentName", "")] = c
            if c.get("componentType") == "tab":
                tab_components[c.get("componentName", "")] = c
        
        print(f"Found {len(components)} components, {len(tab_components)} tabs")
        
        # Find target chart IDs
        chart_id_map = {}
        for name, expected_cid in TARGET_CHARTS:
            if name in components:
                cid = components[name].get("componentId")
                chart_id_map[name] = cid
                print(f"  {name} -> {cid}")
            else:
                print(f"  {name} -> NOT FOUND")
        
        # Find which tabs need activation
        tabs_to_click = set()
        for name, cid in chart_id_map.items():
            chart = components.get(name)
            if not chart:
                continue
            for tab_name, tab in tab_components.items():
                children = tab.get("childrenComponents", [])
                child_ids = [ch["componentId"] if isinstance(ch, dict) else ch for ch in children]
                if chart.get("componentId") in child_ids:
                    tabs_to_click.add(tab_name)
                    print(f"Chart '{name}' in tab '{tab_name}'")
                    break
        
        # Activate tabs
        for tab_name in tabs_to_click:
            click_res = await evaluate(ws, f"""
            (() => {{
                const tabs = document.querySelectorAll('.tab-nav-item');
                for (const t of tabs) {{
                    const title = t.querySelector('.tab-title')?.textContent?.trim();
                    if (title === '{tab_name}') {{
                        t.click();
                        return true;
                    }}
                }}
                return false;
            }})()
            """)
            clicked = click_res.get("result", {}).get("result", {}).get("value", False)
            print(f"Clicked tab '{tab_name}': {clicked}")
            await asyncio.sleep(2)
        
        # Query all charts
        results = {}
        for name, cid in chart_id_map.items():
            print(f"Querying: {name} ({cid})")
            try:
                query_expr = f"""
                (async () => {{
                    const res = await window.DashboardController.executeQueryAndGetCHNResult(['{cid}'], {{force: true}});
                    return JSON.stringify(res);
                }})()
                """
                result = await asyncio.wait_for(
                    evaluate(ws, query_expr, await_promise=True),
                    timeout=60
                )
                data_raw = result.get("result", {}).get("result", {}).get("value", "{}")
                data = json.loads(data_raw)
                results[name] = data
                rows = len(data.get("data", {}).get("data", [])) if data.get("code") == 0 else 0
                print(f"  -> {'OK' if data.get('code')==0 else 'ERR'}, {rows} rows")
            except asyncio.TimeoutError:
                print(f"  -> TIMEOUT")
                results[name] = {"code": -2, "message": "timeout"}
            except Exception as e:
                print(f"  -> Exception: {e}")
                results[name] = {"code": -1, "message": str(e)}
            await asyncio.sleep(1)
    
    return results

async def main():
    results = await fetch()
    output_path = "/mnt/openclaw/.openclaw/workspace/bi_raw_data.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nSaved to {output_path}")
    for name, data in results.items():
        status = "OK" if data.get("code") == 0 else f"ERR({data.get('code')})"
        rows = len(data.get("data", {}).get("data", [])) if data.get("code") == 0 else 0
        print(f"  {name}: {status}, {rows} rows")

if __name__ == "__main__":
    asyncio.run(main())
