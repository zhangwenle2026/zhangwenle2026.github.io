#!/usr/bin/env python3
"""DBR: trigger all queries first, wait, then download"""
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

        # Set all date filters to yesterday using offset=-1
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

        # STEP 1: Trigger ALL queries first
        print("\n--- STEP 1: Triggering all queries ---")
        cmd_id = 100
        for name, chart_id in CHARTS:
            expr = f"""new Promise((resolve) => {{
                try {{ window.DashboardController.executeQueryAndGetCHNResult(["{chart_id}"])
                    .then(r => resolve(JSON.stringify(r)))
                    .catch(e => resolve("ERR:"+e.message));
                }} catch(ex) {{ resolve("EX:"+ex.message); }}
            }})"""
            await ws.send(json.dumps({"id": cmd_id, "method": "Runtime.evaluate", "params": {"expression": expr, "awaitPromise": True, "returnByValue": True}}))
            cmd_id += 1
            await asyncio.sleep(0.5)

        # Wait for all query responses
        print("Waiting for query responses...")
        deadline = asyncio.get_event_loop().time() + 120
        responses = {}
        while asyncio.get_event_loop().time() < deadline and len(responses) < len(CHARTS):
            try:
                r = await asyncio.wait_for(ws.recv(), timeout=1)
                msg = json.loads(r)
                if 100 <= msg.get("id", 0) < 100 + len(CHARTS):
                    idx = msg.get("id") - 100
                    name = CHARTS[idx][0]
                    val = msg.get("result", {}).get("result", {}).get("value", "")
                    resp = json.loads(val) if val else {}
                    responses[name] = resp
                    code = resp.get("code")
                    rows = resp.get("data", {}).get("data", []) if isinstance(resp.get("data"), dict) else []
                    print(f"  [{name}] code={code} rows={len(rows)}")
            except asyncio.TimeoutError:
                break

        # Wait 30s for charts to fully load
        print("\nWaiting 30s for charts to load after queries...")
        await asyncio.sleep(30)

        # STEP 2: Try downloading each chart
        print("\n--- STEP 2: Downloading charts ---")
        cmd_id = 200
        for name, chart_id in CHARTS:
            expr = f"""new Promise((resolve) => {{
                try {{ window.DashboardController.executeDownload("{chart_id}", {{fileType:"CSV"}})
                    .then(r => resolve(JSON.stringify(r)))
                    .catch(e => resolve("ERR:"+e.message));
                }} catch(ex) {{ resolve("EX:"+ex.message); }}
            }})"""
            await ws.send(json.dumps({"id": cmd_id, "method": "Runtime.evaluate", "params": {"expression": expr, "awaitPromise": True, "returnByValue": True}}))
            cmd_id += 1
            await asyncio.sleep(0.5)

        # Wait for all download responses
        print("Waiting for download responses...")
        deadline = asyncio.get_event_loop().time() + 120
        download_responses = {}
        while asyncio.get_event_loop().time() < deadline and len(download_responses) < len(CHARTS):
            try:
                r = await asyncio.wait_for(ws.recv(), timeout=1)
                msg = json.loads(r)
                if 200 <= msg.get("id", 0) < 200 + len(CHARTS):
                    idx = msg.get("id") - 200
                    name = CHARTS[idx][0]
                    val = msg.get("result", {}).get("result", {}).get("value", "")
                    resp = json.loads(val) if val else {}
                    download_responses[name] = resp
                    code = resp.get("code")
                    if code == 0:
                        data = resp.get("data", {})
                        status = data.get("status")
                        file_url = data.get("fileUrl", "")[:150]
                        print(f"  [{name}] status={status} url={file_url}")
                    else:
                        print(f"  [{name}] code={code} msg={resp.get('message', '')}")
            except asyncio.TimeoutError:
                break

        # Check if we got any useful data
        has_download = sum(1 for r in download_responses.values() if r.get("code") == 0 and r.get("data", {}).get("status") == "SUCCEED")
        has_query = sum(1 for r in responses.values() if r.get("code") == 0 and len(r.get("data", {}).get("data", [])) > 0)

        print(f"\nQuery with data: {has_query}/5")
        print(f"Download succeed: {has_download}/5")

        if has_query >= 1 or has_download >= 1:
            results = {}
            for name, chart_id in CHARTS:
                if name in responses and responses[name].get("code") == 0:
                    rows = responses[name].get("data", {}).get("data", [])
                    if rows:
                        results[name] = {"code": 0, "data": {"data": rows}}
                elif name in download_responses and download_responses[name].get("code") == 0:
                    data = download_responses[name].get("data", {})
                    if data.get("status") == "SUCCEED":
                        results[name] = {"code": 0, "download": data.get("fileUrl", "")}

            out = f"/mnt/openclaw/.openclaw/workspace/dbr_data_{DATA_DATE}.json"
            with open(out, "w") as f:
                json.dump({"date": DATA_DATE, "data_source": "dom", "results": results}, f, ensure_ascii=False, indent=2)
            print(f"Saved to {out}")
            return {"has_data": max(has_query, has_download), "date": DATA_DATE, "results": results}

        return {"error": "no data", "date": DATA_DATE}

result = asyncio.run(main())
print(f"\nRESULT: {json.dumps(result, ensure_ascii=False)[:300]}")