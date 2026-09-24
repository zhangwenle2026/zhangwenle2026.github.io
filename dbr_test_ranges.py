#!/usr/bin/env python3
import asyncio, json, websockets, datetime, http.client

brt_now = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=3)
brt_yesterday = (brt_now - datetime.timedelta(days=1)).strftime("%Y%m%d")

conn = http.client.HTTPConnection("localhost", 9222)
conn.request("GET", "/json/list")
tabs = json.loads(conn.getresponse().read())
bi_tab = next((t for t in tabs if 'bi.keetapp' in t.get('url','')), None)
PAGE_WS = bi_tab['webSocketDebuggerUrl']

async def main():
    async with websockets.connect(PAGE_WS) as ws:
        await ws.send(json.dumps({"id":1, "method":"Runtime.enable"}))
        await ws.send(json.dumps({"id":2, "method":"Network.enable"}))
        await asyncio.sleep(1)
        for _ in range(10):
            try: await asyncio.wait_for(ws.recv(), timeout=1)
            except asyncio.TimeoutError: break

        # Get filters
        expr = """new Promise((resolve) => {
            try { window.DashboardController.getFiltersInfo()
                .then(res => resolve(JSON.stringify(res)))
                .catch(err => resolve("ERROR:"+err.message));
            } catch(e) { resolve("EX:"+e.message); }
        })"""
        await ws.send(json.dumps({"id":10, "method":"Runtime.evaluate", "params":{"expression":expr,"awaitPromise":True,"returnByValue":True}}))
        deadline = asyncio.get_event_loop().time() + 30
        while asyncio.get_event_loop().time() < deadline:
            try:
                r = await asyncio.wait_for(ws.recv(), timeout=1)
                msg = json.loads(r)
                if msg.get("id") == 10:
                    val = msg.get("result",{}).get("result",{}).get("value","")
                    data = json.loads(val)
                    filters = data.get("data",[])
                    date_filters = [f for f in filters if f.get("filterType") == "time"]
                    print(f"Date filters: {len(date_filters)}")
                    for df in date_filters:
                        print(f"  {df.get('name')} = {df.get('key')}")
                    break
            except asyncio.TimeoutError: break

        # Try multiple approaches for date filter
        # Approach: last 10 days (offset -10 to -1)
        for label, start_off, end_off in [("last 7 days", -7, -1), ("last 14 days", -14, -1), ("last 30 days", -30, -1)]:
            filter_settings = []
            for df in date_filters:
                filter_settings.append({
                    "id": df.get("key"),
                    "userInput": {
                        "value": [
                            {"offset": start_off, "granularity": "DAY", "type": "OFFSET"},
                            {"offset": end_off, "granularity": "DAY", "type": "OFFSET"}
                        ],
                        "granularity": "DAY"
                    }
                })
            expr = f"""new Promise((resolve) => {{
                try {{ window.DashboardController.setFiltersValues({json.dumps(filter_settings)})
                    .then(r => resolve(JSON.stringify(r)))
                    .catch(e => resolve("ERR:"+e.message));
                }} catch(ex) {{ resolve("EX:"+ex.message); }}
            }})"""
            await ws.send(json.dumps({"id":20, "method":"Runtime.evaluate", "params":{"expression":expr,"awaitPromise":True,"returnByValue":True}}))
            deadline = asyncio.get_event_loop().time() + 30
            while asyncio.get_event_loop().time() < deadline:
                try:
                    r = await asyncio.wait_for(ws.recv(), timeout=1)
                    msg = json.loads(r)
                    if msg.get("id") == 20:
                        val = msg.get("result",{}).get("result",{}).get("value","")
                        resp = json.loads(val)
                        print(f"\nFilter set ({label}): code={resp.get('code')} msg={resp.get('message','')}")
                        break
                except asyncio.TimeoutError: break

            await asyncio.sleep(25)

            # Query Business Performance chart
            expr = """new Promise((resolve) => {
                try { window.DashboardController.executeQueryAndGetCHNResult(["chart-6kwer-1357d"])
                    .then(r => resolve(JSON.stringify(r)))
                    .catch(e => resolve("ERR:"+e.message));
                } catch(ex) { resolve("EX:"+ex.message); }
            })"""
            await ws.send(json.dumps({"id":30, "method":"Runtime.evaluate", "params":{"expression":expr,"awaitPromise":True,"returnByValue":True}}))
            deadline = asyncio.get_event_loop().time() + 60
            while asyncio.get_event_loop().time() < deadline:
                try:
                    r = await asyncio.wait_for(ws.recv(), timeout=1)
                    msg = json.loads(r)
                    if msg.get("id") == 30:
                        val = msg.get("result",{}).get("result",{}).get("value","")
                        resp = json.loads(val) if val else {}
                        code = resp.get("code")
                        data = resp.get("data", {})
                        if isinstance(data, dict):
                            rows = data.get("data", [])
                            cols = data.get("columns", [])
                            print(f"  BP: code={code} rows={len(rows)} cols={len(cols)}")
                            if rows: print(f"  First row: {str(rows[0])[:120]}")
                            elif cols: print(f"  Cols: {cols[:5]}")
                        break
                except asyncio.TimeoutError: break

            # Also try New Signs
            expr = """new Promise((resolve) => {
                try { window.DashboardController.executeQueryAndGetCHNResult(["chart-e8ns5-c9347"])
                    .then(r => resolve(JSON.stringify(r)))
                    .catch(e => resolve("ERR:"+e.message));
                } catch(ex) { resolve("EX:"+ex.message); }
            })"""
            await ws.send(json.dumps({"id":31, "method":"Runtime.evaluate", "params":{"expression":expr,"awaitPromise":True,"returnByValue":True}}))
            deadline = asyncio.get_event_loop().time() + 60
            while asyncio.get_event_loop().time() < deadline:
                try:
                    r = await asyncio.wait_for(ws.recv(), timeout=1)
                    msg = json.loads(r)
                    if msg.get("id") == 31:
                        val = msg.get("result",{}).get("result",{}).get("value","")
                        resp = json.loads(val) if val else {}
                        code = resp.get("code")
                        data = resp.get("data", {})
                        if isinstance(data, dict):
                            rows = data.get("data", [])
                            cols = data.get("columns", [])
                            print(f"  NS: code={code} rows={len(rows)} cols={len(cols)}")
                            if rows: print(f"  First row: {str(rows[0])[:120]}")
                            elif cols: print(f"  Cols: {cols[:5]}")
                        break
                except asyncio.TimeoutError: break

            await asyncio.sleep(3)

result = asyncio.run(main())