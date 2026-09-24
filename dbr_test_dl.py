#!/usr/bin/env python3
"""Test download with cookies from browser session"""
import asyncio, json, websockets, datetime, http.client, urllib.request, urllib.error

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

        # Get browser cookies
        await ws.send(json.dumps({"id":5, "method":"Network.getCookies", "params":{"urls":["https://bi.keetapp.com"]}}))
        deadline = asyncio.get_event_loop().time() + 10
        cookies = []
        cookie_str = ""
        while asyncio.get_event_loop().time() < deadline:
            try:
                r = await asyncio.wait_for(ws.recv(), timeout=1)
                msg = json.loads(r)
                if msg.get("id") == 5:
                    cookies = msg.get("result",{}).get("cookies",[])
                    cookie_str = "; ".join(f"{c['name']}={c['value']}" for c in cookies)
                    print(f"Cookies: {len(cookies)}")
                    break
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
        date_filters = []
        while asyncio.get_event_loop().time() < deadline:
            try:
                r = await asyncio.wait_for(ws.recv(), timeout=1)
                msg = json.loads(r)
                if msg.get("id") == 10:
                    val = msg.get("result",{}).get("result",{}).get("value","")
                    data = json.loads(val)
                    for f in data.get("data",[]):
                        if f.get("filterType") == "time":
                            date_filters.append(f)
                    break
            except asyncio.TimeoutError: break

        # Set date filter
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
                    print(f"Filter set: {val[:100]}")
                    break
            except asyncio.TimeoutError: break

        await asyncio.sleep(25)

        # Try to query with filter parameters passed directly
        # Try to query the API with explicit date parameter
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
                        print(f"BP Query: code={code} rows={len(rows)} cols={len(cols)}")
                        if rows: print(f"  First row: {str(rows[0])[:200]}")
                        elif cols: print(f"  Cols: {cols[:5]}")
                    break
            except asyncio.TimeoutError: break

        await asyncio.sleep(3)

        # Try download with cookies
        expr = """new Promise((resolve) => {
            try { window.DashboardController.executeDownload("chart-6kwer-1357d", {fileType:"CSV"})
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
                    if code == 0:
                        data = resp.get("data", {})
                        status = data.get("status")
                        file_url = data.get("fileUrl", "")
                        print(f"BP Download: status={status}")
                        print(f"  URL: {file_url}")

                        # Try downloading with cookies
                        if file_url and status == "SUCCEED":
                            print("\nTrying download with browser cookies...")
                            req = urllib.request.Request(file_url)
                            req.add_header("Cookie", cookie_str[:2000])
                            req.add_header("User-Agent", "Mozilla/5.0 (X11; Linux x86_64) Chrome/120.0.0.0 Safari/537.36")
                            try:
                                # Follow redirects manually
                                class NoRedirect(urllib.request.HTTPRedirectHandler):
                                    def redirect_request(self, req, fp, code, msg, headers, newurl):
                                        return None
                                opener = urllib.request.build_opener(NoRedirect)
                                resp = opener.open(req, timeout=30)
                                print(f"  Response code: {resp.code}")
                                content = resp.read(1000)
                                print(f"  Content: {content[:200]}")
                            except urllib.error.HTTPError as e:
                                print(f"  HTTP Error: {e.code}")
                                # Try following redirect manually
                                req2 = urllib.request.Request(file_url)
                                req2.add_header("Cookie", cookie_str[:2000])
                                req2.add_header("User-Agent", "Mozilla/5.0")
                                try:
                                    resp2 = urllib.request.urlopen(req2, timeout=30)
                                    print(f"  Followed: {resp2.code}")
                                    content = resp2.read(1000)
                                    print(f"  Content: {content[:200]}")
                                except Exception as e2:
                                    print(f"  Error: {e2}")
                    else:
                        print(f"BP Download: code={code} msg={resp.get('message','')}")
                    break
            except asyncio.TimeoutError: break

result = asyncio.run(main())