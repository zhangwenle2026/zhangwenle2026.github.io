import asyncio, json, websockets, base64, datetime

PAGE_WS = "ws://localhost:9222/devtools/page/30B89CE186B7DF4D7EB7A5EDBC8C0412"

brt_now = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=3)
brt_yesterday = (brt_now - datetime.timedelta(days=1)).strftime("%Y%m%d")
DATA_DATE = brt_yesterday

async def send_cmd(ws, cmd_id, method, params=None):
    msg = {"id": cmd_id, "method": method}
    if params:
        msg["params"] = params
    await ws.send(json.dumps(msg))
    return msg["id"]

async def recv_until(ws, cmd_id, timeout=30):
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        try:
            r = await asyncio.wait_for(ws.recv(), timeout=deadline - asyncio.get_event_loop().time())
            msg = json.loads(r)
            if msg.get("id") == cmd_id:
                return msg
        except asyncio.TimeoutError:
            break
    return None

async def main():
    async with websockets.connect(PAGE_WS) as ws:
        print("Connected, enabling domains...")
        await send_cmd(ws, 1, "Runtime.enable")
        await send_cmd(ws, 2, "Page.enable")
        for _ in range(5):
            try:
                await asyncio.wait_for(ws.recv(), timeout=1)
            except asyncio.TimeoutError:
                break
        
        # Reload page
        print("Reloading page...")
        await send_cmd(ws, 10, "Page.reload", {"ignoreCache": True})
        await asyncio.sleep(15)
        
        # Wait for DashboardController
        for attempt in range(60):
            await send_cmd(ws, 20+attempt, "Runtime.evaluate", {
                "expression": "typeof window.DashboardController",
                "returnByValue": True
            })
            resp = await recv_until(ws, 20+attempt, timeout=5)
            dc = resp.get("result",{}).get("result",{}).get("value","") if resp else ""
            if dc == "object":
                print(f"DashboardController ready at attempt {attempt+1}")
                break
            await asyncio.sleep(2)
        else:
            print("DashboardController not ready after reload")
            return {"error": "DashboardController not ready"}
        
        # Extra wait for charts to load
        await asyncio.sleep(10)
        
        # Check visible content
        await send_cmd(ws, 90, "Runtime.evaluate", {
            "expression": """
                (function(){
                    var body = document.body.innerText;
                    return body.substring(0,500);
                })()
            """,
            "returnByValue": True
        })
        resp = await recv_until(ws, 90, timeout=10)
        body_text = resp.get("result",{}).get("result",{}).get("value","") if resp else ""
        print(f"Body text (first 200): {body_text[:200]}")
        
        charts = [
            ("Business Performance", "chart-6kwer-1357d"),
            ("New Signs", "chart-e8ns5-c9347"),
            ("Operation Performance", "chart-sqalg-1f515"),
            ("Promotion", "chart-iyhbp-a03a1"),
            ("User Experience", "chart-ltuz6-6cbdc"),
        ]
        
        results = {}
        cmd_id = 100
        for name, chart_id in charts:
            print(f"Querying {name} ({chart_id})...")
            expr = f'''
                new Promise((resolve) => {{
                    try {{
                        window.DashboardController.executeQueryAndGetCHNResult("{chart_id}")
                            .then(res => resolve({{ok:true, data:JSON.stringify(res)}}))
                            .catch(err => resolve({{ok:false, error:err.message || String(err)}}));
                    }} catch(e) {{
                        resolve({{ok:false, error: "exception: " + e.message}});
                    }}
                }})
            '''
            await send_cmd(ws, cmd_id, "Runtime.evaluate", {
                "expression": expr,
                "awaitPromise": True,
                "returnByValue": True,
                "timeout": 60000
            })
            resp = await recv_until(ws, cmd_id, timeout=70)
            cmd_id += 1
            if not resp:
                print(f"  -> TIMEOUT")
                results[name] = {"error": "timeout"}
                await asyncio.sleep(2)
                continue
            
            result_obj = resp.get("result",{}).get("result",{})
            val = result_obj.get("value",{})
            
            if val and val.get("ok"):
                try:
                    data = json.loads(val["data"])
                    results[name] = data
                    if isinstance(data, dict) and data.get("code") == 0:
                        rows = data.get("data",{}).get("data",[])
                        print(f"  -> OK {len(rows)} rows")
                    else:
                        print(f"  -> Response code: {data.get('code', 'N/A')}, msg={data.get('message','')}")
                except Exception as e:
                    print(f"  -> Parse error: {e}")
                    results[name] = {"error": f"parse: {e}"}
            else:
                err = val.get("error", "unknown") if val else str(result_obj)
                print(f"  -> ERROR: {err}")
                results[name] = {"error": err}
            
            await asyncio.sleep(2)
        
        has_data = sum(1 for v in results.values() if isinstance(v, dict) and v.get("code") == 0)
        print(f"Charts with data: {has_data}/{len(charts)}")
        
        # Count rows in each
        for name, v in results.items():
            if isinstance(v, dict) and v.get("code") == 0:
                rows = v.get("data",{}).get("data",[])
                print(f"  {name}: {len(rows)} rows")
                if rows:
                    print(f"    sample: {str(rows[0])[:150]}")
        
        if has_data >= 2:
            out = f"/mnt/openclaw/.openclaw/workspace/dbr_data_{DATA_DATE}.json"
            with open(out, "w") as f:
                json.dump({"date": DATA_DATE, "data_source":"dom", "results":results, "body_preview": body_text[:200]}, f, ensure_ascii=False, indent=2)
            print(f"Saved to {out}")
            return {"has_data": has_data, "results": results, "data_source": "dom", "date": DATA_DATE}
        
        # Screenshot fallback
        print("DOM insufficient, taking screenshot fallback...")
        await send_cmd(ws, 200, "Page.captureScreenshot", {"format": "png", "fromSurface": True})
        resp = await recv_until(ws, 200, timeout=30)
        if resp:
            data = resp.get("result",{}).get("data","")
            if data:
                out = f"/mnt/openclaw/.openclaw/workspace/dbr_screenshot_{DATA_DATE}.png"
                with open(out, "wb") as f:
                    f.write(base64.b64decode(data))
                print(f"Screenshot saved: {out}")
                return {"data_source": "screenshot", "screenshot": out}
        
        return {"error": "no data extracted"}

result = asyncio.run(main())
print(json.dumps(result, ensure_ascii=False, indent=2)[:500])
