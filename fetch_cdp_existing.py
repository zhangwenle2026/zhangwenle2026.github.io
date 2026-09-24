import asyncio
import json
import websockets
import urllib.request

CDP_HTTP = "http://127.0.0.1:9222"

# Get existing page info
req = urllib.request.Request(f"{CDP_HTTP}/json/list")
with urllib.request.urlopen(req, timeout=10) as resp:
    pages = json.loads(resp.read().decode())

bi_pages = [p for p in pages if "dashboard-controller" in p.get("url", "")]
if not bi_pages:
    print("No BI pages found!")
    exit(1)

page = bi_pages[0]
ws_url = page["webSocketDebuggerUrl"]
print(f"Using page: {page['id']}, title: {page['title']}, url: {page['url'][:80]}")

async def fetch():
    async with websockets.connect(ws_url) as ws:
        # Enable Runtime
        await ws.send(json.dumps({"id": 1, "method": "Runtime.enable"}))
        resp = await asyncio.wait_for(ws.recv(), timeout=10)
        print(f"Runtime enable: {resp[:120]}")
        
        # Check DashboardController
        print("Checking DashboardController...")
        await ws.send(json.dumps({
            "id": 2,
            "method": "Runtime.evaluate",
            "params": {"expression": "typeof window.DashboardController", "awaitPromise": False, "returnByValue": True}
        }))
        resp = await asyncio.wait_for(ws.recv(), timeout=10)
        result = json.loads(resp)
        val = result.get("result", {}).get("result", {}).get("value", "")
        print(f"DashboardController type: {val}")
        if val != "object":
            print("DashboardController not ready. Waiting 5s...")
            await asyncio.sleep(5)
        
        # Query charts via DashboardController
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
            print(f"\nQuerying: {name} ({chart_id})...")
            expr = f'''
                new Promise((resolve) => {{
                    window.DashboardController.executeQueryAndGetCHNResult("{chart_id}")
                        .then(res => resolve({{ok: true, data: res}}))
                        .catch(err => resolve({{ok: false, error: String(err)}}));
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
                    if isinstance(data, dict):
                        if data.get("code") == 0:
                            rows = data.get("data", {}).get("data", [])
                            print(f"  -> OK: {len(rows)} rows")
                        else:
                            print(f"  -> code={data.get('code')}, msg={data.get('message', 'N/A')[:100]}")
                    else:
                        print(f"  -> type={type(data).__name__}, val={str(data)[:100]}")
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
        print(f"\nSaved to {output_path}")
        
        for name, data in results.items():
            status = "OK" if (isinstance(data, dict) and data.get("code") == 0) else "ERR"
            print(f"  {status}: {name}")

asyncio.run(fetch())
