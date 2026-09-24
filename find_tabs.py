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
        
        # Find tab elements
        tab_info = await eval_js(ws, session_id, """
        (() => {
            // Try different selectors for tabs
            const selectors = [
                '.tab-nav-item',
                '[class*="tab"]',
                '[role="tab"]',
                '.ant-tabs-tab',
                '.bi-tab',
                '.tab-title',
                '[class*="Tab"]',
            ];
            let result = {};
            for (const sel of selectors) {
                const els = document.querySelectorAll(sel);
                if (els.length > 0) {
                    result[sel] = Array.from(els).map(e => ({
                        text: e.textContent?.trim().substring(0, 50),
                        className: e.className?.substring(0, 100),
                        tag: e.tagName
                    }));
                }
            }
            return JSON.stringify(result);
        })()
        """)
        print("Tab elements found:")
        print(tab_info)
        
        # Also try finding the tab names on the page
        all_text = await eval_js(ws, session_id, """
        (() => {
            // Look for text containing tab names
            const tabNames = ['Business Performance', 'Operating Performance', 'User Experience', 'Promotion', 'New Sign'];
            const results = [];
            for (const name of tabNames) {
                const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null, false);
                let node;
                while (node = walker.nextNode()) {
                    if (node.textContent.includes(name)) {
                        const el = node.parentElement;
                        results.push({
                            name: name,
                            text: node.textContent.trim().substring(0, 100),
                            tag: el.tagName,
                            className: el.className?.substring(0, 100),
                            clickable: el.onclick !== null || el.tagName === 'BUTTON' || el.tagName === 'A' || el.getAttribute('role') === 'tab'
                        });
                        break;
                    }
                }
            }
            return JSON.stringify(results);
        })()
        """)
        print("\nTab text locations:")
        print(all_text)

asyncio.run(main())
