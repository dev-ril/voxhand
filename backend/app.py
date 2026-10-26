"""
VOXHAND Backend Gateway
-----------------------
FastAPI WebSocket and REST gateway for the VOXHAND smart sign language glove.
Ingests live sensor telemetry, runs real-time ML inference, and broadcasts results
(predicted text, confidence score, confirmation status, and raw sensor values)
to connected client web/mobile dashboards.
"""

import os
import sys
import time
import json
import asyncio
from typing import Set, Dict, Any, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from ml_pipeline.inference import get_inference_engine, predict_gesture
from firmware.mock_esp32_streamer import MockESP32Glove

# -----------------------------------------------------------------------------
# Connection Manager for WebSocket Clients
# -----------------------------------------------------------------------------
class ConnectionManager:
    """Manages active WebSocket connections for sensor streamers and UI dashboards."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.total_frames_processed: int = 0
        self.last_inference_time: float = 0.0
        self.last_result: Optional[Dict[str, Any]] = None

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        print(f"[WS GATEWAY] Client connected. Total active clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        print(f"[WS GATEWAY] Client disconnected. Total active clients: {len(self.active_connections)}")

    async def broadcast(self, message: Dict[str, Any]):
        """Broadcasts payload to all currently connected clients."""
        if not self.active_connections:
            return

        dead_connections = set()
        json_str = json.dumps(message)

        for connection in self.active_connections:
            try:
                await connection.send_text(json_str)
            except Exception:
                dead_connections.add(connection)

        for dead in dead_connections:
            self.active_connections.discard(dead)


manager = ConnectionManager()
mock_glove = MockESP32Glove(current_gesture="AUTO")

# -----------------------------------------------------------------------------
# Lifespan / Startup Hook
# -----------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pre-load or initialize ML Model on startup
    print("[BACKEND] Initializing VOXHAND Machine Learning Model...")
    engine = get_inference_engine()
    print(f"[BACKEND] ML Engine ready. Trained classes: {engine.classes}")
    yield
    print("[BACKEND] Shutting down gateway...")


app = FastAPI(
    title="VOXHAND Smart Glove Backend Gateway",
    description="Real-time sensor telemetry ingestion and sign language inference server.",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for cross-origin frontend testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------------------------------------------------
# Pydantic Schemas for REST API
# -----------------------------------------------------------------------------
class TelemetryPayload(BaseModel):
    flex: list[float] = Field(..., description="5 normalized finger flex values [0.0 - 1.0]")
    accel: Dict[str, float] = Field(..., description="3-axis accelerometer values {'x', 'y', 'z'}")
    gyro: Dict[str, float] = Field(..., description="3-axis gyroscope values {'x', 'y', 'z'}")
    timestamp: Optional[int] = Field(default_factory=lambda: int(time.time()))


class SimulateRequest(BaseModel):
    gesture: str = Field(default="HELLO", description="Gesture name to simulate (HELLO, THANK YOU, HELP, YES, NO, REST_OR_NOISE)")


# -----------------------------------------------------------------------------
# REST Endpoints
# -----------------------------------------------------------------------------
@app.get("/health")
async def health_check():
    """Health check and gateway status."""
    engine = get_inference_engine()
    return {
        "status": "healthy",
        "service": "VOXHAND Gateway",
        "active_clients": len(manager.active_connections),
        "total_frames_processed": manager.total_frames_processed,
        "classes": engine.classes,
        "confidence_threshold": 0.70,
        "last_result": manager.last_result,
    }


@app.get("/api/gestures")
async def list_gestures():
    """Returns the list of supported gestures and feature specifications."""
    engine = get_inference_engine()
    return {
        "classes": engine.classes,
        "metadata": engine.metadata,
        "confidence_threshold": 0.70,
        "rejection_message": "Unrecognized gesture - please repeat gesture clearly.",
    }


@app.post("/api/predict")
async def predict_single_frame(payload: TelemetryPayload):
    """Executes single-frame inference via HTTP POST."""
    sensor_dict = payload.model_dump()
    result = predict_gesture(sensor_dict)
    manager.total_frames_processed += 1
    manager.last_result = result

    # Also broadcast to active UI connections so dashboard reflects manual POST
    broadcast_data = {
        "type": "INFERENCE_RESULT",
        "text": result["text"],
        "confidence": result["confidence"],
        "status": result["status"],
        "is_rejected": result["is_rejected"],
        "predicted_label": result["predicted_label"],
        "threshold": result["threshold"],
        "probabilities": result["probabilities"],
        "raw_sensor": sensor_dict,
    }
    await manager.broadcast(broadcast_data)
    return result


@app.post("/api/simulate")
async def simulate_gesture(request: SimulateRequest):
    """Generates a synthetic telemetry frame for the requested gesture, runs inference, and broadcasts."""
    gesture_name = request.gesture.upper()
    temp_glove = MockESP32Glove(current_gesture=gesture_name)
    frame = temp_glove.generate_frame()
    result = predict_gesture(frame)

    manager.total_frames_processed += 1
    manager.last_result = result

    broadcast_data = {
        "type": "INFERENCE_RESULT",
        "text": result["text"],
        "confidence": result["confidence"],
        "status": result["status"],
        "is_rejected": result["is_rejected"],
        "predicted_label": result["predicted_label"],
        "threshold": result["threshold"],
        "probabilities": result["probabilities"],
        "raw_sensor": frame,
    }
    await manager.broadcast(broadcast_data)
    return {
        "simulation": frame,
        "inference": result,
    }


# -----------------------------------------------------------------------------
# WebSocket Telemetry Streaming Endpoint (/ws/stream & /ws/ui)
# -----------------------------------------------------------------------------
async def handle_websocket_session(websocket: WebSocket, client_type: str = "GENERIC"):
    await manager.connect(websocket)
    try:
        while True:
            raw_text = await websocket.receive_text()
            try:
                data = json.loads(raw_text)
            except json.JSONDecodeError:
                continue

            msg_type = data.get("type", "TELEMETRY")

            # Handle mock trigger command from dashboard
            if msg_type == "SIMULATE_COMMAND":
                req_gesture = data.get("gesture", "HELLO")
                temp_glove = MockESP32Glove(current_gesture=req_gesture)
                sim_frame = temp_glove.generate_frame()
                res = predict_gesture(sim_frame)
                manager.total_frames_processed += 1
                manager.last_result = res

                await manager.broadcast({
                    "type": "INFERENCE_RESULT",
                    "text": res["text"],
                    "confidence": res["confidence"],
                    "status": res["status"],
                    "is_rejected": res["is_rejected"],
                    "predicted_label": res["predicted_label"],
                    "threshold": res["threshold"],
                    "probabilities": res["probabilities"],
                    "raw_sensor": sim_frame,
                })
                continue

            # Standard telemetry frame received from ESP32 or mock streamer
            if "flex" in data:
                res = predict_gesture(data)
                manager.total_frames_processed += 1
                manager.last_result = res
                manager.last_inference_time = time.time()

                out_packet = {
                    "type": "INFERENCE_RESULT",
                    "text": res["text"],
                    "confidence": res["confidence"],
                    "status": res["status"],
                    "is_rejected": res["is_rejected"],
                    "predicted_label": res["predicted_label"],
                    "threshold": res["threshold"],
                    "probabilities": res["probabilities"],
                    "raw_sensor": {
                        "flex": data.get("flex", []),
                        "accel": data.get("accel", {}),
                        "gyro": data.get("gyro", {}),
                        "timestamp": data.get("timestamp", int(time.time())),
                    },
                }

                # Broadcast to all connected web dashboards
                await manager.broadcast(out_packet)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"[WS GATEWAY] Unexpected error: {e}")
        manager.disconnect(websocket)


@app.websocket("/ws/stream")
async def websocket_stream_endpoint(websocket: WebSocket):
    """Primary telemetry stream endpoint for ESP32 and mock streamer."""
    await handle_websocket_session(websocket, client_type="STREAMER")


@app.websocket("/ws/ui")
async def websocket_ui_endpoint(websocket: WebSocket):
    """Dedicated dashboard listener endpoint."""
    await handle_websocket_session(websocket, client_type="DASHBOARD")


# -----------------------------------------------------------------------------
# Static File Dashboard Serving
# -----------------------------------------------------------------------------
frontend_dir = os.path.join(PROJECT_ROOT, "frontend")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

    @app.get("/")
    async def serve_index():
        index_file = os.path.join(frontend_dir, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return {"message": "VOXHAND Gateway is running. Frontend index.html not found."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app:app", host="0.0.0.0", port=8000, reload=True)

