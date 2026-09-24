import asyncio, json, urllib.request, websockets

CDP = "http://127.0.0.1:9222"
CTRL = "https://bi.keetapp.com/v2/dashboard/dashboard-controller?dashboardId=300001446"
OUT = "/mnt/openclaw/.openclaw/workspace/bi_all_charts.json"

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
        print("JS ERROR:", res.get("description", "")[:300], flush=True)
        return None
    return res.get("value")

CLICK_TAB = """
(() => {
  const tabs = document.querySelectorAll('.tab-nav-item');
  for (const t of tabs) {
    const title = t.querySelector('.tab-title')?.textContent?.trim();
    if (title === '__TAB__') { t.click(); return 'clicked'; }
  }
  return 'not found: ' + Array.from(tabs).map(t=>t.textContent.trim().slice(0,20)).join('|');
})()
"""

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
        tab_list = [c['componentName'] for c in comps.get('data', []) if c['componentType']=='tab']
        print("tabs:", tab_list, flush=True)

        results = {}
        try:
            results = json.load(open(OUT))
        except Exception:
            pass

        # Tab-name guesses for trend charts
        plan = [
            ("Business Performance", ["Last 10 Days - Order Performance", "Last 10 days - New Signs", "Last 10 days - Promotion", "CM - Business Performance"]),
            ("Operating Performance", ["Last 10 days - Operation Performance"]),
            ("User Experience", ["Last 10 days - User Experience"]),
            ("Overall Business Metrics", ["Main Metrics", "Sales Funnel", "Yesterday - SMB - Business Performance"]),
        ]
        for tab_name, charts in plan:
            click = await ev(ws, sid, CLICK_TAB.replace('__TAB__', tab_name))
            print(f"[tab {tab_name}] {click}", flush=True)
            if 'not found' in str(click):
                continue
            await asyncio.sleep(3)
            for name in charts:
                cid = chart_map.get(name)
                if not cid:
                    continue
                res = await ev(ws, sid, f'(async()=>JSON.stringify(await window.DashboardController.executeQueryAndGetCHNResult("{cid}")))()', timeout=90)
                if not res:
                    print(f"  {name}: null", flush=True)
                    continue
                d = json.loads(res)
                rows = d.get('data',{}).get('data',[]) if d.get('code')==0 else []
                print(f"  {name}: rows={len(rows)}", flush=True)
                if rows:
                    results[name] = d
                    with open(OUT,'w') as f:
                        json.dump(results, f, ensure_ascii=False)

        print("Final:", list(results.keys()), flush=True)

asyncio.run(main())
