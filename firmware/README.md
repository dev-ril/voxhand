# VOXHAND ESP32 Firmware & Hardware Simulation

This directory contains the embedded code and synthetic hardware mock for the **VOXHAND** smart sign language glove prototype.

---

## 1. Hardware Architecture & Wiring Diagram

The physical glove system is driven by an **ESP32 DevKit V1** reading 5 analog flex sensors (1 per finger) and a 6-DOF IMU (MPU6050).

> **CRITICAL NOTE ON ESP32 ADC CHANNELS:**  
> The flex sensors **must only be connected to ADC1 pins** (`GPIO 32 - 39`). ADC2 pins cannot be read while the ESP32 WiFi radio is active.

### Pinout Table

| Sensor / Module | ESP32 Pin | Function | Wiring Details |
| :--- | :--- | :--- | :--- |
| **Thumb Flex** | `GPIO 36` (VP) | ADC1_CH0 | 10kΩ pulldown resistor to GND |
| **Index Flex** | `GPIO 39` (VN) | ADC1_CH3 | 10kΩ pulldown resistor to GND |
| **Middle Flex** | `GPIO 34` | ADC1_CH6 | 10kΩ pulldown resistor to GND |
| **Ring Flex** | `GPIO 35` | ADC1_CH7 | 10kΩ pulldown resistor to GND |
| **Pinky Flex** | `GPIO 32` | ADC1_CH4 | 10kΩ pulldown resistor to GND |
| **MPU6050 SDA** | `GPIO 21` | I2C Data | Direct connection (3.3V logic) |
| **MPU6050 SCL** | `GPIO 22` | I2C Clock | Direct connection (3.3V logic) |
| **MPU6050 VCC/GND** | `3.3V` / `GND` | Power | Connect to ESP32 3.3V rail and GND |
| **Status LED** | `GPIO 2` | Digital Out | Onboard blue LED |
| **Calib Button** | `GPIO 0` | Input Pullup | Onboard `BOOT` button |

### Voltage Divider Schematic (per Flex Sensor)
```text
3.3V ───[ Flex Sensor (10k - 30kΩ) ]───┬───[ 10kΩ Fixed Resistor ]─── GND
                                       │
                               ESP32 ADC Pin (e.g. GPIO 36)
```

---

## 2. Flashing the Firmware (`voxhand_firmware.ino`)

1. **Install Arduino IDE & ESP32 Core:**
   - In Arduino IDE, open **Preferences** and add the ESP32 board URL:
     `https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json`
   - Open **Boards Manager** and install `esp32 by Espressif Systems`.
   - Select board: **ESP32 Dev Module**.

2. **Install Required Libraries:**
   - `ArduinoJson` (v6 or v7) by Benoit Blanchon
   - `WebSockets` by Markus Sattler

3. **Configure Network Credentials:**
   Edit the following lines in `voxhand_firmware.ino`:
   ```cpp
   const char* WIFI_SSID     = "Your_WiFi_Network";
   const char* WIFI_PASSWORD = "Your_WiFi_Password";
   const char* WS_HOST       = "192.168.1.100"; // IP address of computer running FastAPI
   const int   WS_PORT       = 8000;
   const char* WS_PATH       = "/ws/stream";
   ```

4. **Upload and Run:**
   - Connect the ESP32 via USB and select the COM port.
   - Click **Upload**.
   - Open Serial Monitor at **115200 baud**.
   - On boot, the glove runs a **5-second dynamic calibration**. Open and close your hand fully so it maps the exact physical resistance of your sensors.
   - Press the `BOOT` button (GPIO 0) at any time to re-calibrate.

---

## 3. Fallback Mock Hardware Streamer (`mock_esp32_streamer.py`)

If you don't have physical hardware connected, you can run the mock streamer. It generates physically accurate synthetic sensor frames with Gaussian noise, micro-tremors, and kinematic waving/nodding oscillations.

### Mode A: Standalone WebSocket Server (Port 8080)
```bash
python firmware/mock_esp32_streamer.py --port 8080
```
This listens on `ws://localhost:8080` and streams 25 FPS telemetry. Client apps or the dashboard can connect directly.

### Mode B: Direct Pusher into Backend Gateway
```bash
python firmware/mock_esp32_streamer.py --target-gateway ws://localhost:8000/ws/stream
```
This pushes telemetry into the FastAPI backend just like a physical ESP32.

### Options:
- `--gesture HELLO`: Lock simulation to a specific gesture (`HELLO`, `THANK YOU`, `HELP`, `YES`, `NO`, `REST_OR_NOISE`).
- `--gesture AUTO`: Cycles through all 5 gestures + rest noise every 4 seconds.
- `--fps 25`: Adjust streaming rate (default: 25 Hz).

