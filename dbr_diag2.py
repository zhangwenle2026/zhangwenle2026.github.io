#!/usr/bin/env python3
"""DBR fetch with full diagnostics"""
import asyncio, json, websockets, datetime, sys, http.client

brt_now = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=3)
brt_yesterday = (brt_now - datetime.timedelta(days=1)).strftime("%Y%m%d")
DATA_DATE = brt_yesterday
DATE_DASHED = (brt_now - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
print(f"Date: {DATA_DATE} / {DATE_DASHED}")

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

        # Check filter info again to see what's available
        filter_expr = """new Promise((resolve) => {
            try { window.DashboardController.getFiltersInfo()
                .then(res => resolve(JSON.stringify(res)))
                .catch(err => resolve("ERROR:"+err.message));
            } catch(e) { resolve("EXCEPTION:"+e.message); }
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
                    print(f"Filters ({len(filters)}):")
                    for f in filters:
                        print(f"  [{f.get('filterType')}] {f.get('name')} = {f.get('key')} currentValue={f.get('currentValue','N/A')}")
                    break
            except asyncio.TimeoutError: break

        # Try multiple date formats for Date filter
        date_filter_id = None
        for f in filters:
            if f.get('name') == 'Date':
                date_filter_id = f.get('key')
                break

        if date_filter_id:
            # Try format 1: YYYYMMDD
            for date_fmt in [DATA_DATE, DATE_DASHED]:
                filter_settings = [{"id": date_filter_id, "userInput": {"value": [date_fmt, date_fmt], "granularity": "DAY"}}]
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
                            print(f"[{date_fmt}] Filter set: {val[:200]}")
                            break
                    except asyncio.TimeoutError: break

                await asyncio.sleep(25)

                # Query chart
                await ws.send(json.dumps({"id":21, "method":"Runtime.evaluate", "params":{"expression":"""new Promise((resolve) => {
                    try { window.DashboardController.executeQueryAndGetCHNResult(["chart-6kwer-1357d"])
                        .then(r => resolve(JSON.stringify(r)))
                        .catch(e => resolve("ERR:"+e.message));
                    } catch(ex) { resolve("EX:"+ex.message); }
                })""","awaitPromise":True,"returnByValue":True}}))
                deadline = asyncio.get_event_loop().time() + 30
                while asyncio.get_event_loop().time() < deadline:
                    try:
                        r = await asyncio.wait_for(ws.recv(), timeout=1)
                        msg = json.loads(r)
                        if msg.get("id") == 21:
                            val = msg.get("result",{}).get("result",{}).get("value","")
                            resp = json.loads(val) if val else {}
                            code = resp.get("code", None)
                            rows = resp.get("data",{}).get("data",[]) if isinstance(resp.get("data"), dict) else []
                            print(f"[{date_fmt}] Chart query: code={code} rows={len(rows)}")
                            if rows:
                                print(f"  sample: {str(rows[0])[:150]}")
                            break
                    except asyncio.TimeoutError: break

result = asyncio.run(main())
