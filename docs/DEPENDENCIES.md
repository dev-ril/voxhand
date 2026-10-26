# 📦 VOXHAND - Software & Hardware Dependencies

This document provides a comprehensive inventory of all runtimes, packages, browser APIs, and hardware components required to operate the **VOXHAND** prototype on any machine.

---

## 💻 1. Host Machine Software Requirements

### Supported Operating Systems
- **Windows:** Windows 10 / 11 (64-bit)
- **macOS:** macOS Monterey, Ventura, Sonoma, Sequoia (Intel & Apple Silicon)
- **Linux:** Ubuntu 20.04+, Debian 11+, Fedora 36+, Arch Linux

### Python Runtime
- **Required:** Python **3.10**, **3.11**, or **3.12**
- Ensure `pip` and `venv` are installed:
  ```bash
  python --version
  pip --version
  ```

---

## 🐍 2. Python Packages

All Python dependencies are listed in [backend/requirements.txt](file:///d:/Work/Personal/voxhand/backend/requirements.txt):

```text
fastapi>=0.110.0
uvicorn>=0.28.0
scikit-learn>=1.3.0
joblib>=1.3.0
numpy>=1.24.0
websockets>=12.0
```

### Dependency Breakdown
| Package | Version | Purpose |
| :--- | :--- | :--- |
| **`fastapi`** | `>= 0.110.0` | High-throughput asynchronous REST gateway and WebSocket server. |
| **`uvicorn`** | `>= 0.28.0` | Production-grade ASGI web server handling HTTP and WebSocket protocol connections. |
| **`scikit-learn`** | `>= 1.3.0` | Random Forest model training, feature normalization, probability calibration, and metrics. |
| **`joblib`** | `>= 1.3.0` | High-efficiency compression and serialization for `model.joblib`. |
| **`numpy`** | `>= 1.24.0` | Vectorized numerical operations, synthetic drift generation, and telemetry parsing. |
| **`websockets`** | `>= 12.0` | WebSocket client/server networking for `mock_esp32_streamer.py`. |

### Installation Command
```bash
pip install -r backend/requirements.txt
```

---

## 🌐 3. Frontend & Browser Requirements

The **VOXHAND Web Companion Dashboard** uses a **zero-install architecture**. No Node.js, npm, webpack, or Vite builds are needed.

### Browser APIs Utilized
- **Web Speech API (`window.speechSynthesis`):** Provides native, multi-language Text-to-Speech vocalization without external paid cloud APIs.
- **Web Audio API (`window.AudioContext`):** Generates real-time synthetic audible alert chimes for low-confidence gestures without audio files.
- **WebSocket API (`window.WebSocket`):** High-frequency (25-50 Hz) bidirectional telemetry communication with $< 5\text{ms}$ latency.
- **SVG Animation:** Real-time 2D matrix transformation for the biomechanical hand model.

### Browser Compatibility
| Browser | Version | Web Speech API | Web Audio API | WebSockets |
| :--- | :--- | :--- | :--- | :--- |
| **Google Chrome** | `80+` | ✅ Full Support | ✅ Full Support | ✅ Full Support |
| **Microsoft Edge** | `80+` | ✅ Full Support | ✅ Full Support | ✅ Full Support |
| **Apple Safari** | `14+` | ✅ Supported | ✅ Full Support | ✅ Full Support |
| **Mozilla Firefox**| `75+` | ⚠️ Limited TTS voices | ✅ Full Support | ✅ Full Support |

### External CDNs (Loaded dynamically)
- **Tailwind CSS (v3.x):** `https://cdn.tailwindcss.com`
- **Lucide Icons:** `https://unpkg.com/lucide@latest`

---

## 🔌 4. Embedded Hardware Toolchain (Physical Glove)

If you are assembling and flashing the physical glove hardware:

### Software & Drivers
- **Arduino IDE:** Version `2.0+` (or PlatformIO in VS Code)
- **Silicon Labs CP210x / CH340 USB-to-UART Driver:** Required for your computer to recognize the ESP32 COM port.
- **ESP32 Arduino Core:** Version `2.0.x` or `3.0.x` by Espressif Systems:
  - Add to Boards Manager: `https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json`

### Arduino Libraries (Install via Arduino Library Manager)
| Library | Author | Purpose |
| :--- | :--- | :--- |
| **`ArduinoJson`** | Benoit Blanchon (`v6.x` or `v7.x`) | Serializes sensor telemetry into compact JSON packets. |
| **`WebSockets`** | Markus Sattler | Provides `WebSocketsClient` for streaming telemetry to FastAPI. |
| **`Wire`** | Arduino (Built-in) | I2C master driver for communicating with MPU6050. |
| **`WiFi`** | Espressif (Built-in) | WiFi station management on ESP32. |

### Bill of Materials (Physical Hardware)
| Item | Quantity | Specifications |
| :--- | :--- | :--- |
| **Microcontroller** | 1 | ESP32 DevKit V1 (30-pin or 38-pin) |
| **Flex Sensors** | 5 | Spectra Symbol 2.2" or 4.5" (10kΩ to 30kΩ nominal) |
| **IMU Sensor** | 1 | MPU6050 (3-axis Accelerometer + 3-axis Gyroscope) |
| **Fixed Resistors** | 5 | 10kΩ 1/4W (for flex sensor voltage dividers) |
| **Glove Substrate**| 1 | Fitted cycling, athletic, or compression glove |
| **Wiring** | 1 set | 28-30 AWG flexible silicone stranded wire |
| **Power** | 1 | 3.7V LiPo Battery + 5V Step-up OR Micro-USB cable |
