# YoloHome Setup Guide

Complete installation and configuration guide for all components.

---

## Prerequisites

### Required Software
- **Python 3.9+** (for backend & AI models)
- **Node.js 18+** (for frontend)
- **PostgreSQL 14+** (for database)
- **PlatformIO** (for ESP32 firmware)

### Required Accounts
- **Adafruit IO** account (free tier: 30 data points/min)
  - Sign up at: https://io.adafruit.com

### Required Hardware
- **Yolo Uno** (ESP32-S3 DevKit)
- **DHT20** sensor (I2C)
- **WS2812** RGB LED strip (4 LEDs)
- **DC mini fan** with PWM
- USB-C cable

---

## 1. Adafruit IO Setup

### Create Account & Get Credentials
1. Go to https://io.adafruit.com
2. Sign up for free account
3. Click your profile → **"My Key"**
4. Copy your **Username** and **Active Key**
5. Keep these for later configuration

### Create Feeds
Go to **Feeds** and create these 4 feeds:
- `yolohome-temperature`
- `yolohome-humidity`
- `yolohome-fan`
- `yolohome-led`

---

## 2. Database Setup

### Install PostgreSQL
**Windows:**
```bash
# Download from: https://www.postgresql.org/download/windows/
# Or use chocolatey:
choco install postgresql
```

**macOS:**
```bash
brew install postgresql@14
brew services start postgresql@14
```

**Linux:**
```bash
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
```

### Create Database
```bash
# Create database
createdb yolohome

# Run schema
psql yolohome < database/schema.sql

# Verify tables created
psql yolohome -c "\dt"
```

You should see 6 tables created.

---

## 3. Backend Setup (FastAPI)

### Install Dependencies
```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (macOS/Linux)
source venv/bin/activate

# Install packages
pip install -r requirements.txt
```

### Configure Environment
Copy `.env.example` to `.env`:
```bash
copy .env.example .env     # Windows
cp .env.example .env       # macOS/Linux
```

Edit `backend/.env`:
```env
# Database
DATABASE_URL=postgresql://localhost/yolohome

# Security
SECRET_KEY=change-this-to-random-secret-key

# Adafruit IO (from step 1)
ADAFRUIT_IO_USERNAME=your_username_here
ADAFRUIT_IO_KEY=your_aio_key_here

# CORS (for production, add your domain)
ALLOWED_ORIGINS=http://localhost:5173
```

### Run Backend
```bash
cd backend
uvicorn main:app --reload
```

**Expected output:**
```
🚀 Starting Adafruit IO MQTT connection...
🔌 Connecting to Adafruit IO...
✅ Connected to Adafruit IO!
📡 Subscribed to all feeds: your_username/feeds/#
INFO:     Uvicorn running on http://0.0.0.0:8000
```

**Test it:**
- Health check: http://localhost:8000
- **API Docs:** http://localhost:8000/docs ⭐

---

## 4. Frontend Setup (React)

### Install Dependencies
```bash
cd frontend
npm install
```

### Run Dev Server
```bash
npm run dev
```

**Expected output:**
```
VITE v5.0.8  ready in 500 ms

➜  Local:   http://localhost:5173/
➜  Network: use --host to expose
```

**Open:** http://localhost:5173

---

## 5. Firmware Setup (ESP32-S3)

### Install PlatformIO
```bash
pip install platformio
```

Or install PlatformIO IDE extension in VS Code.

### Configure WiFi & Adafruit IO
Edit `firmware/include/config.h`:

```cpp
// WiFi Configuration
#define WIFI_SSID "your_wifi_name"
#define WIFI_PASSWORD "your_wifi_password"

// Adafruit IO (same as backend .env)
#define AIO_USERNAME "your_username"
#define AIO_KEY "your_aio_key"

// MQTT Topics (must match feed names)
#define FEED_TEMPERATURE "yolohome-temperature"
#define FEED_HUMIDITY "yolohome-humidity"
#define FEED_FAN "yolohome-fan"
#define FEED_LED "yolohome-led"
```

### Upload Firmware
```bash
cd firmware

# Build and upload
pio run --target upload

# Monitor serial output
pio device monitor
```

**Expected output:**
```
Connecting to WiFi...
WiFi connected!
Connecting to Adafruit IO...
Connected to Adafruit IO!
Publishing temperature: 28.5
Publishing humidity: 65.0
```

### Hardware Connections
Connect sensors/actuators to ESP32-S3:

| Component | Connection | GPIO |
|-----------|------------|------|
| DHT20 SDA | I2C SDA | GPIO 11 |
| DHT20 SCL | I2C SCL | GPIO 12 |
| Fan Signal | PWM | GPIO 7 |
| LED Strip | Data | GPIO 9 |
| LCD SDA | I2C SDA | GPIO 11 (shared) |
| LCD SCL | I2C SCL | GPIO 12 (shared) |

**Power:**
- DHT20: 3.3V
- Fan: 5V (use transistor for PWM)
- LED Strip: 5V (with capacitor)

---

## 6. Test Complete System

### Test 1: Backend ↔ Adafruit IO
1. Backend should be running with "✅ Connected to Adafruit IO!"
2. In Adafruit IO dashboard, go to `yolohome-temperature` feed
3. Click **"Add Data"**, enter `28.5`
4. Check backend logs:
   ```
   📨 Received: your_username/feeds/yolohome-temperature = 28.5
   💾 Saved temperature: 28.5°C
   ```
5. Verify in database:
   ```bash
   psql yolohome -c "SELECT * FROM lich_su_cam_bien ORDER BY recorded_at DESC LIMIT 1;"
   ```

### Test 2: ESP32 → Adafruit IO → Backend
1. ESP32 should be running and publishing
2. Check serial monitor: `Publishing temperature: 28.5`
3. Check Adafruit IO feed: value should appear
4. Check backend logs: `📨 Received...`
5. Check database: new row in `lich_su_cam_bien`

### Test 3: Frontend → Backend → Adafruit IO → ESP32
1. Open http://localhost:5173
2. Go to **Devices** page
3. Click "Turn On Fan"
4. Backend logs: `📤 Published: your_username/feeds/yolohome-fan = 1`
5. Adafruit IO: `yolohome-fan` feed shows "1"
6. ESP32 serial: `Received command: fan = 1`
7. Fan should turn on!

### Test 4: API Documentation
Visit http://localhost:8000/docs to see interactive API:
- Try `/api/devices/1/control` endpoint
- Test with: `{"action": "on"}`

---

## 7. AI Features Setup (Optional)

### Face Recognition
```bash
cd ai-models

# Install dependencies (already in backend requirements.txt)
pip install opencv-python face-recognition

# Train face recognition model
python face_recognition.py
```

### TinyML Model Training
```bash
cd ai-models

# Train anomaly detection model
python train_tinyml_model.py

# Convert to C header
xxd -i dht_anomaly_model.tflite > dht_anomaly_model.h

# Copy to firmware
copy dht_anomaly_model.h ..\firmware\src\
```

---

## Common Issues & Solutions

### Backend: "Failed to connect to Adafruit IO"
**Solution:**
- Check credentials in `backend/.env`
- Verify at https://io.adafruit.com → My Key
- Check internet connection
- Try regenerating AIO Key

### Database: "could not connect to server"
**Solution:**
```bash
# Windows
net start postgresql-x64-14

# macOS
brew services start postgresql@14

# Linux
sudo systemctl start postgresql
```

### Firmware: Upload fails
**Solution:**
1. Hold **BOOT** button on ESP32
2. Click **Upload** in PlatformIO
3. Release BOOT when upload starts
4. If still fails, try different USB cable/port

### Frontend: "Network Error"
**Solution:**
- Make sure backend is running on port 8000
- Check `frontend/vite.config.ts` proxy settings
- Check CORS in `backend/main.py`

### ESP32: "Connecting to WiFi..." (stuck)
**Solution:**
- Check WiFi credentials in `firmware/include/config.h`
- Make sure WiFi is 2.4GHz (ESP32 doesn't support 5GHz)
- Check WiFi signal strength
- Try mobile hotspot for testing

### MQTT: "Subscribed but no data"
**Solution:**
- Verify feed names match exactly in all 3 places:
  1. Adafruit IO feeds
  2. `firmware/include/config.h`
  3. `backend/adafruit_mqtt.py`
- Feed names are case-sensitive!

---

## Development Workflow

### Daily Development
```bash
# Terminal 1: Backend
cd backend
venv\Scripts\activate    # or source venv/bin/activate
uvicorn main:app --reload

# Terminal 2: Frontend
cd frontend
npm run dev

# Terminal 3: Firmware (when needed)
cd firmware
pio device monitor
```

### Testing Changes
1. **Backend changes:** Auto-reloads with `--reload`
2. **Frontend changes:** Auto-reloads with Vite HMR
3. **Firmware changes:** Re-upload with `pio run --target upload`
4. **Database changes:** Run migration scripts

---

## Production Deployment

### Backend (Railway/Heroku)
```bash
# Install Railway CLI
npm i -g @railway/cli

# Login and deploy
railway login
cd backend
railway up
```

### Frontend (Vercel/Netlify)
```bash
# Build production
cd frontend
npm run build

# Deploy to Vercel
npx vercel --prod
```

### Database (Cloud PostgreSQL)
Options:
- Railway PostgreSQL
- Supabase
- AWS RDS
- DigitalOcean Managed Database

Update `DATABASE_URL` in production environment.

---

## Next Steps

1. ✅ Test all 4 tests above
2. ✅ Implement authentication in `backend/routes/auth.py`
3. ✅ Add face recognition to login page
4. ✅ Implement voice control commands
5. ✅ Train and deploy TinyML model
6. ✅ Create automation schedules
7. ✅ Deploy to production

---

## Support

For issues or questions:
- Check `backend/ADAFRUIT_SETUP.md` for Adafruit IO details
- Review API docs at http://localhost:8000/docs
- Monitor serial output: `pio device monitor`
- Check backend logs for MQTT messages

Your YoloHome system is now ready! 🚀
