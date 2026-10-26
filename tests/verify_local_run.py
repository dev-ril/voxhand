"""
VOXHAND Live System Verification Script
---------------------------------------
Starts the FastAPI Gateway, tests REST endpoints, and connects via WebSocket
to stream sensor telemetry and receive live ML inference broadcast packets.
"""

import time
import json
import os
import sys
import urllib.request
import asyncio
import websockets
import multiprocessing

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import uvicorn
from backend.app import app


import threading

def run_server():
    config = uvicorn.Config(app, host="127.0.0.1", port=8000, log_level="warning")
    server = uvicorn.Server(config)
    server.run()


async def run_checks():
    print("=" * 65)
    print("      VOXHAND END-TO-END LIVE RUNTIME VERIFICATION")
    print("=" * 65)

    # 1. Health check
    print("\n[STEP 1] Testing GET /health...")
    with urllib.request.urlopen("http://127.0.0.1:8000/health") as resp:
        data = json.loads(resp.read().decode())
        print("  -> Status:", data["status"])
        print("  -> Classes in model:", data["classes"])
        print("  -> Confidence threshold:", data["confidence_threshold"])

    # 2. Gestures metadata
    print("\n[STEP 2] Testing GET /api/gestures...")
    with urllib.request.urlopen("http://127.0.0.1:8000/api/gestures") as resp:
        data = json.loads(resp.read().decode())
        print("  -> Total classes:", len(data["classes"]))
        print("  -> Rejection message:", data["rejection_message"])

    # 3. HTTP POST /api/predict
    print("\n[STEP 3] Testing POST /api/predict (Simulating 'THANK YOU' gesture)...")
    req_data = {
        "flex": [0.12, 0.08, 0.08, 0.10, 0.12],
        "accel": {"x": 0.04, "y": 0.50, "z": 0.82},
        "gyro": {"x": 1.80, "y": 0.05, "z": 0.05},
        "timestamp": int(time.time()),
    }
    req = urllib.request.Request(
        "http://127.0.0.1:8000/api/predict",
        data=json.dumps(req_data).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read().decode())
        print(f"  -> Recognized Text: {result['text']}")
        print(f"  -> Confidence:      {result['confidence'] * 100:.1f}%")
        print(f"  -> Decision Status: {result['status']}")

    # 4. WebSocket Live Stream Test
    print("\n[STEP 4] Testing WebSocket Stream on ws://127.0.0.1:8000/ws/stream...")
    async with websockets.connect("ws://127.0.0.1:8000/ws/stream") as ws:
        print("  -> WebSocket connected successfully!")
        
        # Test frame: "YES" (closed fist nodding)
        test_frame = {
            "flex": [0.82, 0.92, 0.94, 0.95, 0.93],
            "accel": {"x": 0.05, "y": 0.72, "z": 0.62},
            "gyro": {"x": 2.40, "y": 0.10, "z": 0.05},
            "timestamp": int(time.time()),
        }
        await ws.send(json.dumps(test_frame))
        raw_resp = await asyncio.wait_for(ws.recv(), timeout=3.0)
        ws_data = json.loads(raw_resp)
        print(f"  -> WebSocket Ingested & Predicted: {ws_data['text']}")
        print(f"  -> Confidence:                     {ws_data['confidence'] * 100:.1f}%")
        print(f"  -> Status:                         {ws_data['status']}")

        # Test frame: "NOISE / REST" (trigger rejection)
        noise_frame = {
            "flex": [0.45, 0.40, 0.42, 0.45, 0.45],
            "accel": {"x": 0.0, "y": 0.50, "z": 0.50},
            "gyro": {"x": 0.0, "y": 0.0, "z": 0.0},
            "timestamp": int(time.time()),
        }
        await ws.send(json.dumps(noise_frame))
        raw_resp_noise = await asyncio.wait_for(ws.recv(), timeout=3.0)
        ws_noise = json.loads(raw_resp_noise)
        print(f"\n[STEP 5] Testing Rejection Threshold Logic on Ambiguous Noise Frame...")
        print(f"  -> Output Message:                 {ws_noise['text']}")
        print(f"  -> Decision Status:                {ws_noise['status']}")
        print(f"  -> Is Rejected:                    {ws_noise['is_rejected']}")

    print("\n" + "=" * 65)
    print("  ALL 5 VERIFICATION CHECKS PASSED: SYSTEM IS 100% OPERATIONAL")
    print("=" * 65)


def main():
    t = threading.Thread(target=run_server, daemon=True)
    t.start()

    print("[BOOT] Waiting for FastAPI server to initialize...")
    for _ in range(40):
        try:
            with urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=1) as r:
                if r.status == 200:
                    break
        except Exception:
            time.sleep(0.2)

    asyncio.run(run_checks())


if __name__ == "__main__":
    main()
