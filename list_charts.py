import asyncio, json, urllib.request, websockets

async def main():
    info = json.loads(urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=5).read())
    ws_url = info["webSocketDebuggerUrl"]
    
    async with websockets.connect(ws_url) as ws:
        # Get targets
        cmd_id = 1
        await ws.send(json.dumps({"id": cmd_id, "method": "Target.getTargets"}))
        while True:
            raw = await ws.recv()
            resp = json.loads(raw)
            if resp.get("id") == cmd_id:
                targets = resp["result"]["targetInfos"]
                break
        
        bi_target = next((t for t in targets if "300001446" in t["url"]), None)
        if not bi_target:
            print("No BI dashboard tab found!")
            return
        
        target_id = bi_target["targetId"]
        
        # Attach
        cmd_id = 2
        await ws.send(json.dumps({"id": cmd_id, "method": "Target.attachToTarget", "params": {"targetId": target_id, "flatten": True}}))
        while True:
            raw = await ws.recv()
            resp = json.loads(raw)
            if resp.get("id") == cmd_id:
                session_id = resp["result"]["sessionId"]
                break
        
        # Enable runtime
        cmd_id = 3
        await ws.send(json.dumps({"id": cmd_id, "method": "Runtime.enable", "sessionId": session_id}))
        await asyncio.sleep(1)
        
        # Wait for DashboardController
        for i in range(15):
            cmd_id = 10 + i
            await ws.send(json.dumps({
                "id": cmd_id, "method": "Runtime.evaluate", "sessionId": session_id,
                "params": {"expression": "typeof window.DashboardController !== 'undefined'", "returnByValue": True}
            }))
            while True:
                raw = await ws.recv()
                resp = json.loads(raw)
                if resp.get("id") == cmd_id:
                    ready = resp.get("result", {}).get("result", {}).get("value", False)
                    break
            if ready:
                print("DashboardController ready!")
                break
            await asyncio.sleep(1)
        else:
            print("Timeout waiting for DashboardController")
            return
        
        # Get components
        cmd_id = 30
        await ws.send(json.dumps({
            "id": cmd_id, "method": "Runtime.evaluate", "sessionId": session_id,
            "params": {
                "expression": """
                (async () => {
                    const res = await window.DashboardController.getComponents();
                    return JSON.stringify(res);
                })()
                """,
                "returnByValue": True, "awaitPromise": True
            }
        }))
        while True:
            raw = await ws.recv()
            resp = json.loads(raw)
            if resp.get("id") == cmd_id:
                comps_raw = resp.get("result", {}).get("result", {}).get("value", "{}")
                break
        
        comps = json.loads(comps_raw)
        
        # List all charts with their tabs
        charts = []
        for c in comps.get('data', []):
            if c.get('componentType') == 'chart':
                charts.append({
                    'name': c.get('componentName'),
                    'id': c.get('componentId'),
                    'tabId': c.get('tabId'),
                    'tabName': c.get('tabName')
                })
        
        # Group by tab
        tabs = {}
        for c in charts:
            tab = c['tabName'] or 'Unknown'
            if tab not in tabs:
                tabs[tab] = []
            tabs[tab].append(c)
        
        for tab_name, tab_charts in tabs.items():
            print(f"\n=== {tab_name} ({len(tab_charts)} charts) ===")
            for c in tab_charts:
                print(f"  {c['name']} ({c['id'][:20]}...)")

asyncio.run(main())
