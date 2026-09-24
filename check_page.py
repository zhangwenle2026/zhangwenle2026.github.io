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
        
        # Check the actual page structure
        info = await eval_js(ws, session_id, """
        (() => {
            return JSON.stringify({
                url: window.location.href,
                title: document.title,
                bodyText: document.body.innerText.substring(0, 500),
                hasIframe: document.querySelector('iframe') !== null,
                iframeCount: document.querySelectorAll('iframe').length
            });
        })()
        """)
        print("Page info:")
        print(info)
        
        # Check if there's an iframe with the dashboard
        iframe_info = await eval_js(ws, session_id, """
        (() => {
            const iframes = document.querySelectorAll('iframe');
            return JSON.stringify(Array.from(iframes).map(f => ({
                src: f.src?.substring(0, 200),
                id: f.id,
                name: f.name
            })));
        })()
        """)
        print("\nIframes:")
        print(iframe_info)

asyncio.run(main())
