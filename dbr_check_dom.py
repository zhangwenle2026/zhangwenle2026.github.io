import asyncio, json, websockets
import subprocess

r = subprocess.run(["curl","-s","http://localhost:9222/json/list"], capture_output=True, text=True)
tabs = json.loads(r.stdout)
PAGE_WS = None
for t in tabs:
    if "bi.keetapp" in t.get("url", ""):
        PAGE_WS = t.get("webSocketDebuggerUrl")
        break

async def send_cmd(ws, cid, method, params=None):
    msg = {"id": cid, "method": method}
    if params: msg["params"] = params
    await ws.send(json.dumps(msg))

async def recv_until(ws, cid, to=10):
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
        await send_cmd(ws,1,"Runtime.enable")
        for _ in range(5):
            try: await asyncio.wait_for(ws.recv(), timeout=1)
            except: break
        await asyncio.sleep(3)
        exprs = [
            "(document.querySelectorAll('table').length)",
            "(document.querySelectorAll('.ant-table-body table, .ant-table-content table').length)",
            "(document.querySelectorAll('[class*=\"pivot\"], [class*=\"cross-table\"]').length)",
            "(document.querySelectorAll('.antv-s2-container canvas').length)",
            "(document.querySelectorAll('.mtbi-cell, .data-cell').length)",
        ]
        for i, e in enumerate(exprs):
            await send_cmd(ws, 100+i, "Runtime.evaluate", {"expression": e, "returnByValue": True})
            resp = await recv_until(ws, 100+i, 10)
            val = resp.get("result",{}).get("result",{}).get("value", "N/A") if resp else "N/A"
            print(f"{e}: {val}")
        
        expr = """
        (function(){
            var t = document.querySelector('table');
            if (!t) return 'no table';
            return t.innerText.substring(0, 300);
        })()
        """
        await send_cmd(ws, 200, "Runtime.evaluate", {"expression": expr, "returnByValue": True})
        resp = await recv_until(ws, 200, 10)
        val = resp.get("result",{}).get("result",{}).get("value", "N/A") if resp else "N/A"
        print(f"First table text: {val}")

asyncio.run(main())
