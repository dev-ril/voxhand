"""
VOXHAND Mock ESP32 Hardware Streamer
-----------------------------------
Simulates a physical ESP32 glove sending continuous 25 Hz JSON telemetry packets.
Supports:
  1. Standalone WebSocket Server mode (default on port 8080)
  2. Direct Client Pusher mode (streaming to FastAPI gateway ws://localhost:8000/ws/stream)
  3. Dynamic gesture transitions (Auto-cycle or locked gesture)
  4. Physically accurate noise, micro-tremors, and kinematic oscillations
"""

import sys
import time
import json
import math
import random
import asyncio
import argparse
from typing import Dict, Any, Set
import websockets

# Gesture baseline profiles matching physical glove dynamics
GESTURE_CONFIGS = {
    "HELLO": {
        "description": "Open hand waving side-to-side",
        "flex": [0.08, 0.06, 0.05, 0.06, 0.08],
        "accel": [0.08, 0.94, 0.15],
        "gyro_base": [0.05, 0.05, 0.0],
        "wave_axis": "gyro_z",
        "wave_amp": 2.2,
        "wave_freq": 2.5,
    },
    "THANK YOU": {
        "description": "Flat hand moving forward from chin",
        "flex": [0.12, 0.08, 0.08, 0.10, 0.12],
        "accel": [0.04, 0.50, 0.82],
        "gyro_base": [0.0, 0.05, 0.05],
        "wave_axis": "gyro_x",
        "wave_amp": 1.8,
        "wave_freq": 1.8,
    },
    "HELP": {
        "description": "Thumbs-up resting firmly upright",
        "flex": [0.08, 0.90, 0.93, 0.94, 0.92],
        "accel": [0.05, 0.96, 0.18],
        "gyro_base": [0.06, 0.04, 0.05],
        "wave_axis": None,
        "wave_amp": 0.0,
        "wave_freq": 0.0,
    },
    "YES": {
        "description": "Closed fist nodding up and down",
        "flex": [0.82, 0.92, 0.94, 0.95, 0.93],
        "accel": [0.05, 0.72, 0.62],
        "gyro_base": [0.0, 0.10, 0.05],
        "wave_axis": "gyro_x",
        "wave_amp": 2.5,
        "wave_freq": 2.2,
    },
    "NO": {
        "description": "Index & middle snapping down to pinch thumb",
        "flex": [0.60, 0.72, 0.70, 0.92, 0.93],
        "accel": [0.38, 0.82, 0.32],
        "gyro_base": [0.10, 0.0, 0.35],
        "wave_axis": "gyro_y",
        "wave_amp": 1.9,
        "wave_freq": 3.0,
    },
    "REST_OR_NOISE": {
        "description": "Relaxed hand / low confidence ambiguous motion",
        "flex": [0.45, 0.40, 0.42, 0.45, 0.45],
        "accel": [0.00, 0.50, 0.50],
        "gyro_base": [0.00, 0.00, 0.00],
        "wave_axis": None,
        "wave_amp": 0.3,
        "wave_freq": 0.5,
    },
}

GESTURE_SEQUENCE = ["HELLO", "THANK YOU", "HELP", "YES", "NO", "REST_OR_NOISE"]


class MockESP32Glove:
    """Simulates physical sensor telemetry with realistic biomechanics and noise."""

    def __init__(self, current_gesture: str = "AUTO"):
        self.mode = current_gesture
        self.gesture_index = 0
        self.last_switch_time = time.time()
        self.cycle_interval = 4.0  # seconds per gesture in auto-cycle
        self.t_start = time.time()

    def get_current_gesture_name(self) -> str:
        if self.mode != "AUTO" and self.mode in GESTURE_CONFIGS:
            return self.mode
        # In AUTO mode, rotate through sequence
        elapsed = time.time() - self.last_switch_time
        if elapsed >= self.cycle_interval:
            self.gesture_index = (self.gesture_index + 1) % len(GESTURE_SEQUENCE)
            self.last_switch_time = time.time()
        return GESTURE_SEQUENCE[self.gesture_index]

    def generate_frame(self) -> Dict[str, Any]:
        gesture_name = self.get_current_gesture_name()
        cfg = GESTURE_CONFIGS[gesture_name]
        t = time.time() - self.t_start

        # 1. Flex Sensors with small micro-tremors (noise ~ ±0.015)
        flex_vals = []
        for base_flex in cfg["flex"]:
            noise = random.gauss(0, 0.012)
            tremor = 0.008 * math.sin(12.0 * t + random.random())
            val = round(max(0.0, min(1.0, base_flex + noise + tremor)), 3)
            flex_vals.append(val)

        # 2. Accelerometer (g) with tilt drift
        ax = cfg["accel"][0] + random.gauss(0, 0.015)
        ay = cfg["accel"][1] + random.gauss(0, 0.015)
        az = cfg["accel"][2] + random.gauss(0, 0.015)

        # 3. Gyroscope (rad/s) with dynamic waving / nodding action
        gx = cfg["gyro_base"][0] + random.gauss(0, 0.04)
        gy = cfg["gyro_base"][1] + random.gauss(0, 0.04)
        gz = cfg["gyro_base"][2] + random.gauss(0, 0.04)

        if cfg["wave_axis"] == "gyro_z":
            gz += cfg["wave_amp"] * math.sin(cfg["wave_freq"] * 2 * math.pi * t)
        elif cfg["wave_axis"] == "gyro_x":
            gx += cfg["wave_amp"] * math.sin(cfg["wave_freq"] * 2 * math.pi * t)
        elif cfg["wave_axis"] == "gyro_y":
            gy += cfg["wave_amp"] * math.sin(cfg["wave_freq"] * 2 * math.pi * t)

        return {
            "flex": flex_vals,
            "accel": {
                "x": round(ax, 3),
                "y": round(ay, 3),
                "z": round(az, 3),
            },
            "gyro": {
                "x": round(gx, 3),
                "y": round(gy, 3),
                "z": round(gz, 3),
            },
            "timestamp": int(time.time()),
            "simulated_gesture": gesture_name,  # Informational tag
        }


# -----------------------------------------------------------------------------
# Mode A: Standalone WebSocket Server (Port 8080)
# -----------------------------------------------------------------------------
CONNECTED_CLIENTS: Set[websockets.WebSocketServerProtocol] = set()


async def ws_server_handler(websocket, path, glove: MockESP32Glove):
    CONNECTED_CLIENTS.add(websocket)
    client_addr = websocket.remote_address
    print(f"[MOCK ESP32 SERVER] New subscriber connected: {client_addr}")
    try:
        await websocket.wait_closed()
    finally:
        CONNECTED_CLIENTS.discard(websocket)
        print(f"[MOCK ESP32 SERVER] Subscriber disconnected: {client_addr}")


async def broadcast_loop(glove: MockESP32Glove, fps: int = 25):
    interval = 1.0 / fps
    frame_count = 0
    last_print = time.time()

    while True:
        frame = glove.generate_frame()
        json_data = json.dumps(frame)

        if CONNECTED_CLIENTS:
            # Broadcast to all connected clients
            await asyncio.gather(
                *[client.send(json_data) for client in CONNECTED_CLIENTS],
                return_exceptions=True
            )

        frame_count += 1
        if time.time() - last_print >= 2.0:
            print(
                f"[MOCK STREAM 8080] Active Gesture: {frame['simulated_gesture']:<13} "
                f"| Clients: {len(CONNECTED_CLIENTS)} "
                f"| Flex: {frame['flex']} "
                f"| Accel Y: {frame['accel']['y']:+.2f}"
            )
            last_print = time.time()

        await asyncio.sleep(interval)


async def run_standalone_server(port: int, glove: MockESP32Glove, fps: int):
    print("=" * 70)
    print(f"VOXHAND MOCK ESP32 HARDWARE STREAMER (STANDALONE SERVER)")
    print(f"Streaming realistic telemetry at {fps} Hz on ws://0.0.0.0:{port}")
    print(f"Initial Mode: {glove.mode} (Auto-cycles gestures every {glove.cycle_interval}s)")
    print("=" * 70)

    # Handler wrapper to pass glove instance
    async def handler(ws):
        # Compatible with websockets v11+ and v15+
        CONNECTED_CLIENTS.add(ws)
        print(f"[MOCK SERVER] Client connected from {ws.remote_address}")
        try:
            await ws.wait_closed()
        finally:
            CONNECTED_CLIENTS.discard(ws)
            print(f"[MOCK SERVER] Client disconnected: {ws.remote_address}")

    async with websockets.serve(handler, "0.0.0.0", port):
        await broadcast_loop(glove, fps=fps)


# -----------------------------------------------------------------------------
# Mode B: Direct Client Pusher (Streaming into FastAPI Gateway)
# -----------------------------------------------------------------------------
async def run_client_pusher(target_url: str, glove: MockESP32Glove, fps: int):
    interval = 1.0 / fps
    print("=" * 70)
    print(f"VOXHAND MOCK ESP32 HARDWARE STREAMER (CLIENT PUSHER)")
    print(f"Connecting to Gateway: {target_url}")
    print("=" * 70)

    while True:
        try:
            print(f"[PUSHER] Connecting to {target_url}...")
            async with websockets.connect(target_url) as ws:
                print(f"[PUSHER] Connected successfully! Streaming at {fps} FPS...")
                last_print = time.time()
                while True:
                    frame = glove.generate_frame()
                    await ws.send(json.dumps(frame))

                    if time.time() - last_print >= 2.0:
                        print(
                            f"[PUSHER -> GATEWAY] Gesture: {frame['simulated_gesture']:<13} "
                            f"| Flex: {frame['flex']}"
                        )
                        last_print = time.time()

                    await asyncio.sleep(interval)
        except Exception as e:
            print(f"[PUSHER] Connection error: {e}. Retrying in 2 seconds...")
            await asyncio.sleep(2.0)


# -----------------------------------------------------------------------------
# Entry Point
# -----------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="VOXHAND Mock ESP32 Glove Hardware Streamer")
    parser.add_argument("--port", type=int, default=8080, help="Local WebSocket server port (default: 8080)")
    parser.add_argument("--fps", type=int, default=25, help="Telemetry broadcast frequency (default: 25 Hz)")
    parser.add_argument(
        "--gesture",
        type=str,
        default="AUTO",
        choices=["AUTO", "HELLO", "THANK YOU", "HELP", "YES", "NO", "REST_OR_NOISE"],
        help="Simulate a specific gesture or AUTO to cycle automatically",
    )
    parser.add_argument(
        "--target-gateway",
        type=str,
        default=None,
        help="If specified (e.g. ws://localhost:8000/ws/stream), streams directly to gateway as client instead of running server",
    )
    args = parser.parse_args()

    glove = MockESP32Glove(current_gesture=args.gesture)

    try:
        if args.target_gateway:
            asyncio.run(run_client_pusher(args.target_gateway, glove, args.fps))
        else:
            asyncio.run(run_standalone_server(args.port, glove, args.fps))
    except KeyboardInterrupt:
        print("\n[MOCK STREAMER] Stopped by user.")


if __name__ == "__main__":
    main()

