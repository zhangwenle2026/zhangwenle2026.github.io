#!/usr/bin/env python3
"""DBR fallback: screenshot BI dashboard tabs via CDP."""
import asyncio
import json
import websockets
import base64
import os

PAGE_WS = "ws://localhost:9222/devtools/page/30B89CE186B7DF4D7EB7A5EDBC8C0412"
OUTPUT_DIR = "/mnt/openclaw/.openclaw/workspace"

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

async def capture_screenshot(ws, filename):
    cmd_id = 9000
    await send_cmd(ws, cmd_id, "Page.captureScreenshot", {"format": "png"})
    resp = await recv_until(ws, cmd_id, timeout=20)
    if resp and "result" in resp:
        data = resp["result"].get("data", "")
        if data:
            path = os.path.join(OUTPUT_DIR, filename)
            with open(path, "wb") as f:
                f.write(base64.b64decode(data))
            print(f"Screenshot saved: {path}")
            return path
    print(f"Screenshot failed for {filename}")
    return None

async def eval_js(ws, expr, cmd_id=8000):
    await send_cmd(ws, cmd_id, "Runtime.evaluate", {
        "expression": expr,
        "returnByValue": True,
        "awaitPromise": True
    })
    resp = await recv_until(ws, cmd_id, timeout=15)
    if resp and "result" in resp:
        val = resp["result"].get("result", {}).get("value")
        return val
    return None

async def main():
    async with websockets.connect(PAGE_WS) as ws:
        print("Connected to BI tab")
        await send_cmd(ws, 1, "Runtime.enable")
        await send_cmd(ws, 2, "Page.enable")
        for _ in range(5):
            try:
                await asyncio.wait_for(ws.recv(), timeout=1)
            except asyncio.TimeoutError:
                break

        # Screenshot current tab
        await capture_screenshot(ws, "dbr_fallback_tab1.png")

        tab_texts = ["Business Performance", "New Signs", "Operation Performance", "Promotion", "User Experience"]
        for idx, text in enumerate(tab_texts):
            js = (
                "new Promise((resolve) => {"
                "  const tabs = Array.from(document.querySelectorAll('.ant-tabs-tab, [role=\\\"tab\\\"], .tab-item'));"
                "  const tab = tabs.find(t => (t.innerText && t.innerText.includes('" + text + "')) || (t.textContent && t.textContent.includes('" + text + "')));"
                "  if (tab) {"
                "    tab.click();"
                "    setTimeout(() => resolve('clicked " + text + "'), 4000);"
                "  } else {"
                "    resolve('not found " + text + "');"
                "  }"
                "})"
            )
            res = await eval_js(ws, js, cmd_id=500 + idx)
            print(f"Tab '{text}': {res}")
            if res and 'clicked' in str(res):
                await asyncio.sleep(4)
                await capture_screenshot(ws, f"dbr_fallback_{text.replace(' ', '_').lower()}.png")

        # Try generic ant-tabs-tab switching for any remaining tabs
        for attempt in range(5):
            js = (
                "new Promise((resolve) => {"
                "  const el = document.querySelectorAll('.ant-tabs-tab')[" + str(attempt) + "];"
                "  if (el) { el.click(); setTimeout(() => resolve('clicked " + str(attempt) + "'), 4000); }"
                "  else { resolve('no tab " + str(attempt) + "'); }"
                "})"
            )
            res = await eval_js(ws, js, cmd_id=600 + attempt)
            print(f"Generic tab {attempt}: {res}")
            if res and 'clicked' in str(res):
                await asyncio.sleep(4)
                await capture_screenshot(ws, f"dbr_fallback_generic_{attempt}.png")

if __name__ == "__main__":
    asyncio.run(main())
