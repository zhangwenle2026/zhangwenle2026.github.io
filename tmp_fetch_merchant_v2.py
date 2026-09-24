import asyncio, json, urllib.request, websockets, traceback

CDP = "http://127.0.0.1:9222"
OUT = '/mnt/openclaw/.openclaw/workspace/bi_all_charts.json'

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
        print("JS ERROR:", res.get("description", "")[:200], flush=True)
        return None
    return res.get("value")

def load_existing():
    try:
        return json.load(open(OUT))
    except Exception:
        return {}

async def main():
    try:
        existing = load_existing()
        info = json.loads(urllib.request.urlopen(f"{CDP}/json/version", timeout=5).read())
        tabs = json.loads(urllib.request.urlopen(f"{CDP}/json", timeout=5).read())
        bi = [t for t in tabs if t['type']=='page' and 'bi.keetapp' in t['url']]
        tid = bi[0]['id']
        async with websockets.connect(info["webSocketDebuggerUrl"], max_size=200*1024*1024) as ws:
            resp = await cdp(ws, {"id":1,"method":"Target.attachToTarget","params":{"targetId":tid,"flatten":True}})
            sid = resp["result"]["sessionId"]
            comps_raw = await ev(ws, sid, "(async()=>JSON.stringify(await window.DashboardController.getComponents()))()")
            comps = json.loads(comps_raw or '{}')
            chart_map = {c['componentName']: c['componentId'] for c in comps.get('data', []) if c.get('componentType')=='chart'}
            keys = [n for n in chart_map if 'Merchant List' in n or 'Yesterday' in n or 'New Sign' in n or 'Offline' in n]
            got_any = False
            for name in keys:
                cid = chart_map[name]
                res = await ev(ws, sid, f'(async()=>JSON.stringify(await window.DashboardController.executeQueryAndGetCHNResult("{cid}")))()', 90)
                if res:
                    d = json.loads(res)
                    rows = d.get('data',{}).get('data',[]) if d.get('code')==0 else []
                    print(f"{name}: rows={len(rows)}", flush=True)
                    if rows:
                        existing[name] = d
                        got_any = True
                        json.dump(existing, open(OUT,'w'), ensure_ascii=False)
                        print(f"  -> saved {name} ({len(rows)} rows)", flush=True)
            print("DONE got_any=", got_any, flush=True)
    except Exception:
        traceback.print_exc()
        print("FAILED", flush=True)

asyncio.run(main())
