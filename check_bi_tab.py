#!/usr/bin/env python3
import asyncio, json, urllib.request, websockets
from datetime import datetime

CMD_ID = 0
async def cdp(ws, sid, method, params=None):
    global CMD_ID
    CMD_ID += 1
    cmd = {"id": CMD_ID, "method": method, "params": params or {}}
    if sid: cmd["sessionId"] = sid
    await ws.send(json.dumps(cmd))
    while True:
        r = json.loads(await ws.recv())
        if r.get("id") == CMD_ID:
            return r

async def main():
    info = json.loads(urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=5).read())
    async with websockets.connect(info["webSocketDebuggerUrl"], max_size=50*1024*1024) as ws:
        resp = await cdp(ws, None, "Target.getTargets")
        tid = next(t["targetId"] for t in resp["result"]["targetInfos"] if "bi.keetapp" in t.get("url",""))
        resp = await cdp(ws, None, "Target.attachToTarget", {"targetId": tid, "flatten": True})
        sid = resp["result"]["sessionId"]
        await cdp(ws, sid, "Runtime.enable")
        js = ("JSON.stringify({url: location.href, ready: typeof window.DashboardController, "
              "title: document.title, hasLogin: !!document.querySelector('input[type=password]'), "
              "bodyLen: document.body ? document.body.innerText.length : 0, "
              "snippet: document.body ? document.body.innerText.slice(0,300) : ''})")
        r = await cdp(ws, sid, "Runtime.evaluate", {"expression": js, "returnByValue": True})
        print(r.get("result",{}).get("result",{}).get("value"))

asyncio.run(main())
