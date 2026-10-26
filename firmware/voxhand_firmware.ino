/*
  ==============================================================================
  Project: VOXHAND - Smart Sign Language Glove Prototype
  Firmware: ESP32 Telemetry Transmitter (voxhand_firmware.ino)
  ------------------------------------------------------------------------------
  Hardware Architecture:
    - Microcontroller: ESP32 DevKit V1 (30-pin / 38-pin)
    - 5x Flex Sensors (Spectra Symbol 2.2" or 4.5", 10k-30k ohm):
        Thumb  -> GPIO 36 (ADC1_CH0 / VP)
        Index  -> GPIO 39 (ADC1_CH3 / VN)
        Middle -> GPIO 34 (ADC1_CH6)
        Ring   -> GPIO 35 (ADC1_CH7)
        Pinky  -> GPIO 32 (ADC1_CH4)
        Note: Voltage divider circuit with 10k ohm pulldown resistors to GND.
              Only ADC1 pins are used so WiFi does not interfere with ADC2!
    - 1x 6-DOF IMU (MPU6050 Accelerometer + Gyroscope):
        SDA    -> GPIO 21
        SCL    -> GPIO 22
        VCC    -> 3.3V
        GND    -> GND
        AD0    -> GND (I2C Address 0x68)
    - Status Indicator:
        Onboard LED -> GPIO 2 (Blinks during connect, Solid when streaming)
    - Calibration Button (Optional):
        BOOT Button -> GPIO 0 (Long press triggers re-calibration)
  ------------------------------------------------------------------------------
  Dependencies (Install via Arduino IDE Library Manager):
    - ArduinoJson by Benoit Blanchon (v6.x or v7.x)
    - WebSockets by Markus Sattler (WebSocketsClient)
    - Wire (Built-in ESP32)
    - WiFi (Built-in ESP32)
  ==============================================================================
*/

#include <WiFi.h>
#include <WebSocketsClient.h>
#include <ArduinoJson.h>
#include <Wire.h>

// -----------------------------------------------------------------------------
// WiFi & Gateway Configuration
// -----------------------------------------------------------------------------
const char* WIFI_SSID     = "YOUR_WIFI_SSID";         // Replace with your WiFi SSID
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";     // Replace with your WiFi Password
const char* WS_HOST       = "192.168.1.100";          // IP address of Backend Gateway host
const int   WS_PORT       = 8000;                     // FastAPI WebSocket Port
const char* WS_PATH       = "/ws/stream";             // WebSocket Endpoint Path

WebSocketsClient webSocket;

// -----------------------------------------------------------------------------
// Pin Assignments
// -----------------------------------------------------------------------------
const int PIN_FLEX_THUMB  = 36;  // ADC1_CH0
const int PIN_FLEX_INDEX  = 39;  // ADC1_CH3
const int PIN_FLEX_MIDDLE = 34;  // ADC1_CH6
const int PIN_FLEX_RING   = 35;  // ADC1_CH7
const int PIN_FLEX_PINKY  = 32;  // ADC1_CH4

const int PIN_STATUS_LED  = 2;   // Onboard Blue LED
const int PIN_CALIB_BTN   = 0;   // BOOT Button (Active LOW)

const int FLEX_PINS[5] = {
  PIN_FLEX_THUMB,
  PIN_FLEX_INDEX,
  PIN_FLEX_MIDDLE,
  PIN_FLEX_RING,
  PIN_FLEX_PINKY
};

// -----------------------------------------------------------------------------
// Calibration Data Structures
// Default range for 12-bit ADC (0 - 4095) with 10k voltage divider:
// Unbent / Straight: ~1200 - 1600 (Lower resistance ~10k)
// Fully Bent:        ~2600 - 3400 (Higher resistance ~30k-40k)
// -----------------------------------------------------------------------------
struct SensorCalibration {
  int rawMin;  // Value when finger is fully straight (flex = 0.0)
  int rawMax;  // Value when finger is fully bent (flex = 1.0)
};

SensorCalibration flexCalib[5] = {
  {1400, 3100},  // Thumb
  {1350, 3000},  // Index
  {1400, 3050},  // Middle
  {1380, 2950},  // Ring
  {1300, 2900}   // Pinky
};

// -----------------------------------------------------------------------------
// MPU6050 Registers & Configuration
// -----------------------------------------------------------------------------
const uint8_t MPU6050_ADDR         = 0x68;
const uint8_t MPU6050_PWR_MGMT_1   = 0x6B;
const uint8_t MPU6050_ACCEL_XOUT_H = 0x3B;

// Accelerometer scale factor: ±2g  -> 16384 LSB/g
const float ACCEL_SCALE = 16384.0f;
// Gyroscope scale factor: ±250 deg/s -> 131.0 LSB / (deg/s) -> convert to rad/s
const float GYRO_SCALE  = 131.0f * (180.0f / 3.14159265f); // rad/s conversion factor

// Timing & Streaming Rate
unsigned long lastTelemetryTime = 0;
const unsigned long TELEMETRY_INTERVAL_MS = 40; // 25 Hz transmission rate (40 ms)
bool isWebSocketConnected = false;

// -----------------------------------------------------------------------------
// Normalization Function: Converts raw 12-bit ADC reading to [0.0, 1.0]
// -----------------------------------------------------------------------------
float normalizeFlex(int raw, int rawMin, int rawMax) {
  if (rawMax <= rawMin) rawMax = rawMin + 1; // Prevent division by zero
  float norm = (float)(raw - rawMin) / (float)(rawMax - rawMin);
  if (norm < 0.0f) norm = 0.0f;
  if (norm > 1.0f) norm = 1.0f;
  return norm;
}

// -----------------------------------------------------------------------------
// MPU6050 Hardware Initialization & Reading
// -----------------------------------------------------------------------------
bool initMPU6050() {
  Wire.begin(21, 22, 400000); // SDA = GPIO 21, SCL = GPIO 22, Fast I2C (400kHz)
  delay(50);

  // Wake up MPU6050 (clear SLEEP bit in PWR_MGMT_1)
  Wire.beginTransmission(MPU6050_ADDR);
  Wire.write(MPU6050_PWR_MGMT_1);
  Wire.write(0x00);
  uint8_t error = Wire.endTransmission();

  if (error == 0) {
    Serial.println("[MPU6050] Initialized successfully at address 0x68.");
    return true;
  } else {
    Serial.printf("[MPU6050] ERROR: Device not responding (I2C error code %d).\n", error);
    return false;
  }
}

void readMPU6050(float &ax, float &ay, float &az, float &gx, float &gy, float &gz) {
  Wire.beginTransmission(MPU6050_ADDR);
  Wire.write(MPU6050_ACCEL_XOUT_H);
  if (Wire.endTransmission(false) != 0) {
    // If read fails, fallback to neutral resting state
    ax = 0.0f; ay = 0.98f; az = 0.15f;
    gx = 0.0f; gy = 0.0f;  gz = 0.0f;
    return;
  }

  // Request 14 bytes: Accel (6), Temp (2), Gyro (6)
  Wire.requestFrom(MPU6050_ADDR, (uint8_t)14, (uint8_t)true);
  if (Wire.available() >= 14) {
    int16_t rawAx = (Wire.read() << 8) | Wire.read();
    int16_t rawAy = (Wire.read() << 8) | Wire.read();
    int16_t rawAz = (Wire.read() << 8) | Wire.read();
    Wire.read(); Wire.read(); // Skip temp bytes
    int16_t rawGx = (Wire.read() << 8) | Wire.read();
    int16_t rawGy = (Wire.read() << 8) | Wire.read();
    int16_t rawGz = (Wire.read() << 8) | Wire.read();

    // Scale to standard units (Accel in g, Gyro in rad/s)
    ax = (float)rawAx / ACCEL_SCALE;
    ay = (float)rawAy / ACCEL_SCALE;
    az = (float)rawAz / ACCEL_SCALE;

    gx = (float)rawGx / 131.0f * (3.14159265f / 180.0f);
    gy = (float)rawGy / 131.0f * (3.14159265f / 180.0f);
    gz = (float)rawGz / 131.0f * (3.14159265f / 180.0f);
  }
}

// -----------------------------------------------------------------------------
// Interactive 5-Second Flex Calibration Routine
// -----------------------------------------------------------------------------
void runCalibrationRoutine() {
  Serial.println("\n========================================================");
  Serial.println("[CALIBRATION] Starting 5-second dynamic flex calibration!");
  Serial.println("[CALIBRATION] Open and close your hand fully several times...");
  Serial.println("========================================================");

  for (int i = 0; i < 5; i++) {
    flexCalib[i].rawMin = 4095;
    flexCalib[i].rawMax = 0;
  }

  unsigned long startTime = millis();
  while (millis() - startTime < 5000) {
    digitalWrite(PIN_STATUS_LED, (millis() / 100) % 2); // Fast blink
    for (int i = 0; i < 5; i++) {
      int val = analogRead(FLEX_PINS[i]);
      if (val < flexCalib[i].rawMin && val > 100)  flexCalib[i].rawMin = val;
      if (val > flexCalib[i].rawMax && val < 4000) flexCalib[i].rawMax = val;
    }
    delay(20);
  }

  Serial.println("[CALIBRATION] Complete. Measured Ranges:");
  const char* fingerNames[5] = {"Thumb", "Index", "Middle", "Ring", "Pinky"};
  for (int i = 0; i < 5; i++) {
    // Add margin if range is too narrow
    if (flexCalib[i].rawMax - flexCalib[i].rawMin < 400) {
      flexCalib[i].rawMin = 1300;
      flexCalib[i].rawMax = 3000;
    }
    Serial.printf("  %s: Min=%d, Max=%d (Span=%d)\n",
                  fingerNames[i], flexCalib[i].rawMin, flexCalib[i].rawMax,
                  flexCalib[i].rawMax - flexCalib[i].rawMin);
  }
  Serial.println("========================================================\n");
  digitalWrite(PIN_STATUS_LED, HIGH);
}

// -----------------------------------------------------------------------------
// WebSocket Event Callback
// -----------------------------------------------------------------------------
void webSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
  switch(type) {
    case WStype_DISCONNECTED:
      isWebSocketConnected = false;
      digitalWrite(PIN_STATUS_LED, LOW);
      Serial.println("[WS] Disconnected from backend gateway.");
      break;

    case WStype_CONNECTED:
      isWebSocketConnected = true;
      digitalWrite(PIN_STATUS_LED, HIGH);
      Serial.printf("[WS] Connected successfully to gateway %s:%d%s\n", WS_HOST, WS_PORT, WS_PATH);
      break;

    case WStype_TEXT:
      Serial.printf("[WS] Received response from backend: %s\n", payload);
      break;

    case WStype_ERROR:
      Serial.printf("[WS] Error occurred: %s\n", payload);
      break;

    default:
      break;
  }
}

// -----------------------------------------------------------------------------
// Arduino Setup
// -----------------------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n--------------------------------------------------------");
  Serial.println("    VOXHAND ESP32 SMART GLOVE FIRMWARE INITIALIZING     ");
  Serial.println("--------------------------------------------------------");

  pinMode(PIN_STATUS_LED, OUTPUT);
  pinMode(PIN_CALIB_BTN, INPUT_PULLUP);
  digitalWrite(PIN_STATUS_LED, LOW);

  // Configure ADC attenuation (11dB provides full-scale ~0 - 3.3V range)
  analogSetAttenuation(ADC_11db);
  for (int i = 0; i < 5; i++) {
    pinMode(FLEX_PINS[i], INPUT);
  }

  // Initialize MPU6050
  initMPU6050();

  // Connect to WiFi
  Serial.printf("[WiFi] Connecting to SSID: %s ", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int wifiRetries = 0;
  while (WiFi.status() != WL_CONNECTED && wifiRetries < 20) {
    delay(500);
    Serial.print(".");
    digitalWrite(PIN_STATUS_LED, !digitalRead(PIN_STATUS_LED));
    wifiRetries++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n[WiFi] Connected successfully!");
    Serial.print("[WiFi] ESP32 IP Address: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\n[WiFi] Connection timed out. Running in local acquisition mode.");
  }

  // Configure WebSocket Client
  webSocket.begin(WS_HOST, WS_PORT, WS_PATH);
  webSocket.onEvent(webSocketEvent);
  webSocket.setReconnectInterval(2500);
  webSocket.enableHeartbeat(5000, 3000, 2);

  // Perform initial calibration
  runCalibrationRoutine();
  Serial.println("[SETUP] VOXHAND Firmware ready. Beginning telemetry streaming...");
}

// -----------------------------------------------------------------------------
// Arduino Main Loop
// -----------------------------------------------------------------------------
void loop() {
  webSocket.loop();

  // Check if manual re-calibration button is pressed (GPIO 0 BOOT button)
  if (digitalRead(PIN_CALIB_BTN) == LOW) {
    delay(50); // Debounce
    if (digitalRead(PIN_CALIB_BTN) == LOW) {
      runCalibrationRoutine();
    }
  }

  unsigned long currentMillis = millis();
  if (currentMillis - lastTelemetryTime >= TELEMETRY_INTERVAL_MS) {
    lastTelemetryTime = currentMillis;

    // 1. Read and normalize 5 flex sensors
    float flexNorm[5];
    for (int i = 0; i < 5; i++) {
      int rawVal = analogRead(FLEX_PINS[i]);
      flexNorm[i] = normalizeFlex(rawVal, flexCalib[i].rawMin, flexCalib[i].rawMax);
    }

    // 2. Read 6-DOF IMU (Accelerometer and Gyroscope)
    float ax, ay, az, gx, gy, gz;
    readMPU6050(ax, ay, az, gx, gy, gz);

    // 3. Package into JSON telemetry payload
    // Buffer size calculated for ~200 bytes JSON
    StaticJsonDocument<384> doc;

    JsonArray flexArray = doc.createNestedArray("flex");
    for (int i = 0; i < 5; i++) {
      flexArray.add(serialized(String(flexNorm[i], 3)));
    }

    JsonObject accelObj = doc.createNestedObject("accel");
    accelObj["x"] = serialized(String(ax, 3));
    accelObj["y"] = serialized(String(ay, 3));
    accelObj["z"] = serialized(String(az, 3));

    JsonObject gyroObj = doc.createNestedObject("gyro");
    gyroObj["x"] = serialized(String(gx, 3));
    gyroObj["y"] = serialized(String(gy, 3));
    gyroObj["z"] = serialized(String(gz, 3));

    doc["timestamp"] = (uint32_t)(currentMillis / 1000);

    // 4. Serialize to string
    String jsonString;
    serializeJson(doc, jsonString);

    // 5. Send via WebSocket if connected
    if (isWebSocketConnected) {
      webSocket.sendTXT(jsonString);
    } else {
      // Echo to Serial monitor for USB debugging when offline
      static int serialThrottle = 0;
      if (++serialThrottle % 10 == 0) {
        Serial.printf("[LOCAL STREAM] %s\n", jsonString.c_str());
      }
    }
  }
}

