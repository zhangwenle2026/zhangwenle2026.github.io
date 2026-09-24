#!/usr/bin/env python3
import json, http.client, base64, time, asyncio, websockets

CDP = ("127.0.0.1", 9222)

# Create new tab with longer wait
c = http.client.HTTPConnection(*CDP)
c.request("PUT", "/json/new?https://bi.keetapp.com/v2/dashboard/300001446")
new_tab = json.loads(c.getresponse().read())
print(f"New tab: {new_tab.get('id')}")

# Wait longer for data to load
time.sleep(45)

ws_url = new_tab.get('webSocketDebuggerUrl')

async def screenshot():
    async with websockets.connect(ws_url) as ws:
        await ws.send(json.dumps({"id": 1, "method": "Page.enable"}))
        await asyncio.sleep(2)
        for _ in range(10):
            try: await asyncio.wait_for(ws.recv(), timeout=1)
            except asyncio.TimeoutError: break
        
        await ws.send(json.dumps({"id": 2, "method": "Page.captureScreenshot", "params": {"format": "png", "fromSurface": True}}))
        try:
            r = await asyncio.wait_for(ws.recv(), timeout=15)
            msg = json.loads(r)
            data = msg.get("result",{}).get("data","")
            if data:
                with open("/mnt/openclaw/.openclaw/workspace/dbr_today_loaded.png", "wb") as f:
                    f.write(base64.b64decode(data))
                print("Screenshot saved")
            else:
                print("No data")
        except asyncio.TimeoutError:
            print("Timeout")

asyncio.run(screenshot())

# Close
c = http.client.HTTPConnection(*CDP)
c.request("GET", f"/json/close/{new_tab['id']}")
c.getresponse().read()
print("Done")
