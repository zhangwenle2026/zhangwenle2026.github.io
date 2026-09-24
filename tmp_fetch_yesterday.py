import asyncio, json, urllib.request, websockets

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

async def ev(ws, sid, js, timeout=120):
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

        # tempData keys
        td = await ev(ws, sid, """
        (() => {
          const s = window.DashboardController.engine.store;
          const td = s.tempData || (s.state && s.state.tempData);
          return JSON.stringify({type: typeof td, keys: td ? Object.keys(td) : null});
        })()
        """)
        print("tempData:", td, flush=True)

        # Look inside tempData for filter/query payloads
        probe = await ev(ws, sid, """
        (() => {
          const s = window.DashboardController.engine.store;
          const td = s.tempData || (s.state && s.state.tempData);
          const out = {};
          if (td && typeof td === 'object') {
            for (const k of Object.keys(td)) {
              try {
                const seen = new WeakSet();
                const j = JSON.stringify(td[k], (key, val) => {
                  if (typeof val === 'object' && val !== null) {
                    if (seen.has(val)) return '[circular]';
                    seen.add(val);
                  }
                  return val;
                });
                out[k] = j.slice(0, 400);
              } catch(e) { out[k] = 'ERR'; }
            }
          }
          return JSON.stringify(out);
        })()
        """, timeout=60)
        print("tempData contents:", (probe or '')[:3000], flush=True)

asyncio.run(main())
