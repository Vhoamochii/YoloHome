from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from routes import auth, devices, sensors, webhook
from database import engine, Base
from adafruit_mqtt import mqtt_client

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    
    print("Starting Adafruit IO MQTT connection...")
    mqtt_client.connect()
    
    yield
    
    mqtt_client.disconnect()
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
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(devices.router, prefix="/api/devices", tags=["devices"])
app.include_router(sensors.router, prefix="/api/sensors", tags=["sensors"])
app.include_router(webhook.router, prefix="/api/webhook", tags=["webhook"])

@app.get("/")
async def root():
    return {"message": "YoloHome API is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
