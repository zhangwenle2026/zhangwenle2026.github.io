#!/usr/bin/env python3
"""DBR fetch: set all date filters, wait, query+download each chart"""
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

async def query_chart(ws, chart_id, cmd_id):
    expr = f"""new Promise((resolve) => {{
        try {{ window.DashboardController.executeQueryAndGetCHNResult(["{chart_id}"])
            .then(r => resolve(JSON.stringify(r)))
            .catch(e => resolve("ERR:"+e.message));
        }} catch(ex) {{ resolve("EX:"+ex.message); }}
    }})"""
    await ws.send(json.dumps({"id": cmd_id, "method": "Runtime.evaluate", "params": {"expression": expr, "awaitPromise": True, "returnByValue": True}}))
    deadline = asyncio.get_event_loop().time() + 60
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

async def download_chart(ws, chart_id, cmd_id):
    expr = f"""new Promise((resolve) => {{
        try {{ window.DashboardController.executeDownload("{chart_id}", {{fileType:"CSV"}})
            .then(r => resolve(JSON.stringify(r)))
            .catch(e => resolve("ERR:"+e.message));
        }} catch(ex) {{ resolve("EX:"+ex.message); }}
    }})"""
    await ws.send(json.dumps({"id": cmd_id, "method": "Runtime.evaluate", "params": {"expression": expr, "awaitPromise": True, "returnByValue": True}}))
    deadline = asyncio.get_event_loop().time() + 60
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
        await ws.send(json.dumps({"id": 10, "method": "Runtime.evaluate", "params": {"expression": expr, "awaitPromise": True, "returnByValue": True}}))
        deadline = asyncio.get_event_loop().time() + 30
        filters = []
        while asyncio.get_event_loop().time() < deadline:
            try:
                r = await asyncio.wait_for(ws.recv(), timeout=1)
                msg = json.loads(r)
                if msg.get("id") == 10:
                    val = msg.get("result", {}).get("result", {}).get("value", "")
                    data = json.loads(val)
                    filters = data.get("data", [])
                    break
            except asyncio.TimeoutError:
                break

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

        print(f"Setting {len(date_filters)} date filters to yesterday...")
        expr = f"""new Promise((resolve) => {{
            try {{ window.DashboardController.setFiltersValues({json.dumps(filter_settings)})
                .then(r => resolve(JSON.stringify(r)))
                .catch(e => resolve("ERR:"+e.message));
            }} catch(ex) {{ resolve("EX:"+ex.message); }}
        }})"""
        await ws.send(json.dumps({"id": 20, "method": "Runtime.evaluate", "params": {"expression": expr, "awaitPromise": True, "returnByValue": True}}))
        deadline = asyncio.get_event_loop().time() + 30
        while asyncio.get_event_loop().time() < deadline:
            try:
                r = await asyncio.wait_for(ws.recv(), timeout=1)
                msg = json.loads(r)
                if msg.get("id") == 20:
                    val = msg.get("result", {}).get("result", {}).get("value", "")
                    print(f"Filter set: {val[:150]}")
                    break
            except asyncio.TimeoutError:
                break

        print("Waiting 30s for charts to refresh...")
        await asyncio.sleep(30)

        results = {}
        has_data = 0
        cmd_id = 100
        for name, chart_id in CHARTS:
            print(f"\n{name}:")
            # Query
            resp = await query_chart(ws, chart_id, cmd_id)
            cmd_id += 1
            if resp:
                code = resp.get("code")
                rows = resp.get("data", {}).get("data", []) if isinstance(resp.get("data"), dict) else []
                print(f"  Query: code={code} rows={len(rows)}")
                if rows:
                    has_data += 1
                    results[name] = {"code": 0, "data": {"data": rows}}

            await asyncio.sleep(2)

            # Download
            resp = await download_chart(ws, chart_id, cmd_id)
            cmd_id += 1
            if resp:
                code = resp.get("code")
                if code == 0:
                    data = resp.get("data", {})
                    status = data.get("status")
                    file_url = data.get("fileUrl", "")
                    print(f"  Download: status={status}")
                    if name not in results:
                        results[name] = {"code": 0, "download": file_url}
                else:
                    print(f"  Download: code={code} msg={resp.get('message', '')}")

            await asyncio.sleep(2)

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