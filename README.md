# 🖐️ VOXHAND: AI-Powered Smart Sign Language Glove Prototype

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-teal.svg)](https://fastapi.tiangolo.com/)
[![scikit-learn](https://img.shields.io/badge/scikit--learn-1.3+-orange.svg)](https://scikit-learn.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**VOXHAND** is an end-to-end cybernetic assistive glove system that translates physical sign language gestures into real-time speech and high-contrast text. It combines embedded sensor fusion, lightweight machine learning classification, and an accessible Web Companion Dashboard featuring real-time Text-to-Speech (TTS).

---

## 📑 Architecture Overview

```mermaid
flowchart LR
    subgraph Hardware [Physical Glove Hardware / Simulation]
        FLEX["5x Flex Sensors<br/>(Thumb to Pinky, ADC1)"]
        IMU["6-DOF IMU (MPU6050)<br/>(Accel + Gyroscope, I2C)"]
        ESP32["ESP32 Microcontroller<br/>(25 Hz Telemetry Packager)"]
        MOCK["Mock ESP32 Streamer<br/>(Python Synthetic Hardware)"]
        FLEX --> ESP32
        IMU --> ESP32
    end

    subgraph Backend [Backend Gateway (FastAPI)]
        WS["WebSocket Gateway<br/>(/ws/stream & /ws/ui)"]
        ML["ML Pipeline (Random Forest)<br/>(11-Dim Vector Inference)"]
        REJECT["Confidence Gate<br/>(Threshold >= 70%)"]
        WS --> ML --> REJECT
    end

    subgraph Companion [Interactive Web Companion]
        DASH["Live Hand Visualizer<br/>(Dynamic SVG + Flex Bars)"]
        HORIZON["6-DOF Attitude Horizon<br/>(Pitch & Roll Display)"]
        TTS["Web Speech TTS Engine<br/>(SpeechSynthesis Vocalizer)"]
        ALERT["Visual & Audio Nudge<br/>(Low-Confidence Alerts)"]
    end

    ESP32 -.->|JSON over WebSocket| WS
    MOCK -.->|Synthetic Frames (25 Hz)| WS
    REJECT --> DASH
    REJECT --> HORIZON
    REJECT --> TTS
    REJECT --> ALERT
```

---

## 📂 Monorepo Structure

```text
voxhand/
├── firmware/
│   ├── voxhand_firmware.ino      # ESP32 C++ Arduino sketch (ADC + I2C + WebSockets)
│   ├── mock_esp32_streamer.py    # Fallback synthetic hardware streamer (port 8080 & pusher)
│   └── README.md                 # Pinout schematic, ADC1 rules, and calibration guide
├── ml_pipeline/
│   ├── __init__.py
│   ├── train_model.py            # Physically grounded synthetic dataset & model training
│   ├── inference.py              # Real-time inference engine & 0.70 confidence threshold
│   ├── model.joblib              # Serialized high-accuracy Random Forest classifier
│   └── model_metadata.json       # Feature mappings, class definitions, and metadata
├── backend/
│   ├── __init__.py
│   ├── app.py                    # FastAPI server (WebSockets, REST API, Static Web Server)
│   └── requirements.txt          # Python dependencies
├── frontend/
│   ├── index.html                # High-contrast accessible dashboard (Tailwind + Lucide)
│   ├── app.js                    # SVG hand animator, IMU horizon, Web Speech TTS, WebSockets
│   └── styles.css                # Glowing indicators, soundwave animations, cybernetic styles
├── tests/
│   ├── __init__.py
│   └── test_pipeline.py          # Complete unit test suite (ML, routes, streamer schema)
├── run_demo.py                   # One-command runner for instant testing
└── README.md                     # Top-level documentation
```

---

## ⚡ Quickstart (Zero-Hardware Demo Mode)

You can launch and test the entire system on your computer immediately without ESP32 hardware connected.

### 1. Install Dependencies
```bash
pip install -r backend/requirements.txt
```

### 2. Launch the Unified Demo
```bash
python run_demo.py
```
This automatically:
- Verifies/trains the Random Forest model (`ml_pipeline/model.joblib`).
- Starts the FastAPI Backend on `http://localhost:8000`.
- Automatically opens the **Interactive Web Companion Dashboard** in your browser.

### 3. Stream Synthetic Glove Telemetry
To simulate continuous hardware streaming, open a second terminal and run:
```bash
# Push realistic 25 Hz telemetry directly into the gateway:
python firmware/mock_esp32_streamer.py --target-gateway ws://localhost:8000/ws/stream
```
*The glove will begin auto-cycling through gestures (`HELLO`, `THANK YOU`, `HELP`, `YES`, `NO`, `REST_OR_NOISE`) with real-time speech synthesis!*

Alternatively, you can test gestures directly from the Web Dashboard using the **Interactive Simulation Buttons** or **Manual Sensor Sliders**.

---

## 🖐️ Embedded Glove Hardware (`firmware/`)

### Wiring Specifications

| Component | ESP32 Pin | Function | Wiring Details |
| :--- | :--- | :--- | :--- |
| **Thumb Flex** | `GPIO 36` (VP) | ADC1_CH0 | 10kΩ pulldown resistor to GND |
| **Index Flex** | `GPIO 39` (VN) | ADC1_CH3 | 10kΩ pulldown resistor to GND |
| **Middle Flex** | `GPIO 34` | ADC1_CH6 | 10kΩ pulldown resistor to GND |
| **Ring Flex** | `GPIO 35` | ADC1_CH7 | 10kΩ pulldown resistor to GND |
| **Pinky Flex** | `GPIO 32` | ADC1_CH4 | 10kΩ pulldown resistor to GND |
| **MPU6050 SDA** | `GPIO 21` | I2C Data | Direct 3.3V connection |
| **MPU6050 SCL** | `GPIO 22` | I2C Clock | Direct 3.3V connection |
| **MPU6050 VCC/GND** | `3.3V` / `GND` | Power | Connect to ESP32 3.3V rail & GND |
| **Status LED** | `GPIO 2` | Digital Out | Onboard blue LED |
| **Calib Button** | `GPIO 0` | Input Pullup | Onboard `BOOT` button |

> ⚠️ **Important ESP32 ADC Channel Note:**  
> All 5 flex sensors are wired to **ADC1** pins (`GPIO 32-39`). On the ESP32, ADC2 cannot be used while the WiFi radio is transmitting.

### Telemetry Packet Format (JSON)
Transmitted at 25 Hz (every 40 ms) over WebSocket:
```json
{
  "flex": [0.12, 0.08, 0.08, 0.10, 0.12],
  "accel": {"x": 0.04, "y": 0.50, "z": 0.82},
  "gyro": {"x": 1.80, "y": 0.05, "z": 0.05},
  "timestamp": 1714523456
}
```

### Dynamic 5-Second Flex Calibration
On startup (or by pressing the `BOOT` button), the firmware initiates a 5-second calibration window where the user flexes and relaxes their hand. The minimum and maximum raw 12-bit ADC values ($0 - 4095$) are captured per finger, normalizing the output to a clean percentage ($0.0 - 1.0$):
$$\text{Normalized Flex} = \text{clip}\left(\frac{\text{raw} - \text{min}}{\text{max} - \text{min}}, 0.0, 1.0\right)$$

---

## 🧠 Machine Learning Pipeline (`ml_pipeline/`)

### Biomechanical Gesture Profiles

The model classifies 5 primary sign language gestures + an uncalibrated noise/resting class based on physical constraints:

1. **`HELLO` (Open Palm / Waving)**:
   - Hand open (all 5 fingers straight, flex $\approx 0.05 - 0.10$).
   - Hand upright ($\text{Accel}_Y \approx 0.94\text{g}$).
   - Lateral waving motion ($\text{Gyro}_Z$ oscillation $\approx \pm 2.2\text{ rad/s}$).
2. **`THANK YOU` (Chin Outward Flat Palm)**:
   - All fingers extended flat (flex $\approx 0.08 - 0.12$).
   - Hand pitched forward ($\text{Accel}_Z \approx 0.82\text{g}$, $\text{Accel}_Y \approx 0.50\text{g}$).
   - Forward tilt rotational impulse ($\text{Gyro}_X \approx 1.8\text{ rad/s}$).
3. **`HELP` (Thumbs-Up Pose)**:
   - Thumb extended straight (flex $\approx 0.08$).
   - 4 fingers curled into a fist (flex $\approx 0.90 - 0.94$).
   - Thumb pointing vertically upward ($\text{Accel}_Y \approx 0.96\text{g}$).
4. **`YES` (Nodding Closed Fist)**:
   - All 5 fingers curled into a tight fist (flex $\approx 0.82 - 0.95$).
   - Rhythmic up-and-down nodding motion ($\text{Gyro}_X$ oscillation $\approx \pm 2.4\text{ rad/s}$).
5. **`NO` (Index & Middle Pinching Thumb)**:
   - Thumb, Index, and Middle snap together (flex $\approx 0.60 - 0.72$).
   - Ring and Pinky curled back (flex $\approx 0.92$).
   - Rapid snapping rotational rate ($\text{Gyro}_Y \approx 1.75\text{ rad/s}$).
6. **`REST_OR_NOISE` (Idle / Transition)**:
   - Ambiguous intermediate flex values and random orientations.

### Confidence Rejection Threshold
```python
if confidence < 0.70 or predicted_label == "REST_OR_NOISE":
    status = "REJECTED"
    text = "Unrecognized gesture - please repeat gesture clearly."
else:
    status = "CONFIRMED"
    text = predicted_label
```

To retrain the model at any time:
```bash
python ml_pipeline/train_model.py --samples 1500
```

---

## 🌐 Web Companion Dashboard (`frontend/`)

The dashboard provides a high-fidelity assistive communication terminal:

- **Biomechanical SVG Hand Model:** Features 5 independently animated finger bones that dynamically flex and curl in response to normalized sensor readings, with strain-responsive color grading.
- **6-DOF Artificial Horizon:** Visualizes real-time pitch and roll attitude tilt computed from the accelerometer and gyroscope.
- **High-Contrast Speech Box:** Large, accessible typography displaying recognized text with animated soundwave visualizers.
- **Text-to-Speech (TTS):** Browser-native vocalization via the Web Speech API (`window.speechSynthesis`) with automatic debouncing to prevent voice stuttering.
- **Low-Confidence Audio & Visual Nudge:** Triggers an audible dual-tone chime (Web Audio API) and an animated amber alert banner when confidence drops below $70\%$.
- **Hardware Simulation Lab:** Built-in buttons and sliders allow manual parameter testing and automated cycling directly from the browser.

---

## 🧪 Running the Test Suite

Run the full automated test suite covering ML bounds, inference, rejection thresholds, mock streamers, and FastAPI REST endpoints:

```bash
python -m unittest discover tests -v
```

Output:
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
Ran 10 tests in 0.652s

OK
```

---

## 🔌 REST & WebSocket API Reference

| Endpoint | Method / Protocol | Description |
| :--- | :--- | :--- |
| `ws://localhost:8000/ws/stream` | WebSocket | Primary live stream for ESP32 and mock hardware |
| `ws://localhost:8000/ws/ui` | WebSocket | Dedicated listener for companion dashboards |
| `GET /health` | HTTP GET | Gateway health, loaded model classes, active clients |
| `GET /api/gestures` | HTTP GET | Registered gestures, feature vector list, thresholds |
| `POST /api/predict` | HTTP POST | Run inference on a manual JSON sensor packet |
| `POST /api/simulate` | HTTP POST | Generate a synthetic frame for a gesture and broadcast |
| `GET /` | HTTP GET | Serves the interactive companion web dashboard |

---

## 📄 License
This project is open-source under the MIT License.

