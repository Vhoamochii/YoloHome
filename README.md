# YoloHome: AI IoT Smart Home System

## Project Overview
YoloHome is a comprehensive smart home system integrating IoT and AI technologies using Adafruit IO, ESP32-S3, DHT20 sensor, and edge AI capabilities including face recognition and voice recognition.

## System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    YOUR COMPUTER                         │
│  ┌─────────────┐          ┌──────────────┐             │
│  │  Frontend   │ ◄─REST─► │   Backend    │             │
│  │  React      │          │   FastAPI    │             │
│  │  :5173      │          │   :8000      │             │
│  └─────────────┘          └──────┬───────┘             │
│                                   │                      │
│                                   ↓                      │
│                           ┌───────────────┐             │
│                           │  PostgreSQL   │             │
│                           └───────────────┘             │
└─────────────────────────────────────────────────────────┘
                              │
                       MQTT over Internet
                              ↓
                    ┌──────────────────┐
                    │  Adafruit IO     │
                    │  MQTT Broker     │
                    └──────────────────┘
                              │
                       MQTT over WiFi
                              ↓
                    ┌──────────────────┐
                    │     ESP32-S3     │
                    │   (Yolo Uno)     │
                    │  - DHT20 sensor  │
                    │  - Fan (PWM)     │
                    │  - LED (RGB)     │
                    │  - TinyML AI     │
                    └──────────────────┘
```

### 4-Layer Architecture
1. **Presentation Layer** - React + TypeScript + Tailwind CSS
2. **Application Layer** - FastAPI + MQTT + AI Integration
3. **Data Layer** - PostgreSQL Database
4. **Edge/IoT Layer** - ESP32-S3 FreeRTOS with 7 Tasks

## Tech Stack

### Frontend (UI/UX)
- React 18 + TypeScript
- Vite 5 (build tool)
- Tailwind CSS + Material-UI
- Recharts (real-time data visualization)
- Web Speech API (Vietnamese voice control)
- Face-api.js (face recognition)
- Axios (API client)

**Features:**
- Dashboard with live sensor graphs
- Device control interface
- Voice command microphone
- Face recognition login
- Schedule management
- Responsive design

### Backend (AI + Control Flow)
- FastAPI 2.0 (async Python framework)
- Paho MQTT (Adafruit IO real-time connection)
- SQLAlchemy (PostgreSQL ORM)
- Face Recognition library (AI)
- OpenCV (image processing)
- PyJWT (authentication)
- Python-dotenv (configuration)

**Features:**
- Real-time MQTT subscription to Adafruit IO
- Automatic sensor data saving to PostgreSQL
- Device control via MQTT publish
- Face recognition API
- JWT authentication
- Auto-generated API docs at `/docs`

### Database (PostgreSQL)
- Real-time sensor history
- User accounts & face profiles
- Device status & configuration
- Schedule automation
- Activity logs

**Tables:**
- `nguoi_dung` - Users
- `face_profiles` - Face encodings
- `thiet_bi` - Devices
- `trang_thai_thiet_bi` - Device status
- `lich_su_cam_bien` - Sensor history
- `lich_trinh` - Schedules

### Firmware (ESP32-S3)
- ESP32-S3 (Yolo Uno)
- FreeRTOS with 7 parallel tasks
- TensorFlow Lite Micro (TinyML)
- Adafruit IO MQTT client
- DHT20 I2C sensor
- NeoPixel LED control
- PWM fan control

**FreeRTOS Tasks:**
1. `sensor_task` - Read DHT20 every 2s
2. `tinyml_task` - AI inference on sensor data
3. `control_logic_task` - Auto cooling logic
4. `actuator_task` - Control fan/LED
5. `adafruitio_task` - MQTT communication
6. `status_led_task` - LED status indicator
7. `boot_button_task` - Factory reset handler

### AI Features
- **Face Recognition** - Login & registration using face encodings
- **Voice Recognition** - Vietnamese command recognition
- **Edge AI (TinyML)** - On-device anomaly detection
- **Auto Cooling** - AI-driven temperature control with ramp curve
- **Manual Lockdown** - Override AI decisions for 30 minutes

## Core Features

### 1. Authentication
- Email/Password login with JWT
- Face recognition login (using camera)
- Face registration and profile management

### 2. Real-time Environment Monitoring
- Live temperature & humidity from DHT20
- Auto-refresh dashboard every 5 seconds
- Historical data charts (24 hours)
- Anomaly detection alerts

### 3. Device Control
- Manual on/off control
- Fan speed adjustment (0-100%)
- RGB LED color control
- Vietnamese voice commands ("Bật quạt", "Tắt đèn")
- Schedule automation (daily/weekly)

### 4. Edge AI
- TinyML model runs on ESP32
- Auto cooling with graduated ramp (0→50→100% over 10 min)
- Manual lockdown mode (user control takes priority)
- Real-time inference <500ms

## Data Flow

### Sensor Data (ESP32 → Backend → Database)
```
1. ESP32 reads DHT20 sensor
2. Publishes to Adafruit IO: "yolohome-temperature"
3. Backend MQTT client receives message
4. Saves to PostgreSQL: lich_su_cam_bien
5. Frontend fetches via: GET /api/sensors/current
```

### Device Control (Frontend → Backend → ESP32)
```
1. User clicks "Turn On Fan" on dashboard
2. Frontend: POST /api/devices/1/control {"action": "on"}
3. Backend publishes to Adafruit IO: "yolohome-fan" = "1"
4. ESP32 subscribes, receives command
5. Actuator task turns on fan via PWM
6. ESP32 publishes status back
7. Backend updates database
```

## Project Structure
```
YoloHome/
├── frontend/                  # React + TypeScript
│   ├── src/
│   │   ├── pages/            # Dashboard, Devices, Login, Schedule
│   │   ├── components/       # VoiceControl, ProtectedLayout
│   │   └── services/         # API client
│   └── package.json
│
├── backend/                   # FastAPI + MQTT
│   ├── routes/               # API endpoints
│   │   ├── auth.py          # Login, face recognition
│   │   ├── devices.py       # Device control (MQTT publish)
│   │   ├── sensors.py       # Sensor data API
│   │   └── webhook.py       # Adafruit IO webhook
│   ├── adafruit_mqtt.py     # MQTT client (auto-connects)
│   ├── main.py              # FastAPI app + MQTT startup
│   ├── models.py            # SQLAlchemy models
│   └── requirements.txt
│
├── firmware/                  # ESP32-S3 FreeRTOS
│   ├── src/
│   │   ├── tasks/           # 7 FreeRTOS tasks
│   │   └── main.cpp         # Entry point
│   ├── include/
│   │   ├── config.h         # WiFi, Adafruit IO config
│   │   └── types.h          # Struct definitions
│   └── platformio.ini
│
├── ai-models/                 # AI training scripts
│   ├── train_tinyml_model.py
│   └── face_recognition.py
│
└── database/
    └── schema.sql            # PostgreSQL tables
```

## Hardware Requirements
- **Yolo Uno** (ESP32-S3 DevKit)
- **DHT20** Temperature & Humidity Sensor (I2C)
- **WS2812** RGB LED Strip (4 LEDs)
- **DC Mini Fan** with PWM control
- **LCD 16x2** Display (optional)

## Getting Started

See `SETUP.md` for detailed installation and configuration instructions.

**Quick Start:**
```bash
# 1. Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload

# 2. Frontend
cd frontend
npm install
npm run dev

# 3. Firmware (Yolo Uno) — see "Firmware Setup" below first
cd firmware
pio run -e yolo_uno --target upload
```

## Firmware Setup: Adafruit IO Cloud Task on Yolo Uno

The cloud task (`adafruitio_task`) is the only firmware code that talks to Adafruit IO. Other
tasks never call the Adafruit IO library directly; they exchange data with it through queues.
Tested end to end on a Yolo Uno: telemetry reaches Adafruit IO, and LED colour commands reach
the board and are acknowledged.

### 1. Files

```
firmware/
├── platformio.ini
├── boards/
│   └── yolo_uno.json          # from github.com/nhanksd85/YoloUNO_PlatformIO (branch LED_Blinky)
├── include/
│   ├── adafruitio_task.h      # message formats + queue API for other tasks
│   ├── config.h               # pins (Yolo Uno / Yolo:Bit, picked by chip), feed keys, tuning
│   ├── secrets.h              # copy of secrets.h.example — gitignored, never commit
│   └── bareboard_demo.h       # optional: test with nothing plugged in
└── src/
    ├── main.cpp
    └── tasks/
        ├── adafruitio_task.cpp
        └── bareboard_demo.cpp # optional
```

Add `firmware/include/secrets.h` to `.gitignore`.

### 2. `platformio.ini`

```ini
[env:yolo_uno]
platform = espressif32 @ 7.1.2      ; Arduino core 2.0.17 — pinned, newer releases change APIs
board = yolo_uno
framework = arduino
monitor_speed = 115200
lib_deps =
    adafruit/Adafruit IO Arduino@4.3.7
    adafruit/Adafruit NeoPixel@1.15.1
lib_ignore = WiFiNINA_-_Adafruit_Fork   ; otherwise its WiFi.h shadows the ESP32's
lib_ldf_mode = chain+
build_flags =
    -D ARDUINO_USB_MODE=1               ; USB-C is the ESP32-S3's native USB
    -D ARDUINO_USB_CDC_ON_BOOT=1        ; so Serial prints over USB-C
```

### 3. Credentials and feeds

`include/secrets.h`:

```cpp
#pragma once
#define WIFI_SSID     "your_wifi_ssid"      // 2.4 GHz, no login web page (a phone hotspot works)
#define WIFI_PASSWORD "your_wifi_password"
#define AIO_USERNAME  "your_adafruit_username"
#define AIO_KEY       "aio_xxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

Create these 10 feeds on io.adafruit.com and check that each **key** matches exactly
(10 is the free-tier maximum):

| Feed key | Direction |
|---|---|
| `yolohome-temperature`, `yolohome-humidity`, `yolohome-light`, `yolohome-presence` | board → cloud |
| `yolohome-fan`, `yolohome-led` | commands, cloud → board |
| `yolohome-ack`, `yolohome-event`, `yolohome-mode`, `yolohome-fan-state` | board → cloud |

### 4. Start the task in `main.cpp`

```cpp
#include "adafruitio_task.h"

EventGroupHandle_t gSystemEvents = nullptr;   // skip if your firmware already defines it

void setup() {
  Serial.begin(115200);
  gSystemEvents = xEventGroupCreate();
  cloud_init();                               // create the queues BEFORE starting any task
  xTaskCreatePinnedToCore(task_adafruitio, "cloud", 8192, nullptr, 2, nullptr, 0);  // TLS needs 8 KB
  // ... other tasks
}
```

For a first test with nothing plugged in, use `src/main_bareboard.cpp` as `main.cpp`: it also
starts `task_bareboard_demo` and prints the link status every 5 s.

### 5. Build, flash, monitor

```bash
cd firmware
pio run -e yolo_uno                 # first build downloads the toolchain (several minutes)
pio run -e yolo_uno -t upload       # no buttons needed normally
pio device monitor -e yolo_uno
```

If the upload fails with "Failed to connect", put the board in download mode (hold **BOOT**,
press **RST**, release BOOT), upload again, then press **RST** to start the program.
BOOT + RST alone does not restart the program; RST alone does.

### 6. Expected result (bare-board demo)

- Serial monitor: `cloud UP | published …` every 5 s.
- On-board LED (GPIO 48) blinks 1 s on / 1 s off; `yolohome-light` receives **50** every 30 s.
- `yolohome-mode` shows `BAREBOARD_DEMO`.
- Entering `#00FF00` in `yolohome-led` turns the RGB LED green and adds `led:-:1:00FF00:U`
  to `yolohome-ack`. Entering `70` in `yolohome-fan` is refused: `fan:-:0:70:U:NOHW`.
- After a reset, the RGB LED returns to the last colour stored on `yolohome-led` once the
  board reconnects (a few seconds).

### 7. Connecting the other tasks

| Task | Call |
|---|---|
| Sensor task | `cloud_post_sample(Sample{temp, humi, light, presence})` on every reading; NaN = failed read |
| Control logic | Read `CloudCommandMsg` from `qCloudCommands`; after deciding, always call `cloud_post_ack(dev, id, ok, value, actor, reason)` — rejections too (reason `LOCK`, `SAFE`, …) |
| Control logic | `cloud_post_mode("MANUAL_LOCKDOWN until 15:12")`, `cloud_post_fan_state(70)`, `cloud_post_event("SAFETY", "46.2")` |
| Anyone | Bit `EVT_CLOUD_UP` in `gSystemEvents` is set while connected; clear ⇒ OFFLINE_FAILSAFE |

A command with actor `Sync` restores state after a reconnect and must **not** start a Manual
Lockdown. Check that `EVT_CLOUD_UP` (bit 8) does not collide with your existing event bits.

### 8. Pitfalls (Yolo Uno)

- **Pin names are wrong for this board.** `boards/yolo_uno.json` reuses the M5Stack AtomS3
  pin definitions, so `SDA`, `SCL`, `LED_BUILTIN`, `D7`, `A0` … refer to that board. Use only the
  numeric pins in `config.h`. In particular, call `Wire.begin(DHT_SDA, DHT_SCL)` (11, 12)
  **before** any DHT20/LCD library's `begin()`.
- **`'class WiFiClass' has no member named 'reconnect'`** means the WiFiNINA fork got into the
  build: check the `lib_ignore` line above, then `pio run -e yolo_uno -t clean`.
- **`DHT sensor library` in the dependency graph** comes with the Adafruit IO library and only
  supports DHT11/DHT22. The DHT20 needs its own library (e.g. `DHT20`).
- The Yolo Uno has **no buzzer**; the audible alert needs a buzzer module on a free port.

To test the backend side against the running board, see `backend/live_test.py`.

## API Documentation

Once backend is running, visit:
- **Interactive API Docs:** http://localhost:8000/docs
- **Health Check:** http://localhost:8000

## License
MIT