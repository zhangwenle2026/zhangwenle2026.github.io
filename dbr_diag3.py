#!/usr/bin/env python3
import asyncio, json, websockets, datetime, sys, http.client

brt_now = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=3)
brt_yesterday = (brt_now - datetime.timedelta(days=1)).strftime("%Y%m%d")
DATA_DATE = brt_yesterday

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
        filter_expr = """new Promise((resolve) => {
            try { window.DashboardController.getFiltersInfo()
                .then(res => resolve(JSON.stringify(res)))
                .catch(err => resolve("ERROR:"+err.message));
            } catch(e) { resolve("EX:"+e.message); }
        })"""
        await ws.send(json.dumps({"id":10, "method":"Runtime.evaluate", "params":{"expression":filter_expr,"awaitPromise":True,"returnByValue":True}}))
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

        # Set date filters
        filter_settings = []
        for df in date_filters:
            filter_settings.append({
                "id": df.get("key"),
                "userInput": {
                    "value": [
                        {"offset": -1, "granularity": "DAY", "type": "OFFSET"},
                        {"offset": -1, "granularity": "DAY", "type": "OFFSET"}
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
                    print(f"Filter set: {val[:150]}")
                    break
            except asyncio.TimeoutError: break

        print("Waiting 30s...")
        await asyncio.sleep(30)

        # Query charts
        CHARTS = [
            ("Business Performance", "chart-6kwer-1357d"),
            ("New Signs", "chart-e8ns5-c9347"),
            ("Operation Performance", "chart-sqalg-1f515"),
            ("Promotion", "chart-iyhbp-a03a1"),
            ("User Experience", "chart-ltuz6-6cbdc"),
        ]

        cmd_id = 100
        for name, chart_id in CHARTS:
            print(f"\n{name}:")
            # Trigger query and get full response including columns
            expr = f"""new Promise((resolve) => {{
                try {{ window.DashboardController.executeQueryAndGetCHNResult(["{chart_id}"])
                    .then(r => resolve(JSON.stringify(r)))
                    .catch(e => resolve("ERR:"+e.message));
                }} catch(ex) {{ resolve("EX:"+ex.message); }}
            }})"""
            await ws.send(json.dumps({"id":cmd_id, "method":"Runtime.evaluate", "params":{"expression":expr,"awaitPromise":True,"returnByValue":True}}))
            cmd_id += 1
            deadline = asyncio.get_event_loop().time() + 60
            while asyncio.get_event_loop().time() < deadline:
                try:
                    r = await asyncio.wait_for(ws.recv(), timeout=1)
                    msg = json.loads(r)
                    if msg.get("id") == cmd_id - 1:
                        val = msg.get("result",{}).get("result",{}).get("value","")
                        resp = json.loads(val) if val else {}
                        code = resp.get("code")
                        data = resp.get("data", {})
                        if isinstance(data, dict):
                            rows = data.get("data", [])
                            cols = data.get("columns", [])
                            print(f"  code={code} rows={len(rows)} cols={len(cols)}")
                            if rows:
                                print(f"  First row: {str(rows[0])[:200]}")
                            elif cols:
                                print(f"  Columns: {cols[:5]}")
                        break
                except asyncio.TimeoutError:
                    break
            await asyncio.sleep(3)

result = asyncio.run(main())