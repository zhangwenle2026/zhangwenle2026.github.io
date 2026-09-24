import asyncio, json, urllib.request, websockets

async def cdp(ws, cmd):
    await ws.send(json.dumps(cmd))
    while True:
        r = json.loads(await ws.recv())
        if r.get("id") == cmd.get("id"):
            return r

JS = """
(() => {
  const keys = Object.keys(window).filter(k => /dashboard|Dashboard|controller|Controller|chart/i.test(k));
  return JSON.stringify({globals: keys.slice(0,50)});
})()
"""

async def main():
    info = json.loads(urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=5).read())
    tabs = json.loads(urllib.request.urlopen("http://127.0.0.1:9222/json", timeout=5).read())
    bi = [t for t in tabs if t['type']=='page' and 'bi.keetapp' in t['url']]
    t = bi[0]
    async with websockets.connect(info["webSocketDebuggerUrl"], max_size=50*1024*1024) as ws:
        resp = await cdp(ws, {"id":1,"method":"Target.attachToTarget","params":{"targetId":t['id'],"flatten":True}})
        sid = resp.get("result",{}).get("sessionId")
        r = await cdp(ws, {"id":2,"method":"Runtime.evaluate","params":{"expression":JS,"returnByValue":True},"sessionId":sid})
        print(r.get("result",{}).get("result",{}).get("value"))

asyncio.run(main())
