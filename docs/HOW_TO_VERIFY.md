# 🧪 VOXHAND - How to Verify Guide

This document outlines the systematic verification process for **VOXHAND**, ensuring hardware simulation, machine learning inference, confidence rejection gating, REST APIs, WebSockets, and Text-to-Speech (TTS) function as expected.

---

## 1. Automated Unit Test Suite

Run the built-in test suite to verify mathematics, model bounds, inference accuracy, and API endpoints:

```bash
python -m unittest discover tests -v
```

### Expected Output
```text
test_gestures_route (test_pipeline.TestBackendGatewayRoutes.test_gestures_route) ... ok
test_health_route (test_pipeline.TestBackendGatewayRoutes.test_health_route) ... ok
test_predict_route (test_pipeline.TestBackendGatewayRoutes.test_predict_route) ... ok
test_simulate_route (test_pipeline.TestBackendGatewayRoutes.test_simulate_route) ... ok
test_mock_auto_cycle_transitions (test_pipeline.TestMockHardwareStreamer.test_mock_auto_cycle_transitions) ... ok
test_mock_frame_structure (test_pipeline.TestMockHardwareStreamer.test_mock_frame_structure) ... ok
test_inference_gestures (test_pipeline.TestVoxhandMLPipeline.test_inference_gestures) ... ok
test_rejection_logic_on_forced_high_threshold (test_pipeline.TestVoxhandMLPipeline.test_rejection_logic_on_forced_high_threshold) ... ok
test_rejection_logic_on_noise (test_pipeline.TestVoxhandMLPipeline.test_rejection_logic_on_noise) ... ok
test_synthetic_dataset_bounds (test_pipeline.TestVoxhandMLPipeline.test_synthetic_dataset_bounds) ... ok

----------------------------------------------------------------------
Ran 10 tests in ~0.65s

OK
```

### Test Scope Breakdown
| Test Case | Scope & Verification Criteria |
| :--- | :--- |
| `test_synthetic_dataset_bounds` | Validates flex is bounded in $[0.0, 1.0]$, accel in $[-2.0, 2.0]\text{g}$, and gyro in $[-6.0, 6.0]\text{rad/s}$. |
| `test_inference_gestures` | Feeds known biomechanical vectors for all 5 signs; asserts predicted label match, $\ge 70\%$ confidence, and status `CONFIRMED`. |
| `test_rejection_logic_on_noise` | Feeds random resting vectors; asserts status `REJECTED` and rejection alert message. |
| `test_rejection_logic_on_forced_high_threshold` | Tests dynamic threshold adjustments (e.g. $99.99\%$). |
| `test_mock_frame_structure` | Asserts mock telemetry adheres strictly to the ESP32 JSON schema. |
| `test_mock_auto_cycle_transitions` | Verifies dynamic gesture switching in auto-cycle mode. |
| `test_health_route` | Asserts `GET /health` returns HTTP 200 and healthy model status. |
| `test_gestures_route` | Asserts `GET /api/gestures` returns all 6 registered gesture classes. |
| `test_predict_route` | Asserts `POST /api/predict` handles single-frame inference. |
| `test_simulate_route` | Asserts `POST /api/simulate` triggers synthetic frame inference and broadcast. |

---

## 2. Live Runtime Verification Script

To test the entire live stack (spawning the server, connecting WebSockets, ingesting telemetry, and verifying rejection):

```bash
python tests/verify_local_run.py
```

### What It Verifies
1. **Server Initialization:** Binds FastAPI to port 8000 and loads `model.joblib`.
2. **REST Endpoints:** Probes `/health` and `/api/gestures`.
3. **HTTP Inference:** Sends a JSON vector for `THANK YOU` and validates output.
4. **WebSocket Streaming:** Connects to `ws://127.0.0.1:8000/ws/stream`, streams a `YES` frame, and receives the broadcast result.
5. **Rejection Gating:** Streams an ambiguous noise frame and validates that `is_rejected == True`.

---

## 3. Manual Dashboard Verification Checklist

Launch the UI:
```bash
python run_demo.py
```
Open `http://localhost:8000/` and complete the following checks:

### Checklist

- [ ] **Connection Status:**
  - Status pill in the header should display **"Live Stream Connected"** with a green glowing dot and live FPS counter.
- [ ] **Biomechanical Hand Visualizer:**
  - Click `👋 HELLO`: All 5 SVG fingers should extend straight, and flex percentages should read $< 15\%$.
  - Click `✊ YES`: All 5 fingers should curl into a fist, bars turning rose/amber with flex percentages $> 80\%$.
  - Click `👍 HELP`: Thumb should stay extended while the other 4 fingers curl down.
- [ ] **6-DOF Attitude Horizon:**
  - Click `🙏 THANK YOU`: Artificial horizon should pitch forward, and $\text{Accel}_Z$ should increase to $\approx +0.82\text{g}$.
  - Pitch and roll angles update dynamically in degrees.
- [ ] **Text-to-Speech (TTS) Vocalization:**
  - Click any confirmed gesture (`HELLO`, `THANK YOU`, `HELP`, `YES`, `NO`).
  - Browser should vocalize the word clearly via the Web Speech API.
  - Animated teal soundwave bars pulse while audio is playing.
- [ ] **Low-Confidence Auditory & Visual Alert:**
  - Click `⚠️ NOISE / IDLE`.
  - Confidence ring drops or turns amber.
  - Amber warning box appears: *"Unrecognized gesture - please repeat gesture clearly."*
  - An audible double-tone chime sounds via the Web Audio API.
- [ ] **Speech History Log:**
  - Spoken words appear in the right-hand panel with timestamps and confidence scores.
  - Clicking the speaker icon re-vocalizes the phrase.

---

## 4. REST API Endpoint Verification via Curl

You can also test the backend using `curl` or PowerShell:

### Health Check
```bash
curl http://localhost:8000/health
```
```json
{
  "status": "healthy",
  "service": "VOXHAND Gateway",
  "active_clients": 1,
  "classes": ["HELLO", "HELP", "NO", "REST_OR_NOISE", "THANK YOU", "YES"],
  "confidence_threshold": 0.7
}
```

### Manual Inference Request
```bash
curl -X POST http://localhost:8000/api/predict \
  -H "Content-Type: application/json" \
  -d "{\"flex\": [0.12, 0.08, 0.08, 0.10, 0.12], \"accel\": {\"x\": 0.04, \"y\": 0.50, \"z\": 0.82}, \"gyro\": {\"x\": 1.80, \"y\": 0.05, \"z\": 0.05}}"
```
```json
{
  "text": "THANK YOU",
  "predicted_label": "THANK YOU",
  "confidence": 1.0,
  "status": "CONFIRMED",
  "is_rejected": false,
  "threshold": 0.7
}
```

### Trigger Gesture Simulation
```bash
curl -X POST http://localhost:8000/api/simulate \
  -H "Content-Type: application/json" \
  -d "{\"gesture\": \"HELP\"}"
```
