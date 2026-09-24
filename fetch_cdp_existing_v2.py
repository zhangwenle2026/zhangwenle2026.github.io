import asyncio
import json
import websockets

CDP_URL = "http://127.0.0.1:9222"
PAGE_ID = "9A5BB9DCC72BF0893B14918DD67401F3"
WS_URL = f"ws://127.0.0.1:9222/devtools/page/{PAGE_ID}"

async def recv_until_id(ws, target_id, timeout=30):
    """Receive messages until one with matching id is found."""
    while True:
        resp = await asyncio.wait_for(ws.recv(), timeout=timeout)
        msg = json.loads(resp)
        if msg.get("id") == target_id:
            return msg
        # Skip events and unmatched responses

async def cdp_fetch_existing():
    print(f"Connecting to existing BI tab: {PAGE_ID}")
    
    async with websockets.connect(WS_URL) as ws:
        # Enable Page and Runtime
        await ws.send(json.dumps({"id": 1, "method": "Page.enable"}))
        await ws.send(json.dumps({"id": 2, "method": "Runtime.enable"}))
        await recv_until_id(ws, 1)
        await recv_until_id(ws, 2)
        print("Domains enabled")
        
        # Reload page
        print("Reloading page...")
        await ws.send(json.dumps({"id": 3, "method": "Page.reload"}))
        await recv_until_id(ws, 3)
        
        # Wait for load
        print("Waiting for page load...")
        while True:
            msg = await asyncio.wait_for(ws.recv(), timeout=60)
            m = json.loads(msg)
            if m.get("method") == "Page.loadEventFired":
                print("Page loaded!")
                break
            if m.get("id") == 3:
                print("Reload confirmed")
        
        # Wait for DashboardController
        print("Waiting for DashboardController...")
        for attempt in range(60):
            await ws.send(json.dumps({
                "id": 10 + attempt,
                "method": "Runtime.evaluate",
                "params": {
                    "expression": "typeof window.DashboardController !== 'undefined'",
                    "awaitPromise": False
                }
            }))
            msg = await recv_until_id(ws, 10 + attempt, timeout=10)
            val = msg.get("result", {}).get("result", {}).get("value", False)
            if val:
                print("DashboardController is ready!")
                break
            await asyncio.sleep(1)
        else:
            print("DashboardController NOT found after 60s")
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
        for idx, (name, chart_id) in enumerate(charts):
            print(f"\nQuerying: {name} (id={chart_id})...")
            expr = f'''
                new Promise((resolve, reject) => {{
                    try {{
                        window.DashboardController.executeQueryAndGetCHNResult("{chart_id}")
                            .then(res => resolve({{ok: true, data: res}}))
                            .catch(err => resolve({{ok: false, error: err.message || String(err)}}));
                    }} catch (e) {{
                        resolve({{ok: false, error: e.message || String(e)}});
                    }}
                }})
            '''
            req_id = 200 + idx
            await ws.send(json.dumps({
                "id": req_id,
                "method": "Runtime.evaluate",
                "params": {
                    "expression": expr,
                    "awaitPromise": True,
                    "returnByValue": True,
                    "timeout": 60000
                }
            }))
            
            try:
                msg = await recv_until_id(ws, req_id, timeout=90)
                result_val = msg.get("result", {}).get("result", {}).get("value", {})
                
                if isinstance(result_val, dict) and result_val.get("ok"):
                    data = result_val["data"]
                    results[name] = data
                    if isinstance(data, dict) and data.get("code") == 0:
                        rows = data.get("data", {}).get("data", [])
                        print(f"  -> OK: {len(rows)} rows")
                    else:
                        print(f"  -> Response: {json.dumps(data, ensure_ascii=False)[:300]}")
                else:
                    print(f"  -> Result type: {type(result_val)}, value: {str(result_val)[:300]}")
                    results[name] = {"error": str(result_val)}
            except asyncio.TimeoutError:
                print(f"  -> TIMEOUT")
                results[name] = {"error": "timeout"}
        
        # Save
        output_path = "/mnt/openclaw/.openclaw/workspace/bi_raw_data.json"
        with open(output_path, "w") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\nData saved to {output_path}")
        
        # Also save a summary
        summary = {}
        for name, data in results.items():
            if isinstance(data, dict) and data.get("code") == 0:
                rows = data.get("data", {}).get("data", [])
                cols = [c.get("name", c.get("col", "?")) for c in data.get("data", {}).get("schema", [])]
                summary[name] = {
                    "rows": len(rows),
                    "columns": cols,
                    "first_3_rows": rows[:3]
                }
            else:
                summary[name] = {"error": data.get("error", str(data))}
        
        summary_path = "/mnt/openclaw/.openclaw/workspace/bi_raw_data_summary.json"
        with open(summary_path, "w") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"Summary saved to {summary_path}")

asyncio.run(cdp_fetch_existing())
