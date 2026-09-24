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
                out = "/mnt/openclaw/.openclaw/workspace/dbr_screenshot_check.png"
                with open(out, "wb") as f:
                    f.write(base64.b64decode(data))
                print(f"Screenshot saved: {out}")
                
        # Check date indicators
        await send_cmd(ws, 101, "Runtime.evaluate", {
            "expression": """
                (function(){
                    var els = document.querySelectorAll('[class*="date"], [class*="time"], .ant-picker-input input, [class*="range"]');
                    var texts = [];
                    for(var i=0;i<els.length;i++){
                        var t = els[i].textContent || els[i].value || '';
                        if(t && t.length > 4) texts.push(t.trim());
                    }
                    return texts.slice(0,10);
                })()
            """,
            "returnByValue": True
        })
        resp = await recv_until(ws, 101, timeout=10)
        date_texts = resp.get("result",{}).get("result",{}).get("value",[]) if resp else []
        print(f"Date indicators: {date_texts}")
        
        # Check loading status
        await send_cmd(ws, 102, "Runtime.evaluate", {
            "expression": """
                (function(){
                    var spinners = document.querySelectorAll('.ant-spin-dot, .loading, .ant-skeleton');
                    return 'spinners=' + spinners.length;
                })()
            """,
            "returnByValue": True
        })
        resp = await recv_until(ws, 102, timeout=10)
        loading = resp.get("result",{}).get("result",{}).get("value","") if resp else ""
        print(f"Loading: {loading}")

asyncio.run(main())
