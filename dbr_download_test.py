import asyncio, json, websockets
import subprocess

r = subprocess.run(["curl","-s","http://localhost:9222/json/list"], capture_output=True, text=True)
tabs = json.loads(r.stdout)
PAGE_WS = None
for t in tabs:
    if "bi.keetapp" in t.get("url", ""):
        PAGE_WS = t.get("webSocketDebuggerUrl")
        break

if not PAGE_WS:
    print("No BI tab")
    exit(1)

async def send_cmd(ws, cid, method, params=None):
    msg = {"id": cid, "method": method}
    if params: msg["params"] = params
    await ws.send(json.dumps(msg))

async def recv_until(ws, cid, to=60):
    d = asyncio.get_event_loop().time() + to
    while asyncio.get_event_loop().time() < d:
        try:
            r = await asyncio.wait_for(ws.recv(), timeout=d-asyncio.get_event_loop().time())
            m = json.loads(r)
            if m.get("id") == cid:
                return m
        except asyncio.TimeoutError:
            break
    return None

async def main():
    async with websockets.connect(PAGE_WS) as ws:
        await send_cmd(ws, 1, "Runtime.enable")
        for _ in range(5):
            try: await asyncio.wait_for(ws.recv(), timeout=1)
            except: break
        
        # First, get components to find chart IDs
        await send_cmd(ws, 10, "Runtime.evaluate", {
            "expression": "window.DashboardController.getComponents().then(res => JSON.stringify(res))",
            "awaitPromise": True, "returnByValue": True, "timeout": 30000
        })
        resp = await recv_until(ws, 10, 40)
        val = resp.get("result",{}).get("result",{}).get("value","") if resp else ""
        try:
            comps = json.loads(val)
            print("Components:", json.dumps(comps, ensure_ascii=False, indent=2)[:2000])
        except:
            print("Failed to parse components:", val[:500])
            return
        
        # Find chart components
        charts = []
        if isinstance(comps, dict) and comps.get("code") == 0:
            for c in comps.get("data", []):
                if c.get("componentType") == "chart":
                    charts.append((c.get("componentName"), c.get("componentId")))
        print(f"\nFound {len(charts)} charts:")
        for name, cid in charts:
            print(f"  {name} -> {cid}")
        
        # Try executeDownload for each chart
        cmd_id = 100
        for name, cid in charts[:3]:  # test first 3
            print(f"\n--- Testing download for {name} ({cid}) ---")
            
            # First trigger query
            await send_cmd(ws, cmd_id, "Runtime.evaluate", {
                "expression": f'''window.DashboardController.executeQueryAndGetCHNResult("{cid}").then(res => JSON.stringify(res))''',
                "awaitPromise": True, "returnByValue": True, "timeout": 60000
            })
            resp = await recv_until(ws, cmd_id, 70)
            cmd_id += 1
            val = resp.get("result",{}).get("result",{}).get("value","") if resp else ""
            try:
                qres = json.loads(val)
                rows = len(qres.get("data",{}).get("data",[])) if isinstance(qres, dict) else 0
                print(f"  Query result: code={qres.get('code') if isinstance(qres,dict) else 'N/A'}, rows={rows}")
            except:
                print(f"  Query result parse error: {val[:200]}")
            
            await asyncio.sleep(2)
            
            # Then try download
            await send_cmd(ws, cmd_id, "Runtime.evaluate", {
                "expression": f'''window.DashboardController.executeDownload("{cid}").then(res => JSON.stringify(res))''',
                "awaitPromise": True, "returnByValue": True, "timeout": 60000
            })
            resp = await recv_until(ws, cmd_id, 70)
            cmd_id += 1
            val = resp.get("result",{}).get("result",{}).get("value","") if resp else ""
            try:
                dres = json.loads(val)
                print(f"  Download result: code={dres.get('code') if isinstance(dres,dict) else 'N/A'}")
                if isinstance(dres, dict) and dres.get("code") == 0:
                    data = dres.get("data", {})
                    print(f"    data keys: {list(data.keys())}")
                    if "fileUrl" in data:
                        print(f"    fileUrl: {data['fileUrl'][:200]}")
                    if "wenshuUrl" in data:
                        print(f"    wenshuUrl: {data['wenshuUrl'][:200]}")
            except:
                print(f"  Download result parse error: {val[:500]}")
            
            await asyncio.sleep(2)

asyncio.run(main())
