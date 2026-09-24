#!/usr/bin/env python3
"""DBR fetch with page reload for 2026-09-11"""
import asyncio, json, websockets, base64, datetime, sys, http.client

brt_now = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=3)
brt_yesterday = (brt_now - datetime.timedelta(days=1)).strftime("%Y%m%d")
DATA_DATE = brt_yesterday
print(f"Data date: {DATA_DATE}")

# Discover BI tab
conn = http.client.HTTPConnection("localhost", 9222)
conn.request("GET", "/json/list")
tabs = json.loads(conn.getresponse().read())
bi_tab = next((t for t in tabs if 'bi.keetapp' in t.get('url','')), None)
if not bi_tab:
    print("ERROR: No BI tab found"); sys.exit(1)
PAGE_WS = bi_tab['webSocketDebuggerUrl']
print(f"BI tab: {bi_tab['url']}")

TARGET_CHARTS = {
    "Business Performance": "chart-6kwer-1357d",
    "New Signs": "chart-e8ns5-c9347",
    "Operation Performance": "chart-sqalg-1f515",
    "Promotion": "chart-iyhbp-a03a1",
    "User Experience": "chart-ltuz6-6cbdc",
}
ORG_2_ID = "65280006_zhangwenle"

async def main():
    async with websockets.connect(PAGE_WS) as ws:
        print("Connected")
        await ws.send(json.dumps({"id":1, "method":"Runtime.enable"}))
        await ws.send(json.dumps({"id":2, "method":"Page.enable"}))
        await asyncio.sleep(1)
        for _ in range(10):
            try: await asyncio.wait_for(ws.recv(), timeout=1)
            except asyncio.TimeoutError: break

        # RELOAD
        print("Reloading page...")
        await ws.send(json.dumps({"id":10, "method":"Page.reload"}))
        deadline = asyncio.get_event_loop().time() + 15
        while asyncio.get_event_loop().time() < deadline:
            try:
                r = await asyncio.wait_for(ws.recv(), timeout=1)
                msg = json.loads(r)
                if msg.get("id") == 10:
                    print(f"Reload ACK: {msg}"); break
            except asyncio.TimeoutError: break

        print("Waiting 30s for page load...")
        await asyncio.sleep(30)

        # Check URL
        await ws.send(json.dumps({"id":20, "method":"Runtime.evaluate", "params":{"expression":"location.href","returnByValue":True}}))
        deadline = asyncio.get_event_loop().time() + 10
        while asyncio.get_event_loop().time() < deadline:
            try:
                r = await asyncio.wait_for(ws.recv(), timeout=1)
                msg = json.loads(r)
                if msg.get("id") == 20:
                    url = msg.get("result",{}).get("result",{}).get("value","")
                    print(f"URL: {url}")
                    if "login" in url.lower(): print("SSO expired!"); return {"error":"SSO expired"}
                    break
            except asyncio.TimeoutError: break

        # DashboardController
        print("Waiting for DashboardController...")
        ready = False
        for attempt in range(30):
            await ws.send(json.dumps({"id":30+attempt, "method":"Runtime.evaluate", "params":{"expression":"typeof window.DashboardController","returnByValue":True}}))
            deadline = asyncio.get_event_loop().time() + 5
            while asyncio.get_event_loop().time() < deadline:
                try:
                    r = await asyncio.wait_for(ws.recv(), timeout=1)
                    msg = json.loads(r)
                    if msg.get("id") == 30+attempt:
                        dc = msg.get("result",{}).get("result",{}).get("value","")
                        if dc == "object":
                            print(f"DashboardController ready (attempt {attempt+1})"); ready = True; break
                        break
                except asyncio.TimeoutError: break
            if ready: break
            await asyncio.sleep(1)
        if not ready: print("DashboardController not ready"); return {"error":"DashboardController not ready"}

        # Get filters
        print("Getting filters...")
        filter_expr = """new Promise((resolve) => {
            try { window.DashboardController.getFiltersInfo()
                .then(res => resolve({ok:true, data:JSON.stringify(res)}))
                .catch(err => resolve({ok:false, error:err.message||String(err)}));
            } catch(e) { resolve({ok:false, error:e.message}); }
        })"""
        await ws.send(json.dumps({"id":60, "method":"Runtime.evaluate", "params":{"expression":filter_expr,"awaitPromise":True,"returnByValue":True}}))
        filter_map = {}
        deadline = asyncio.get_event_loop().time() + 30
        while asyncio.get_event_loop().time() < deadline:
            try:
                r = await asyncio.wait_for(ws.recv(), timeout=1)
                msg = json.loads(r)
                if msg.get("id") == 60:
                    val = msg.get("result",{}).get("result",{}).get("value",{})
                    if val and val.get("ok"):
                        filters = json.loads(val["data"])
                        for f in filters.get("data",[]):
                            filter_map[f.get("name","")] = f.get("key")
                            print(f"  Filter: {f.get('name')} = {f.get('key')}")
                    break
            except asyncio.TimeoutError: break

        # Set date + org filters
        date_key = filter_map.get("Date")
        org2_key = None
        for k, v in filter_map.items():
            if "二级" in k or "org_2" in k.lower(): org2_key = v; break

        filter_settings = []
        if date_key:
            filter_settings.append({"id":date_key,"userInput":{"value":[DATA_DATE,DATA_DATE],"granularity":"DAY"}})
        if org2_key:
            filter_settings.append({"id":org2_key,"userInput":{"value":[ORG_2_ID],"isEmpty":False,"isNoFilter":False,"isSelectDummyAll":False,"selectAllFlag":False}})

        if filter_settings:
            print(f"Setting {len(filter_settings)} filters...")
            expr = f"""new Promise((resolve) => {{
                try {{ window.DashboardController.setFiltersValues({json.dumps(filter_settings)})
                    .then(res => resolve({{ok:true, data:JSON.stringify(res)}}))
                    .catch(err => resolve({{ok:false, error:err.message||String(err)}}));
                }} catch(e) {{ resolve({{ok:false, error:e.message}}); }}
            }})"""
            await ws.send(json.dumps({"id":70, "method":"Runtime.evaluate", "params":{"expression":expr,"awaitPromise":True,"returnByValue":True}}))
            deadline = asyncio.get_event_loop().time() + 30
            while asyncio.get_event_loop().time() < deadline:
                try:
                    r = await asyncio.wait_for(ws.recv(), timeout=1)
                    msg = json.loads(r)
                    if msg.get("id") == 70:
                        val = msg.get("result",{}).get("result",{}).get("value",{})
                        if val and val.get("ok"):
                            d = json.loads(val["data"])
                            print(f"  Filters set: code={d.get('code')} msg={d.get('message','')}")
                        break
                except asyncio.TimeoutError: break

        print("Waiting 25s for charts to refresh...")
        await asyncio.sleep(25)

        # Query charts
        results = {}
        has_data = 0
        cmd_id = 100
        for name, chart_id in TARGET_CHARTS.items():
            print(f"\nQuerying {name}...")
            expr = f"""new Promise((resolve) => {{
                try {{ window.DashboardController.executeQueryAndGetCHNResult(["{chart_id}"])
                    .then(res => resolve({{ok:true, data:JSON.stringify(res)}}))
                    .catch(err => resolve({{ok:false, error:err.message||String(err)}}));
                }} catch(e) {{ resolve({{ok:false, error:e.message}}); }}
            }})"""
            await ws.send(json.dumps({"id":cmd_id, "method":"Runtime.evaluate", "params":{"expression":expr,"awaitPromise":True,"returnByValue":True}}))
            deadline = asyncio.get_event_loop().time() + 70
            while asyncio.get_event_loop().time() < deadline:
                try:
                    r = await asyncio.wait_for(ws.recv(), timeout=1)
                    msg = json.loads(r)
                    if msg.get("id") == cmd_id:
                        val = msg.get("result",{}).get("result",{}).get("value",{})
                        if val and val.get("ok"):
                            data = json.loads(val["data"])
                            results[name] = data
                            if isinstance(data, dict) and data.get("code") == 0:
                                rows = data.get("data",{}).get("data",[])
                                cols = data.get("data",{}).get("columns",[])
                                print(f"  -> {len(rows)} rows, cols: {cols[:5]}")
                                if rows: has_data += 1; print(f"  sample: {str(rows[0])[:150]}")
                            else: print(f"  -> code={data.get('code','N/A')}")
                        else:
                            err = val.get("error","unknown") if val else str(msg)
                            print(f"  -> ERROR: {err}")
                            results[name] = {"error": err}
                        break
                except asyncio.TimeoutError: break
            cmd_id += 1
            await asyncio.sleep(2)

        print(f"\nCharts with data: {has_data}/{len(results)}")

        if has_data >= 1:
            out = f"/mnt/openclaw/.openclaw/workspace/dbr_data_{DATA_DATE}.json"
            with open(out, "w") as f:
                json.dump({"date":DATA_DATE,"data_source":"dom","results":results}, f, ensure_ascii=False, indent=2)
            print(f"Saved to {out}")
            return {"has_data": has_data, "date": DATA_DATE, "results": results}
        else:
            print("\nNo data. Taking screenshot...")
            await ws.send(json.dumps({"id":200, "method":"Page.captureScreenshot", "params":{"format":"png","fromSurface":True}}))
            deadline = asyncio.get_event_loop().time() + 30
            while asyncio.get_event_loop().time() < deadline:
                try:
                    r = await asyncio.wait_for(ws.recv(), timeout=1)
                    msg = json.loads(r)
                    if msg.get("id") == 200:
                        data = msg.get("result",{}).get("data","")
                        if data:
                            out = f"/mnt/openclaw/.openclaw/workspace/dbr_screenshot_{DATA_DATE}.png"
                            with open(out, "wb") as f:
                                f.write(base64.b64decode(data))
                            print(f"Screenshot: {out}")
                            return {"data_source":"screenshot","screenshot":out,"date":DATA_DATE}
                        break
                except asyncio.TimeoutError: break
            return {"error":"no data, screenshot failed"}

result = asyncio.run(main())
print(f"\nRESULT: {json.dumps(result, ensure_ascii=False)[:300]}")