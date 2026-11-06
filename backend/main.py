from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import engine, Base, upgrade_schema
from models import User, FaceProfile, Device, DeviceStatus, SensorHistory, Schedule, ActivityLog, FireAlertHistory
from routes import activity, auth, devices, sensors, webhook, schedules
from adafruit_mqtt import mqtt_client
from device_control import register_handlers, seed_default_devices
from scheduler import scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure all tables are created
    Base.metadata.create_all(bind=engine)
    upgrade_schema()
    seed_default_devices()   # once, before requests: concurrent seeding created duplicates
    register_handlers()
    print("Database tables initialized successfully.")
    
    print("Starting Adafruit IO MQTT connection...")
    try:
        mqtt_client.connect()
    except Exception as e:
        print(f"MQTT startup warning: {e}")

    scheduler.start()

    yield

    scheduler.stop()
    try:
        mqtt_client.disconnect()
    except Exception:
        pass
    print("Application shutting down...")

app = FastAPI(
    title="YoloHome API",
    description="Smart Home AI IoT System",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(devices.router, prefix="/api/devices", tags=["devices"])
app.include_router(sensors.router, prefix="/api/sensors", tags=["sensors"])
app.include_router(schedules.router, prefix="/api/schedules", tags=["schedules"])
app.include_router(activity.router, prefix="/api/activity", tags=["activity"])
app.include_router(webhook.router, prefix="/api/webhook", tags=["webhook"])

@app.get("/")
async def root():
    return {"message": "YoloHome API is running", "status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
