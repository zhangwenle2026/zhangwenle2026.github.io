#!/usr/bin/env python3
"""Test single date: 20260828 with org filter"""
import asyncio, json, websockets, datetime, sys, http.client

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

        # Get filters
        filter_expr = """new Promise((resolve) => {
            try { window.DashboardController.getFiltersInfo()
                .then(res => resolve(JSON.stringify(res)))
                .catch(err => resolve("ERROR:"+err.message));
            } catch(e) { resolve("EX:"+e.message); }
        })"""
        await ws.send(json.dumps({"id":10, "method":"Runtime.evaluate", "params":{"expression":filter_expr,"awaitPromise":True,"returnByValue":True}}))
        deadline = asyncio.get_event_loop().time() + 30
        date_filter_id = None
        org2_filter_id = None
        while asyncio.get_event_loop().time() < deadline:
            try:
                r = await asyncio.wait_for(ws.recv(), timeout=1)
                msg = json.loads(r)
                if msg.get("id") == 10:
                    val = msg.get("result",{}).get("result",{}).get("value","")
                    data = json.loads(val)
                    for f in data.get("data",[]):
                        if f.get('name') == 'Date' and f.get('filterType') == 'time':
                            date_filter_id = f.get('key')
                        if '二级' in f.get('name','') or 'org_2' in f.get('key','').lower():
                            org2_filter_id = f.get('key')
                    break
            except asyncio.TimeoutError: break

        print(f"Date filter: {date_filter_id}, Org2 filter: {org2_filter_id}")

        # Set BOTH date + org filter for 20260828
        filter_settings = [
            {"id": date_filter_id, "userInput": {"value": ["20260828", "20260828"], "granularity": "DAY"}},
        ]
        if org2_filter_id:
            filter_settings.append({"id": org2_filter_id, "userInput": {"value": ["65280006_zhangwenle"], "isEmpty":False, "isNoFilter":False, "isSelectDummyAll":False, "selectAllFlag":False}})

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
                    print(f"Filter set: {msg.get('result',{}).get('result',{}).get('value','')[:150]}")
                    break
            except asyncio.TimeoutError: break

        await asyncio.sleep(20)

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
                    print(f"[20260828] code={code} rows={len(rows)}")
                    if rows: print(f"  sample: {str(rows[0])[:150]}")
                    break
            except asyncio.TimeoutError: break

result = asyncio.run(main())
