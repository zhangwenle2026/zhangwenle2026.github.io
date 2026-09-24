#!/usr/bin/env python3
"""DBR: query + download each chart completely before moving to next"""
import asyncio, json, websockets, datetime, sys, http.client

brt_now = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=3)
brt_yesterday = (brt_now - datetime.timedelta(days=1)).strftime("%Y%m%d")
DATA_DATE = brt_yesterday
print(f"Date: {DATA_DATE}")

conn = http.client.HTTPConnection("localhost", 9222)
conn.request("GET", "/json/list")
tabs = json.loads(conn.getresponse().read())
bi_tab = next((t for t in tabs if 'bi.keetapp' in t.get('url','')), None)
PAGE_WS = bi_tab['webSocketDebuggerUrl']

CHARTS = [
    ("Business Performance", "chart-6kwer-1357d"),
    ("New Signs", "chart-e8ns5-c9347"),
    ("Operation Performance", "chart-sqalg-1f515"),
    ("Promotion", "chart-iyhbp-a03a1"),
    ("User Experience", "chart-ltuz6-6cbdc"),
]

async def evaluate(ws, expr, cmd_id):
    await ws.send(json.dumps({"id": cmd_id, "method": "Runtime.evaluate", "params": {"expression": expr, "awaitPromise": True, "returnByValue": True}}))
    deadline = asyncio.get_event_loop().time() + 120
    while asyncio.get_event_loop().time() < deadline:
        try:
            r = await asyncio.wait_for(ws.recv(), timeout=1)
            msg = json.loads(r)
            if msg.get("id") == cmd_id:
                val = msg.get("result", {}).get("result", {}).get("value", "")
                return json.loads(val) if val else {}
        except asyncio.TimeoutError:
            break
    return None

async def main():
    async with websockets.connect(PAGE_WS) as ws:
        print("Connected")
        await ws.send(json.dumps({"id": 1, "method": "Runtime.enable"}))
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
        resp = await evaluate(ws, expr, 10)
        filters = resp.get("data", [])
        date_filters = [f for f in filters if f.get("filterType") == "time"]
        print(f"Date filters: {len(date_filters)}")

        # Set all date filters to yesterday
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

        print(f"Setting {len(date_filters)} date filters...")
        expr = f"""new Promise((resolve) => {{
            try {{ window.DashboardController.setFiltersValues({json.dumps(filter_settings)})
                .then(r => resolve(JSON.stringify(r)))
                .catch(e => resolve("ERR:"+e.message));
            }} catch(ex) {{ resolve("EX:"+ex.message); }}
        }})"""
        resp = await evaluate(ws, expr, 20)
        print(f"Filter set: code={resp.get('code')}")

        # Wait 25s
        print("Waiting 25s...")
        await asyncio.sleep(25)

        # Process each chart: query + download immediately
        results = {}
        has_data = 0
        cmd_id = 100
        for name, chart_id in CHARTS:
            print(f"\n--- {name} ---")

            # Trigger query
            expr = f"""new Promise((resolve) => {{
                try {{ window.DashboardController.executeQueryAndGetCHNResult(["{chart_id}"])
                    .then(r => resolve(JSON.stringify(r)))
                    .catch(e => resolve("ERR:"+e.message));
                }} catch(ex) {{ resolve("EX:"+ex.message); }}
            }})"""
            resp = await evaluate(ws, expr, cmd_id)
            cmd_id += 1

            query_rows = 0
            if resp and resp.get("code") == 0:
                rows = resp.get("data", {}).get("data", [])
                query_rows = len(rows)
                print(f"  Query: {query_rows} rows")
                if rows:
                    has_data += 1
                    results[name] = {"code": 0, "data": {"data": rows}}

            # Trigger download
            expr = f"""new Promise((resolve) => {{
                try {{ window.DashboardController.executeDownload("{chart_id}", {{fileType:"CSV"}})
                    .then(r => resolve(JSON.stringify(r)))
                    .catch(e => resolve("ERR:"+e.message));
                }} catch(ex) {{ resolve("EX:"+ex.message); }}
            }})"""
            resp = await evaluate(ws, expr, cmd_id)
            cmd_id += 1

            if resp and resp.get("code") == 0:
                data = resp.get("data", {})
                status = data.get("status")
                file_url = data.get("fileUrl", "")
                print(f"  Download: status={status}")
                if name not in results:
                    results[name] = {"code": 0, "download": file_url}
                    has_data += 1

        print(f"\nCharts with data: {has_data}/5")

        if has_data >= 1:
            out = f"/mnt/openclaw/.openclaw/workspace/dbr_data_{DATA_DATE}.json"
            with open(out, "w") as f:
                json.dump({"date": DATA_DATE, "data_source": "dom", "results": results}, f, ensure_ascii=False, indent=2)
            print(f"Saved to {out}")
            return {"has_data": has_data, "date": DATA_DATE, "results": results}
        else:
            return {"error": "no data", "date": DATA_DATE}

result = asyncio.run(main())
print(f"\nRESULT: {json.dumps(result, ensure_ascii=False)[:300]}")