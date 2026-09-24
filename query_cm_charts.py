import asyncio, json, urllib.request, websockets
from datetime import datetime

async def cdp_send(ws, session_id, method, params=None):
    cmd_id = int(datetime.now().timestamp() * 1000) % 100000
    cmd = {"id": cmd_id, "method": method, "params": params or {}}
    if session_id:
        cmd["sessionId"] = session_id
    await ws.send(json.dumps(cmd))
    while True:
        raw = await ws.recv()
        resp = json.loads(raw)
        if resp.get("id") == cmd_id:
            return resp

async def eval_js(ws, session_id, js):
    resp = await cdp_send(ws, session_id, "Runtime.evaluate", {
        "expression": js, "returnByValue": True, "awaitPromise": True
    })
    return resp.get("result", {}).get("result", {}).get("value")

async def main():
    info = json.loads(urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=5).read())
    ws_url = info["webSocketDebuggerUrl"]
    
    async with websockets.connect(ws_url) as ws:
        # Get targets
        resp = await cdp_send(ws, None, "Target.getTargets")
        targets = resp["result"]["targetInfos"]
        bi_target = next((t for t in targets if "300001446" in t["url"]), None)
        if not bi_target:
            print("No BI dashboard tab found!")
            return
        
        target_id = bi_target["targetId"]
        resp = await cdp_send(ws, None, "Target.attachToTarget", {"targetId": target_id, "flatten": True})
        session_id = resp["result"]["sessionId"]
        
        await cdp_send(ws, session_id, "Runtime.enable")
        await asyncio.sleep(1)
        
        # Wait for DashboardController
        for i in range(15):
            ready = await eval_js(ws, session_id, "typeof window.DashboardController !== 'undefined'")
            if ready:
                print("DashboardController ready!")
                break
            await asyncio.sleep(1)
        else:
            print("Timeout waiting for DashboardController")
            return
        
        # Query specific charts by their IDs
        chart_ids = {
            "CM - Operating Merchants": "chart-xu3l7-21399",
            "CM - User Experience": "chart-j9b7t-e9ace",
            "CM - Promotion": "chart-0xw88-29243",
            "BDM - Operating Merchants": "chart-wpm8v-29fb6",
        }
        
        for name, cid in chart_ids.items():
            print(f"\nQuerying: {name} ({cid})")
            try:
                res = await eval_js(ws, session_id, f"""
                (async () => {{
                    const res = await window.DashboardController.executeQueryAndGetCHNResult(['{cid}'], {{force: true}});
                    return JSON.stringify(res);
                }})()
                """)
                data = json.loads(res or '{}')
                rows = len(data.get('data', {}).get('data', [])) if data.get('code') == 0 else 0
                cols = data.get('data', {}).get('columns', [])
                print(f"  -> code={data.get('code')}, rows={rows}, cols={cols}")
                if data.get('code') == 0 and rows > 0:
                    for row in data['data']['data'][:3]:
                        print(f"    {row}")
            except Exception as e:
                print(f"  -> ERROR: {e}")
            await asyncio.sleep(1)

asyncio.run(main())
