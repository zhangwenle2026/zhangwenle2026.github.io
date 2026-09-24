#!/usr/bin/env python3
"""DBR fetch using executeDownload approach"""
import asyncio, json, websockets, datetime, sys, http.client

brt_now = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=3)
brt_yesterday = (brt_now - datetime.timedelta(days=1)).strftime("%Y%m%d")
DATA_DATE = brt_yesterday
print(f"Data date: {DATA_DATE}")

conn = http.client.HTTPConnection("localhost", 9222)
conn.request("GET", "/json/list")
tabs = json.loads(conn.getresponse().read())
bi_tab = next((t for t in tabs if 'bi.keetapp' in t.get('url','')), None)
if not bi_tab:
    print("No BI tab"); sys.exit(1)
PAGE_WS = bi_tab['webSocketDebuggerUrl']

TARGET_CHARTS = {
    "Business Performance": "chart-6kwer-1357d",
    "New Signs": "chart-e8ns5-c9347",
    "Operation Performance": "chart-sqalg-1f515",
    "Promotion": "chart-iyhbp-a03a1",
    "User Experience": "chart-ltuz6-6cbdc",
}

async def main():
    async with websockets.connect(PAGE_WS) as ws:
        print("Connected")
        await ws.send(json.dumps({"id":1, "method":"Runtime.enable"}))
        await asyncio.sleep(1)
        for _ in range(10):
            try: await asyncio.wait_for(ws.recv(), timeout=1)
            except asyncio.TimeoutError: break

        # Get components to understand the page structure
        expr = """new Promise((resolve) => {
            try { window.DashboardController.getComponents()
                .then(res => resolve(JSON.stringify(res)))
                .catch(err => resolve("ERROR:"+err.message));
            } catch(e) { resolve("EX:"+e.message); }
        })"""
        await ws.send(json.dumps({"id":5, "method":"Runtime.evaluate", "params":{"expression":expr,"awaitPromise":True,"returnByValue":True}}))
        deadline = asyncio.get_event_loop().time() + 30
        while asyncio.get_event_loop().time() < deadline:
            try:
                r = await asyncio.wait_for(ws.recv(), timeout=1)
                msg = json.loads(r)
                if msg.get("id") == 5:
                    val = msg.get("result",{}).get("result",{}).get("value","")
                    data = json.loads(val)
                    print(f"Components: code={data.get('code')}")
                    components = data.get("data",[])
                    for c in components:
                        ct = c.get("componentType")
                        cn = c.get("componentName","")
                        cid = c.get("componentId","")
                        print(f"  [{ct}] {cn} = {cid}")
                    break
            except asyncio.TimeoutError: break

        # Get all filters
        expr = """new Promise((resolve) => {
            try { window.DashboardController.getFiltersInfo()
                .then(res => resolve(JSON.stringify(res)))
                .catch(err => resolve("ERROR:"+err.message));
            } catch(e) { resolve("EX:"+e.message); }
        })"""
        await ws.send(json.dumps({"id":10, "method":"Runtime.evaluate", "params":{"expression":expr,"awaitPromise":True,"returnByValue":True}}))
        deadline = asyncio.get_event_loop().time() + 30
        filters_data = None
        while asyncio.get_event_loop().time() < deadline:
            try:
                r = await asyncio.wait_for(ws.recv(), timeout=1)
                msg = json.loads(r)
                if msg.get("id") == 10:
                    val = msg.get("result",{}).get("result",{}).get("value","")
                    filters_data = json.loads(val)
                    break
            except asyncio.TimeoutError: break

        if not filters_data:
            print("Could not get filters")
            return

        filters = filters_data.get("data",[])
        print(f"\nFilters ({len(filters)}):")
        date_filters = []
        for f in filters:
            print(f"  [{f.get('filterType')}] {f.get('name')} = {f.get('key')} currentValue={f.get('currentValue','N/A')}")
            if f.get('filterType') == 'time':
                date_filters.append(f)

        if not date_filters:
            print("No date filter found!")
            return

        # Use the first date filter (or all of them)
        date_filter_id = date_filters[0].get('key')
        print(f"\nUsing date filter: {date_filter_id}")

        # Set date filter using offset method
        # Yesterday: offset=-1 for both start and end
        filter_settings = [{"id": date_filter_id, "userInput": {
            "value": [
                {"offset": -1, "granularity": "DAY", "type": "OFFSET"},
                {"offset": -1, "granularity": "DAY", "type": "OFFSET"}
            ],
            "granularity": "DAY"
        }}]

        print(f"Setting date filter (offset=-1)...")
        expr = f"""new Promise((resolve) => {{
            try {{ window.DashboardController.setFiltersValues({json.dumps(filter_settings)})
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
                    print(f"  Filter set: {val[:200]}")
                    break
            except asyncio.TimeoutError: break

        print("Waiting 25s for charts to refresh...")
        await asyncio.sleep(25)

        # Try executeDownload approach
        results = {}
        has_data = 0
        for name, chart_id in TARGET_CHARTS.items():
            print(f"\n{name}:")

            # First trigger query
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
                            has_data += 1
                            results[name] = {"code":0,"data":{"data":rows}}
                        break
                except asyncio.TimeoutError: break

            # Try executeDownload
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
                        print(f"  Download: {val[:300]}")
                        break
                except asyncio.TimeoutError: break

            await asyncio.sleep(3)

        print(f"\nCharts with data via query: {has_data}/5")

        if has_data >= 1:
            out = f"/mnt/openclaw/.openclaw/workspace/dbr_data_{DATA_DATE}.json"
            with open(out, "w") as f:
                json.dump({"date":DATA_DATE,"data_source":"dom","results":results}, f, ensure_ascii=False, indent=2)
            print(f"Saved to {out}")
            return {"has_data":has_data, "date":DATA_DATE, "results":results}

        return {"error":"no data"}

result = asyncio.run(main())
print(f"\nRESULT: {json.dumps(result, ensure_ascii=False)[:300]}")