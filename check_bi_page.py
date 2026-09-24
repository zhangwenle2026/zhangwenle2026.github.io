#!/usr/bin/env python3
import asyncio
import json
import websockets

WS_URL = "ws://127.0.0.1:9222/devtools/page/47DD593784802B11FBF1348C3410BFF8"

async def main():
    print("Connecting...")
    ws = await websockets.connect(WS_URL)
    print("Connected")
    
    # Send Runtime.enable
    await ws.send(json.dumps({"id": 1, "method": "Runtime.enable"}))
    msg = await asyncio.wait_for(ws.recv(), timeout=10)
    print(f"Runtime.enable response: {msg[:200]}")
    
    # Evaluate expression
    expr = "typeof window.DashboardController !== 'undefined'"
    await ws.send(json.dumps({"id": 2, "method": "Runtime.evaluate", "params": {"expression": expr, "returnByValue": True}}))
    msg = await asyncio.wait_for(ws.recv(), timeout=10)
    data = json.loads(msg)
    print(f"Evaluate result: {json.dumps(data, indent=2)[:500]}")
    
    await ws.close()

asyncio.run(main())
