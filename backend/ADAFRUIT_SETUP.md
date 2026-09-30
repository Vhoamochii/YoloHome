# Adafruit IO Setup for Backend

## ✅ What Was Added

Your **`backend/main.py`** now connects to Adafruit IO automatically when you start the server!

### Files Modified/Created:
1. ✅ `backend/main.py` - Added MQTT connection on startup
2. ✅ `backend/adafruit_mqtt.py` - MQTT client that connects to Adafruit IO
3. ✅ `backend/requirements.txt` - Added `paho-mqtt` and `python-dotenv`

---

## 🔧 Setup Steps

### 1. Install Dependencies
```bash
cd backend
pip install -r requirements.txt
```

### 2. Configure Adafruit IO Credentials

Create/edit `backend/.env`:
```env
# Database
DATABASE_URL=postgresql://localhost/yolohome
SECRET_KEY=your-secret-key-change-me

# Adafruit IO - GET THESE FROM https://io.adafruit.com
ADAFRUIT_IO_USERNAME=your_username
ADAFRUIT_IO_KEY=your_aio_key
```

**Get your credentials:**
1. Go to https://io.adafruit.com
2. Click your profile → "My Key"
3. Copy **Username** and **Active Key**
4. Paste into `.env` file

### 3. Create Feeds on Adafruit IO

Go to https://io.adafruit.com and create these feeds:
- ✅ `yolohome-temperature`
- ✅ `yolohome-humidity`
- ✅ `yolohome-fan`
- ✅ `yolohome-led`

### 4. Setup Database
```bash
# Create database
createdb yolohome

# Run schema
psql yolohome < ../database/schema.sql
```

### 5. Start Your Backend
```bash
cd backend
uvicorn main:app --reload
```

---

## 🎉 What Happens

When you start the backend, you'll see:

```
🚀 Starting Adafruit IO MQTT connection...
🔌 Connecting to Adafruit IO...
✅ Connected to Adafruit IO!
📡 Subscribed to all feeds: your_username/feeds/#
INFO:     Uvicorn running on http://0.0.0.0:8000
```

**Now your backend:**
- ✅ Connects to Adafruit IO automatically
- ✅ Subscribes to all your feeds
- ✅ Saves sensor data to PostgreSQL when ESP32 publishes
- ✅ Can send commands to ESP32 (fan, LED control)

---

## 📊 Data Flow

```
┌─────────────┐
│   ESP32     │ ──── Publishes sensor data ───┐
│  (Firmware) │                                 │
└─────────────┘                                 ↓
                                         ┌─────────────────┐
                                         │  Adafruit IO    │
                                         │  MQTT Broker    │
                                         └─────────────────┘
                                                 │
                          Subscribes to feeds ───┘
                                                 ↓
                                         ┌─────────────────┐
                                         │  Your Backend   │
                                         │  (FastAPI)      │
                                         └─────────────────┘
                                                 │
                                    Saves to ────┘
                                                 ↓
                                         ┌─────────────────┐
                                         │   PostgreSQL    │
                                         │   Database      │
                                         └─────────────────┘
                                                 │
                                    Fetches from ┘
                                                 ↓
                                         ┌─────────────────┐
                                         │  React Frontend │
                                         │  (Dashboard)    │
                                         └─────────────────┘
```

---

## 🧪 Test the Connection

### Test 1: Check Backend Logs
Start backend and look for:
```
✅ Connected to Adafruit IO!
```

### Test 2: Publish from Adafruit IO Dashboard
1. Go to https://io.adafruit.com
2. Open your `yolohome-temperature` feed
3. Click "Add Data" → Enter `28.5`
4. Check your backend logs:
```
📨 Received: your_username/feeds/yolohome-temperature = 28.5
💾 Saved temperature: 28.5°C
```

### Test 3: Check Database
```bash
psql yolohome
SELECT * FROM lich_su_cam_bien ORDER BY recorded_at DESC LIMIT 5;
```

You should see the sensor data!

---

## 🎮 Control Devices from Backend

Now you can control ESP32 from your backend!

### Example: Turn on fan
```python
from adafruit_mqtt import mqtt_client

# In your route handler
mqtt_client.publish("yolohome-fan", "100")  # 100% speed
```

This is already set up in `backend/routes/devices.py` (you just need to implement it)!

---

## 🐛 Troubleshooting

### Error: "Failed to connect to Adafruit IO"
- ✅ Check your username/key in `.env`
- ✅ Make sure you have internet connection
- ✅ Verify credentials at https://io.adafruit.com

### Error: "Module not found: adafruit_mqtt"
```bash
cd backend
pip install -r requirements.txt
```

### No data being saved to database
- ✅ Make sure PostgreSQL is running
- ✅ Check database connection in `.env`
- ✅ Create database with: `createdb yolohome`
- ✅ Run schema: `psql yolohome < ../database/schema.sql`

---

## 📚 Next Steps

1. ✅ Configure ESP32 firmware with same feeds
2. ✅ Upload firmware to ESP32
3. ✅ ESP32 will publish sensor data → Adafruit IO → Your Backend → Database
4. ✅ Start frontend to see the dashboard
5. ✅ Control devices from frontend → Backend → Adafruit IO → ESP32

Your full stack is connected! 🚀
