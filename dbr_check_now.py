#!/usr/bin/env python3
import json, http.client, base64, time, asyncio, websockets

CDP = ("127.0.0.1", 9222)

def cdp_call(method, params=None):
    conn = http.client.HTTPConnection(*CDP)
    body = json.dumps({"id": 1, "method": method, "params": params or {}})
    conn.request("POST", "/json/new?about:blank", body)
    resp = conn.getresponse().read()
    return json.loads(resp)

# Get list
c = http.client.HTTPConnection(*CDP)
c.request("GET", "/json/list")
tabs = json.loads(c.getresponse().read())

# Close any existing bi.keetapp tabs
for t in tabs:
    if 'bi.keetapp' in t.get('url',''):
        tc = http.client.HTTPConnection(*CDP)
        tc.request("GET", f"/json/close/{t['id']}")
        tc.getresponse().read()
        print(f"Closed old tab: {t['id']}")
        time.sleep(1)

# Create new tab
c = http.client.HTTPConnection(*CDP)
c.request("PUT", "/json/new?https://bi.keetapp.com/v2/dashboard/300001446")
new_tab = json.loads(c.getresponse().read())
print(f"New tab: {new_tab.get('id')} | {new_tab.get('url','')[:60]}")

time.sleep(15)

# Screenshot via CDP
ws_url = new_tab.get('webSocketDebuggerUrl')

async def screenshot():
    async with websockets.connect(ws_url) as ws:
        await ws.send(json.dumps({"id": 1, "method": "Page.enable"}))
        await asyncio.sleep(2)
        # drain
        for _ in range(10):
            try: await asyncio.wait_for(ws.recv(), timeout=1)
            except asyncio.TimeoutError: break
        
        await ws.send(json.dumps({"id": 2, "method": "Page.captureScreenshot", "params": {"format": "png", "fromSurface": True}}))
        try:
            r = await asyncio.wait_for(ws.recv(), timeout=15)
            msg = json.loads(r)
            data = msg.get("result",{}).get("data","")
            if data:
                with open("/mnt/openclaw/.openclaw/workspace/dbr_today_status.png", "wb") as f:
                    f.write(base64.b64decode(data))
                print("Screenshot saved")
            else:
                print("No data in screenshot response")
                print(json.dumps(msg, indent=2)[:500])
        except asyncio.TimeoutError:
            print("Screenshot timeout")

asyncio.run(screenshot())

# Close the tab
c = http.client.HTTPConnection(*CDP)
c.request("GET", f"/json/close/{new_tab['id']}")
c.getresponse().read()
print("Tab closed")
