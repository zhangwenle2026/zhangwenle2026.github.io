import asyncio, json, urllib.request, websockets, sys

CDP = "http://127.0.0.1:9222"
CTRL = "https://bi.keetapp.com/v2/dashboard/dashboard-controller?dashboardId=300001446"

async def cdp(ws, cmd, session_id=None):
    if session_id:
        cmd["sessionId"] = session_id
    await ws.send(json.dumps(cmd))
    while True:
        r = json.loads(await ws.recv())
        if r.get("id") == cmd.get("id"):
            return r

async def ev(ws, sid, js, timeout=90):
    r = await cdp(ws, {"id": int(asyncio.get_event_loop().time()*1000)%1000000,
                       "method": "Runtime.evaluate",
                       "params": {"expression": js, "returnByValue": True, "awaitPromise": True, "timeout": timeout*1000}},
                  sid)
    res = r.get("result", {}).get("result", {})
    if res.get("subtype") == "error":
        print("JS ERROR:", res.get("description", "")[:400], flush=True)
        return None
    return res.get("value")

async def main():
    info = json.loads(urllib.request.urlopen(f"{CDP}/json/version", timeout=5).read())
    tabs = json.loads(urllib.request.urlopen(f"{CDP}/json", timeout=5).read())
    bi = [t for t in tabs if t['type']=='page' and 'bi.keetapp' in t['url']]
    tid = bi[0]['id']
    print("Using tab", tid[:8], flush=True)
    async with websockets.connect(info["webSocketDebuggerUrl"], max_size=200*1024*1024) as ws:
        resp = await cdp(ws, {"id":1,"method":"Target.attachToTarget","params":{"targetId":tid,"flatten":True}})
        sid = resp["result"]["sessionId"]
        await cdp(ws, {"id":2,"method":"Runtime.enable"}, sid)

        cur = await ev(ws, sid, "location.href")
        if "dashboard-controller" not in cur:
            await cdp(ws, {"id":3,"method":"Page.navigate","params":{"url":CTRL}}, sid)
            await asyncio.sleep(12)

        for i in range(30):
            v = await ev(ws, sid, "typeof window.DashboardController !== 'undefined'")
            if v: break
            await asyncio.sleep(1)
        else:
            print("Controller never mounted", flush=True); return
        print("Controller ready", flush=True)

        comps_raw = await ev(ws, sid, "(async()=>JSON.stringify(await window.DashboardController.getComponents()))()")
        comps = json.loads(comps_raw or '{}')
        chart_map = {c['componentName']: c['componentId'] for c in comps.get('data', []) if c['componentType']=='chart'}
        print("charts:", len(chart_map), flush=True)

        results = {}
        # Priority list: data-dense list charts first
        priority = ["Merchant List", "Merchant List - Operating Merchants", "Performance (BD Level)",
                    "Performance (BDM Level)", "Performance (RM - CM Level)", "Main Metrics",
                    "Sales Funnel", "Yesterday - SMB - Business Performance"]
        order = [n for n in priority if n in chart_map] + [n for n in chart_map if n not in priority]
        for name in order:
            cid = chart_map[name]
            try:
                res = await ev(ws, sid, f'(async()=>JSON.stringify(await window.DashboardController.executeQueryAndGetCHNResult("{cid}")))()', timeout=90)
                if not res:
                    print(f"  {name}: null", flush=True); continue
                d = json.loads(res)
                code = d.get('code')
                rows = d.get('data',{}).get('data',[]) if code==0 else []
                print(f"  {name}: code={code} rows={len(rows)}", flush=True)
                if rows:
                    results[name] = d
                    with open('/mnt/openclaw/.openclaw/workspace/bi_all_charts.json','w') as f:
                        json.dump(results, f, ensure_ascii=False)
            except Exception as e:
                print(f"  {name}: EXC {e}", flush=True)

        print(f"Done. Non-empty: {list(results.keys())}", flush=True)

asyncio.run(main())
