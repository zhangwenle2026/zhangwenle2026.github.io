import asyncio
import json
import websockets
import urllib.request

CDP_URL = "http://127.0.0.1:9222"

async def cdp_fetch():
    # Create a new page via CDP HTTP
    req = urllib.request.Request(f"{CDP_URL}/json/new?about:blank")
    with urllib.request.urlopen(req, timeout=10) as resp:
        page_info = json.loads(resp.read().decode())
    
    ws_url = page_info["webSocketDebuggerUrl"]
    print(f"New page: {page_info['id']}, WS: {ws_url}")
    
    async with websockets.connect(ws_url) as ws:
        # Enable Page and Runtime domains
        await ws.send(json.dumps({"id": 1, "method": "Page.enable"}))
        await ws.send(json.dumps({"id": 2, "method": "Runtime.enable"}))
        
        # Wait for enable responses
        for _ in range(2):
            resp = await asyncio.wait_for(ws.recv(), timeout=10)
            print(f"Enable resp: {resp[:100]}")
        
        # Navigate to BI dashboard
        print("Navigating to BI dashboard...")
        await ws.send(json.dumps({
            "id": 3,
            "method": "Page.navigate",
            "params": {
                "url": "https://bi.keetapp.com/v2/dashboard/dashboard-controller?dashboardId=300001446"
            }
        }))
        
        # Wait for load event
        while True:
            resp = await asyncio.wait_for(ws.recv(), timeout=60)
            msg = json.loads(resp)
            if msg.get("method") == "Page.loadEventFired":
                print("Page loaded!")
                break
            if msg.get("id") == 3:
                print(f"Navigate resp: {resp[:200]}")
        
        # Wait for DashboardController
        print("Waiting for DashboardController...")
        await ws.send(json.dumps({
            "id": 4,
            "method": "Runtime.evaluate",
            "params": {
                "expression": "typeof window.DashboardController !== 'undefined'",
                "awaitPromise": False
            }
        }))
        
        resp = await asyncio.wait_for(ws.recv(), timeout=10)
        print(f"DC check: {resp[:200]}")
        
        # Poll until DashboardController is ready
        for attempt in range(30):
            await ws.send(json.dumps({
                "id": 5 + attempt,
                "method": "Runtime.evaluate",
                "params": {
                    "expression": "typeof window.DashboardController !== 'undefined'",
                    "awaitPromise": False
                }
            }))
            resp = await asyncio.wait_for(ws.recv(), timeout=10)
            result = json.loads(resp)
            val = result.get("result", {}).get("result", {}).get("value", False)
            if val:
                print("DashboardController is ready!")
                break
            await asyncio.sleep(1)
        else:
            print("DashboardController not found after 30s")
            return
        
        # Query charts
        charts = [
            ("Last 10 days - New Signs", "chart-e8ns5-c9347"),
            ("Last 10 Days - Order Performance", "dashboard-chart-container-7p18g-b0ef9"),
            ("Last 10 days - Promotion", "chart-iyhbp-a03a1"),
            ("Last 10 days - Operation Performance", "chart-sqalg-1f515"),
            ("Last 10 days - User Experience", "chart-ltuz6-6cbdc"),
            ("CM - Business Performance", "chart-6kwer-1357d"),
        ]
        
        results = {}
        for name, chart_id in charts:
            print(f"\nQuerying: {name}...")
            expr = f'''
                new Promise((resolve) => {{
                    window.DashboardController.executeQueryAndGetCHNResult("{chart_id}")
                        .then(res => resolve({{ok: true, data: res}}))
                        .catch(err => resolve({{ok: false, error: err.message}}));
                }})
            '''
            await ws.send(json.dumps({
                "id": 100,
                "method": "Runtime.evaluate",
                "params": {
                    "expression": expr,
                    "awaitPromise": True,
                    "returnByValue": True,
                    "timeout": 45000
                }
            }))
            
            try:
                resp = await asyncio.wait_for(ws.recv(), timeout=60)
                msg = json.loads(resp)
                result_val = msg.get("result", {}).get("result", {}).get("value", {})
                if result_val.get("ok"):
                    data = result_val["data"]
                    results[name] = data
                    if isinstance(data, dict) and data.get("code") == 0:
                        rows = data.get("data", {}).get("data", [])
                        print(f"  -> OK: {len(rows)} rows")
                    else:
                        print(f"  -> Response: {json.dumps(data, ensure_ascii=False)[:200]}")
                else:
                    err = result_val.get("error", "unknown")
                    print(f"  -> ERROR: {err}")
                    results[name] = {"error": err}
            except asyncio.TimeoutError:
                print(f"  -> TIMEOUT")
                results[name] = {"error": "timeout"}
        
        # Save
        output_path = "/mnt/openclaw/.openclaw/workspace/bi_raw_data.json"
        with open(output_path, "w") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\nData saved to {output_path}")
        
        # Close the page
        await ws.send(json.dumps({"id": 999, "method": "Page.close"}))

asyncio.run(cdp_fetch())
