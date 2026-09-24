#!/usr/bin/env python3
"""Quick test: Business Performance chart download"""
import asyncio, json, websockets, datetime, http.client

conn = http.client.HTTPConnection("localhost", 9222)
conn.request("GET", "/json/list")
tabs = json.loads(conn.getresponse().read())
bi_tab = next((t for t in tabs if 'bi.keetapp' in t.get('url','')), None)
PAGE_WS = bi_tab['webSocketDebuggerUrl']

async def main():
    async with websockets.connect(PAGE_WS) as ws:
        print("Connected")
        await ws.send(json.dumps({"id":1, "method":"Runtime.enable"}))
        await asyncio.sleep(1)
        for _ in range(10):
            try: await asyncio.wait_for(ws.recv(), timeout=1)
            except asyncio.TimeoutError: break

        # Get filter info
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
                    date_filters = [f for f in filters if f.get('filterType') == 'time']
                    print(f"Date filters: {len(date_filters)}")
                    for df in date_filters:
                        print(f"  {df.get('name')} = {df.get('key')}")
                    break
            except asyncio.TimeoutError: break

        # Set date on ALL 5 date filters to "yesterday" (offset=-1)
        all_date_filters = []
        for df in date_filters:
            all_date_filters.append({"id": df.get('key'), "userInput": {
                "value": [
                    {"offset": -1, "granularity": "DAY", "type": "OFFSET"},
                    {"offset": -1, "granularity": "DAY", "type": "OFFSET"}
                ],
                "granularity": "DAY"
            }})

        print(f"\nSetting {len(all_date_filters)} date filters...")
        expr = f"""new Promise((resolve) => {{
            try {{ window.DashboardController.setFiltersValues({json.dumps(all_date_filters)})
                .then(r => resolve(JSON.stringify(r)))
                .catch(e => resolve("ERR:"+e.message));
            }} catch(ex) {{ resolve("EX:"+ex.message); }}
        }})"""
        await ws.send(json.dumps({"id":20, "method":"Runtime.evaluate", "params":{"expression":expr,"awaitPromise":True,"returnByValue":True}}))
        deadline = asyncio.get_event_loop().time() + 20
        while asyncio.get_event_loop().time() < deadline:
            try:
                r = await asyncio.wait_for(ws.recv(), timeout=1)
                msg = json.loads(r)
                if msg.get("id") == 20:
                    val = msg.get("result",{}).get("result",{}).get("value","")
                    print(f"Filter set: {val[:200]}")
                    break
            except asyncio.TimeoutError: break

        print("Waiting 25s...")
        await asyncio.sleep(25)

        # Query ALL 5 charts with query+download
        charts = [
            ("Business Performance", "chart-6kwer-1357d"),
            ("New Signs", "chart-e8ns5-c9347"),
            ("Operation Performance", "chart-sqalg-1f515"),
            ("Promotion", "chart-iyhbp-a03a1"),
            ("User Experience", "chart-ltuz6-6cbdc"),
        ]

        for name, chart_id in charts:
            print(f"\n{name}:")

            # Trigger query
            expr = f"""new Promise((resolve) => {{
                try {{ window.DashboardController.executeQueryAndGetCHNResult(["{chart_id}"])
                    .then(r => resolve(JSON.stringify(r)))
                    .catch(e => resolve("ERR:"+e.message));
                }} catch(ex) {{ resolve("EX:"+ex.message); }}
            }})"""
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
                        rows = resp.get("data",{}).get("data",[]) if isinstance(resp.get("data"), dict) else []
                        print(f"  Query: code={code} rows={len(rows)}")
                        if rows:
                            print(f"  Sample: {str(rows[0])[:120]}")
                        break
                except asyncio.TimeoutError: break

            await asyncio.sleep(2)

            # Download
            expr = f"""new Promise((resolve) => {{
                try {{ window.DashboardController.executeDownload("{chart_id}", {{fileType:"CSV"}})
                    .then(r => resolve(JSON.stringify(r)))
                    .catch(e => resolve("ERR:"+e.message));
                }} catch(ex) {{ resolve("EX:"+ex.message); }}
            }})"""
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
                        if code == 0:
                            data = resp.get("data",{})
                            status = data.get("status")
                            file_url = data.get("fileUrl","")[:150]
                            print(f"  Download: status={status} url={file_url}")
                        else:
                            print(f"  Download: code={code} msg={resp.get('message','')}")
                        break
                except asyncio.TimeoutError: break

            await asyncio.sleep(2)

result = asyncio.run(main())
print("\nDONE")