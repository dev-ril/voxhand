# 🗺️ VOXHAND - Project Status, Pending Items & Engineering Roadmap

This document outlines the current state of the **VOXHAND** prototype, detailing what is **fully implemented and verified** versus what remains **pending for future hardware iterations and production scaling**.

---

## ✅ 1. Completed & Fully Verified in Current Prototype

| Component | Status | Implementation Details |
| :--- | :--- | :--- |
| **Embedded Firmware** | **COMPLETE** | `voxhand_firmware.ino` reads 5 flex sensors on ADC1, MPU6050 via I2C, normalizes raw values to percentages ($0.0 - 1.0$), executes a 5-second dynamic calibration routine, packages JSON telemetry, and streams over WebSockets. |
| **Hardware Simulation** | **COMPLETE** | `mock_esp32_streamer.py` generates synthetic telemetry with micro-tremors, Gaussian noise, and dynamic rotational drift at 25 Hz; supports standalone server mode (port 8080) and gateway pusher mode. |
| **ML Training Pipeline** | **COMPLETE** | `train_model.py` generates physically grounded datasets across 5 signs + noise, trains a calibrated Random Forest classifier ($100\%$ test accuracy), and serializes `model.joblib`. |
| **Inference Engine** | **COMPLETE** | `inference.py` processes raw vectors in $< 5\text{ms}$, computes confidence scores, and strictly enforces the $70\%$ confidence rejection threshold. |
| **Backend Gateway** | **COMPLETE** | FastAPI server (`app.py`) provides real-time WebSocket ingestion (`/ws/stream`), client broadcast (`/ws/ui`), REST endpoints (`/health`, `/api/gestures`, `/api/predict`, `/api/simulate`), and static dashboard serving. |
| **Interactive Dashboard**| **COMPLETE** | Responsive dark-mode dashboard featuring an animated SVG hand visualizer, 6-DOF IMU artificial horizon, large typography speech box, radial confidence meter, and manual slider testing lab. |
| **Text-to-Speech (TTS)** | **COMPLETE** | Browser-native vocalization via the Web Speech API (`window.speechSynthesis`) with debouncing and active soundwave visualizers. |
| **Audible & Visual Alerts**| **COMPLETE** | Low-confidence gestures trigger an amber visual warning and an audible dual-tone chime generated via the Web Audio API. |
| **Automated Test Suite** | **COMPLETE** | 10 comprehensive unit tests passing in `tests/test_pipeline.py` plus end-to-end integration check in `tests/verify_local_run.py`. |

---

## ⏳ 2. Pending Items & Future Engineering Roadmap

While the digital prototype, backend, machine learning pipeline, and simulation systems are 100% complete, the following engineering tasks are planned for future physical hardware revisions:

### Phase 2: Physical Hardware & Glove Prototyping (Pending Physical Assembly)
- [ ] **Physical Glove Assembly:** Stitching flex sensor pockets onto a breathable athletic glove substrate and mounting the 5 Spectra Symbol flex sensors.
- [ ] **Custom PCB / Flex-PCB Fabrication:** Design a compact custom PCB or Flexible Printed Circuit (FPC) shield for the ESP32 DevKit to replace breadboard jumper wires.
- [ ] **3D-Printed Enclosure:** Design an ergonomic, lightweight wrist-mount enclosure (STL format) to house the ESP32, MPU6050, and wiring harness.
- [ ] **Battery & Power Circuitry:** Integrate a 3.7V 500mAh LiPo rechargeable battery, a TP4056 charging module, and a power switch.
- [ ] **ESP32 Power Optimization:** Implement light-sleep and dynamic CPU frequency scaling (down to 80 MHz) to extend battery life beyond 8 hours of continuous transmission.

### Phase 3: Wireless Communication Enhancements
- [ ] **BLE (Bluetooth Low Energy) Firmware Mode:** Implement a secondary firmware variant using BLE Nordic UART Service (NUS) or custom GATT profile to pair directly with iOS/Android mobile apps without requiring a local WiFi network.
- [ ] **ESP-NOW Mesh Protocol:** Explore ultra-low-latency ESP-NOW protocol for direct ESP32-to-ESP32 receiver dongle communication.

### Phase 4: Machine Learning & Vocabulary Expansion
- [ ] **Temporal Time-Series Model (1D-CNN + LSTM / GRU):** The current prototype classifies static gesture states frame-by-frame. Upgrading to a sliding temporal window classifier will enable recognition of continuous, multi-stage dynamic signs (e.g. signs involving compound motions like waving, slicing, or circling).
- [ ] **ASL Alphabet Expansion:** Expand training dataset from the 5 core emergency phrases (`HELLO`, `THANK YOU`, `HELP`, `YES`, `NO`) to the complete 26-letter American Sign Language (ASL) fingerspelling alphabet.
- [ ] **Two-Hand (Bimanual) Support:** Many complex sign language gestures require both hands. Extend backend telemetry schema to aggregate synchronized data streams from two gloves (Left Hand + Right Hand).
- [ ] **On-Device TinyML Inference:** Compile the trained model using TensorFlow Lite for Microcontrollers (TFLM) to run inference directly on the ESP32 microcontroller, outputting audio directly via an onboard I2S DAC and mini speaker.

---

## 📊 Summary Comparison: Prototype vs. Production Vision

| Feature | VOXHAND Prototype (Current) | Production Hardware (Roadmap) |
| :--- | :--- | :--- |
| **Gesture Vocabulary** | 5 Core Signs + Rest/Noise Baseline | Full ASL Alphabet + 100 Common Phrases |
| **Model Architecture** | Calibrated Random Forest ($< 5\text{ms}$) | 1D-CNN + BiLSTM (Continuous Sequence) |
| **Data Ingestion** | WiFi WebSockets + Mock Streamer | WiFi + BLE GATT + ESP-NOW |
| **Audio Output** | Web Speech API (Client Browser) | Web Speech API + Onboard I2S Speaker |
| **Hardware Form Factor**| ESP32 DevKit + Breadboard / Mock | Custom Wrist Enclosure + LiPo Battery |
| **Operating Mode** | Real-Time Telemetry Streaming | Autonomous Edge Device + Web Companion |

