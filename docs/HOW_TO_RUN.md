# 🚀 VOXHAND - How to Run Guide

This guide details all execution modes for the **VOXHAND** smart sign language glove system, covering zero-hardware mock testing, modular service launching, and physical hardware deployment.

---

## ⚡ Mode 1: Fast-Track Unified Demo (Recommended)

The easiest way to launch the entire system with zero hardware setup:

```bash
# From the project root directory:
python run_demo.py
```

### What this does automatically:
1. **Checks ML Model:** Ensures `ml_pipeline/model.joblib` exists; if not, trains it automatically in ~3 seconds.
2. **Starts Backend Gateway:** Launches FastAPI and WebSocket ingestion on `http://localhost:8000`.
3. **Serves Web Companion Dashboard:** Mounts the interactive HTML5/Tailwind dashboard at `http://localhost:8000/`.
4. **Launches Browser:** Automatically opens your default web browser to the dashboard.

---

## 🧩 Mode 2: Modular Multi-Terminal Execution

For development, debugging, or custom network setups, you can run the components in independent terminal windows.

### Terminal 1: Backend Gateway & Web Server
```bash
# Option A (Standard uvicorn):
uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload

# Option B (Python module launcher):
python -m backend.app
```
- Gateway URL: `http://localhost:8000`
- Telemetry Ingestion WebSocket: `ws://localhost:8000/ws/stream`
- Dashboard Listener WebSocket: `ws://localhost:8000/ws/ui`
- Interactive API Docs (Swagger): `http://localhost:8000/docs`

---

### Terminal 2: Synthetic Hardware Streamer

Simulates the physical glove sending continuous 25 Hz telemetry packets over WiFi WebSockets.

#### A. Gateway Pusher Mode (Streams directly into FastAPI backend)
```bash
python firmware/mock_esp32_streamer.py --target-gateway ws://localhost:8000/ws/stream
```
- Automatically rotates through all 5 gestures + noise every 4 seconds.
- Telemetry updates the dashboard in real time at 25 FPS.

#### B. Standalone Server Mode (Streams on port 8080)
```bash
python firmware/mock_esp32_streamer.py --port 8080
```
- Runs an independent WebSocket server on `ws://0.0.0.0:8080`.
- In the dashboard, enter `ws://localhost:8080` in the top connection bar and click **Connect**.

#### C. Locking to a Specific Gesture
```bash
# Continuously stream "THANK YOU" only:
python firmware/mock_esp32_streamer.py --target-gateway ws://localhost:8000/ws/stream --gesture "THANK YOU"

# Continuously stream "HELP":
python firmware/mock_esp32_streamer.py --target-gateway ws://localhost:8000/ws/stream --gesture "HELP"

# Continuously stream "REST_OR_NOISE" to test rejection:
python firmware/mock_esp32_streamer.py --target-gateway ws://localhost:8000/ws/stream --gesture "REST_OR_NOISE"
```

---

## 🖐️ Mode 3: Physical ESP32 Hardware Deployment

When deploying to physical glove hardware:

### 1. Identify Your Computer's Local IP Address
- **Windows (PowerShell):** `ipconfig` &rarr; look for IPv4 Address (e.g. `192.168.1.100`)
- **macOS / Linux:** `ifconfig` or `ip a`

### 2. Configure Firmware
Open `firmware/voxhand_firmware.ino` in the Arduino IDE and update lines 46-50:
```cpp
const char* WIFI_SSID     = "Your_WiFi_Network_Name";
const char* WIFI_PASSWORD = "Your_WiFi_Password";
const char* WS_HOST       = "192.168.1.100";  // IP of computer running backend
const int   WS_PORT       = 8000;
const char* WS_PATH       = "/ws/stream";
```

### 3. Flash to ESP32
1. Connect ESP32 DevKit to computer via micro-USB.
2. In Arduino IDE: **Tools &rarr; Board &rarr; esp32 &rarr; ESP32 Dev Module**.
3. Select the active COM port under **Tools &rarr; Port**.
4. Click **Upload**.

### 4. Calibration & Streaming
1. Open the Serial Monitor at **115200 baud**.
2. On boot, the onboard LED blinks rapidly for **5 seconds** during the dynamic calibration routine.
3. Open and close your hand fully several times to register minimum and maximum flex resistance.
4. Once connected to WiFi, the glove streams live packets to `http://<YOUR_IP>:8000/ws/stream`.

---

## 🎛️ Dashboard Navigation & Controls

| Component | How to Use |
| :--- | :--- |
| **Stream URL Bar** | Set connection URL (`ws://localhost:8000/ws/stream` or `ws://localhost:8080`) and click **Connect**. |
| **TTS Toggle** | Click **TTS Active / Muted** to enable or mute browser speech synthesis. |
| **Quick Gesture Triggers** | Click `👋 HELLO`, `🙏 THANK YOU`, `👍 HELP`, `✊ YES`, `👌 NO`, or `⚠️ NOISE` for instant packet emission. |
| **Auto-Cycle Demo** | Click **Start Auto-Cycle Demo** to loop through all signs every 3.5 seconds with live audio. |
| **Manual Sensor Sliders** | Expand "Manual Sensor Overrides" to drag flex strain and tilt angle, then click **Send Manual Frame**. |
| **History Log** | Displays previously spoken signs; click the speaker icon next to any entry to vocalize it again. |

---

## ❓ Troubleshooting

### Port 8000 Already in Use
If port 8000 is occupied by another application, launch with a custom port:
```bash
python run_demo.py --port 8080
# or
uvicorn backend.app:app --port 8080
```

### Browser Text-to-Speech Not Vocalizing
1. Modern browsers require **one user interaction** (e.g. clicking anywhere on the page) before allowing audio playback.
2. Ensure system volume is unmuted and the **TTS Active** button in the dashboard header is teal.

### WebSocket Disconnected
- Verify that the backend gateway is running in your terminal.
- Check that the URL in the dashboard matches `ws://localhost:8000/ws/stream`.
