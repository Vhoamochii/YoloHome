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

# 3. Firmware
cd firmware
pio run --target upload
```

## API Documentation

Once backend is running, visit:
- **Interactive API Docs:** http://localhost:8000/docs
- **Health Check:** http://localhost:8000

## License
MIT
