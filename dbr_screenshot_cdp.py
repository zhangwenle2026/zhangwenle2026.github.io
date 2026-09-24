import asyncio, json, websockets, base64, os
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

async def recv_until(ws, cid, to=30):
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
        
        # Wait for page to fully load
        await asyncio.sleep(5)
        
        # Take screenshot
        await send_cmd(ws, 10, "Page.captureScreenshot", {"format": "png", "fullPage": True})
        resp = await recv_until(ws, 10, 30)
        data = resp.get("result", {}).get("data", "") if resp else ""
        if data:
            out = "/mnt/openclaw/.openclaw/workspace/dbr_screenshot_20260908.png"
            with open(out, "wb") as f:
                f.write(base64.b64decode(data))
            print(f"Screenshot saved: {out}")
        else:
            print("No screenshot data")

asyncio.run(main())
