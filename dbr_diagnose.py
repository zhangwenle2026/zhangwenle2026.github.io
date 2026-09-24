#!/usr/bin/env python3
import asyncio, json, websockets, datetime, sys, http.client

brt_now = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=3)
brt_yesterday = (brt_now - datetime.timedelta(days=1)).strftime("%Y%m%d")
print(f"BRT yesterday: {brt_yesterday}")

conn = http.client.HTTPConnection("localhost", 9222)
conn.request("GET", "/json/list")
tabs = json.loads(conn.getresponse().read())
bi_tab = next((t for t in tabs if 'bi.keetapp' in t.get('url','')), None)
if not bi_tab:
    print("No BI tab"); sys.exit(1)
PAGE_WS = bi_tab['webSocketDebuggerUrl']
print(f"BI tab: {bi_tab['url']}")

async def main():
    async with websockets.connect(PAGE_WS) as ws:
        print("Connected")
        await ws.send(json.dumps({"id":1, "method":"Runtime.enable"}))
        await asyncio.sleep(1)
        for _ in range(10):
            try: await asyncio.wait_for(ws.recv(), timeout=1)
            except asyncio.TimeoutError: break

        # Check page title
        await ws.send(json.dumps({"id":10, "method":"Runtime.evaluate", "params":{"expression":"document.title","returnByValue":True}}))
        deadline = asyncio.get_event_loop().time() + 10
        while asyncio.get_event_loop().time() < deadline:
            try:
                r = await asyncio.wait_for(ws.recv(), timeout=1)
                msg = json.loads(r)
                if msg.get("id") == 10:
                    title = msg.get("result",{}).get("result",{}).get("value","")
                    print(f"Title: {title}")
                    break
            except asyncio.TimeoutError: break

        # Check page body
        await ws.send(json.dumps({"id":11, "method":"Runtime.evaluate", "params":{"expression":"document.body?.innerText?.substring(0, 800)","returnByValue":True}}))
        deadline = asyncio.get_event_loop().time() + 10
        while asyncio.get_event_loop().time() < deadline:
            try:
                r = await asyncio.wait_for(ws.recv(), timeout=1)
                msg = json.loads(r)
                if msg.get("id") == 11:
                    text = msg.get("result",{}).get("result",{}).get("value","")
                    print(f"Body text:\n{text}")
                    break
            except asyncio.TimeoutError: break

        # DashboardController state
        await ws.send(json.dumps({"id":12, "method":"Runtime.evaluate", "params":{"expression":"typeof window.DashboardController","returnByValue":True}}))
        deadline = asyncio.get_event_loop().time() + 10
        while asyncio.get_event_loop().time() < deadline:
            try:
                r = await asyncio.wait_for(ws.recv(), timeout=1)
                msg = json.loads(r)
                if msg.get("id") == 12:
                    dc = msg.get("result",{}).get("result",{}).get("value","")
                    print(f"DashboardController: {dc}")
                    break
            except asyncio.TimeoutError: break

        # Get filter values
        await ws.send(json.dumps({"id":13, "method":"Runtime.evaluate", "params":{"expression":"""new Promise((resolve) => {
            try { window.DashboardController.getFilterValues()
                .then(res => resolve(JSON.stringify(res)))
                .catch(err => resolve("ERROR:"+err.message));
            } catch(e) { resolve("EXCEPTION:"+e.message); }
        })""","awaitPromise":True,"returnByValue":True}}))
        deadline = asyncio.get_event_loop().time() + 20
        while asyncio.get_event_loop().time() < deadline:
            try:
                r = await asyncio.wait_for(ws.recv(), timeout=1)
                msg = json.loads(r)
                if msg.get("id") == 13:
                    val = msg.get("result",{}).get("result",{}).get("value","")
                    print(f"Filter values: {val[:500]}")
                    break
            except asyncio.TimeoutError: break

        # Query chart
        await ws.send(json.dumps({"id":14, "method":"Runtime.evaluate", "params":{"expression":"""new Promise((resolve) => {
            try { window.DashboardController.executeQueryAndGetCHNResult(["chart-6kwer-1357d"])
                .then(res => resolve(JSON.stringify(res)))
                .catch(err => resolve("ERROR:"+err.message));
            } catch(e) { resolve("EXCEPTION:"+e.message); }
        })""","awaitPromise":True,"returnByValue":True}}))
        deadline = asyncio.get_event_loop().time() + 30
        while asyncio.get_event_loop().time() < deadline:
            try:
                r = await asyncio.wait_for(ws.recv(), timeout=1)
                msg = json.loads(r)
                if msg.get("id") == 14:
                    val = msg.get("result",{}).get("result",{}).get("value","")
                    print(f"Chart query: {val[:800]}")
                    break
            except asyncio.TimeoutError: break

        # Get page HTML structure
        await ws.send(json.dumps({"id":15, "method":"Runtime.evaluate", "params":{"expression":"document.querySelector('.dashboard-container, .dashboard-content, [class*=dashboard]')?.innerHTML?.substring(0, 500)","returnByValue":True}}))
        deadline = asyncio.get_event_loop().time() + 10
        while asyncio.get_event_loop().time() < deadline:
            try:
                r = await asyncio.wait_for(ws.recv(), timeout=1)
                msg = json.loads(r)
                if msg.get("id") == 15:
                    val = msg.get("result",{}).get("result",{}).get("value","")
                    print(f"Dashboard container: {val[:500]}")
                    break
            except asyncio.TimeoutError: break

result = asyncio.run(main())
