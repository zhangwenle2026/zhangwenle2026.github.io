import asyncio, json, websockets, base64

PAGE_WS = "ws://localhost:9222/devtools/page/30B89CE186B7DF4D7EB7A5EDBC8C0412"

async def send_cmd(ws, cmd_id, method, params=None):
    msg = {"id": cmd_id, "method": method}
    if params:
        msg["params"] = params
    await ws.send(json.dumps(msg))
    return msg["id"]

async def recv_until(ws, cmd_id, timeout=30):
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        try:
            r = await asyncio.wait_for(ws.recv(), timeout=deadline - asyncio.get_event_loop().time())
            msg = json.loads(r)
            if msg.get("id") == cmd_id:
                return msg
        except asyncio.TimeoutError:
            break
    return None

async def main():
    async with websockets.connect(PAGE_WS) as ws:
        print("Connected")
        await send_cmd(ws, 1, "Runtime.enable")
        await send_cmd(ws, 2, "Page.enable")
        for _ in range(5):
            try:
                await asyncio.wait_for(ws.recv(), timeout=1)
            except asyncio.TimeoutError:
                break
        
        # Screenshot
        await send_cmd(ws, 100, "Page.captureScreenshot", {"format": "png", "fromSurface": True})
        resp = await recv_until(ws, 100, timeout=30)
        if resp:
            data = resp.get("result",{}).get("data","")
            if data:
                out = "/mnt/openclaw/.openclaw/workspace/dbr_screenshot_debug.png"
                with open(out, "wb") as f:
                    f.write(base64.b64decode(data))
                print(f"Screenshot saved: {out}")
        
        # Check body text
        await send_cmd(ws, 101, "Runtime.evaluate", {
            "expression": "document.body.innerText.substring(0,800)",
            "returnByValue": True
        })
        resp = await recv_until(ws, 101, timeout=10)
        text = resp.get("result",{}).get("result",{}).get("value","") if resp else ""
        print(f"Body text: {text[:500]}")
        
        # Check for errors
        await send_cmd(ws, 102, "Runtime.evaluate", {
            "expression": """
                (function(){
                    var errs = document.querySelectorAll('.ant-result-title, .ant-alert-message, [class*="error"], [class*="Error"]');
                    return Array.from(errs).map(e=>e.textContent).slice(0,5);
                })()
            """,
            "returnByValue": True
        })
        resp = await recv_until(ws, 102, timeout=10)
        errs = resp.get("result",{}).get("result",{}).get("value",[]) if resp else []
        print(f"Errors: {errs}")
        
        # Check console for errors
        await send_cmd(ws, 103, "Runtime.evaluate", {
            "expression": """
                (function(){
                    var msgs = [];
                    var origErr = console.error;
                    return "check console manually";
                })()
            """,
            "returnByValue": True
        })

asyncio.run(main())
