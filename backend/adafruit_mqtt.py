"""
Adafruit IO MQTT Connection Manager
This connects your backend to Adafruit IO in real-time
"""
import paho.mqtt.client as mqtt
import os
from dotenv import load_dotenv
import json
from database import SessionLocal
from models import SensorHistory
from datetime import datetime

load_dotenv()

# Adafruit IO credentials
AIO_USERNAME = os.getenv("ADAFRUIT_IO_USERNAME", "your_username")
AIO_KEY = os.getenv("ADAFRUIT_IO_KEY", "your_key")

# MQTT Topics (feeds)
FEED_TEMPERATURE = f"{AIO_USERNAME}/feeds/yolohome-temperature"
FEED_HUMIDITY = f"{AIO_USERNAME}/feeds/yolohome-humidity"
FEED_FAN = f"{AIO_USERNAME}/feeds/yolohome-fan"
FEED_LED = f"{AIO_USERNAME}/feeds/yolohome-led"

class AdafruitMQTTClient:
    def __init__(self):
        self.client = mqtt.Client()
        self.client.username_pw_set(AIO_USERNAME, AIO_KEY)
        
        # Set callbacks
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect
        
        self.connected = False
    
    def on_connect(self, client, userdata, flags, rc):
        """Called when connected to Adafruit IO"""
        if rc == 0:
            print("✅ Connected to Adafruit IO!")
            self.connected = True
            
            # Subscribe to all feeds
            client.subscribe(f"{AIO_USERNAME}/feeds/#")
            print(f"📡 Subscribed to all feeds: {AIO_USERNAME}/feeds/#")
        else:
            print(f"❌ Failed to connect to Adafruit IO. Code: {rc}")
    
    def on_message(self, client, userdata, msg):
        """Called when message received from Adafruit IO"""
        topic = msg.topic
        payload = msg.payload.decode()
        
        print(f"📨 Received: {topic} = {payload}")
        
        # Save sensor data to database
        if "temperature" in topic or "humidity" in topic:
            self.save_sensor_data(topic, payload)
    
    def on_disconnect(self, client, userdata, rc):
        """Called when disconnected from Adafruit IO"""
        self.connected = False
        print("⚠️ Disconnected from Adafruit IO")
        if rc != 0:
            print("🔄 Attempting to reconnect...")
    
    def save_sensor_data(self, topic, value):
        """Save sensor data to PostgreSQL database"""
        try:
            db = SessionLocal()
            
            # Parse the value
            float_value = float(value)
            
            # Determine if it's temperature or humidity
            if "temperature" in topic:
                # Save temperature
                sensor = SensorHistory(
                    temperature=float_value,
                    humidity=None,
                    recorded_at=datetime.utcnow()
                )
                print(f"💾 Saved temperature: {float_value}°C")
            elif "humidity" in topic:
                # Save humidity
                sensor = SensorHistory(
                    temperature=None,
                    humidity=float_value,
                    recorded_at=datetime.utcnow()
                )
                print(f"💾 Saved humidity: {float_value}%")
            
            db.add(sensor)
            db.commit()
            db.close()
            
        except Exception as e:
            print(f"❌ Error saving sensor data: {e}")
    
    def connect(self):
        """Connect to Adafruit IO MQTT broker"""
        try:
            print("🔌 Connecting to Adafruit IO...")
            self.client.connect("io.adafruit.com", 1883, 60)
            self.client.loop_start()  # Run in background thread
            return True
        except Exception as e:
            print(f"❌ Failed to connect: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from Adafruit IO"""
        self.client.loop_stop()
        self.client.disconnect()
        print("👋 Disconnected from Adafruit IO")
    
    def publish(self, feed, value):
        """Publish value to Adafruit IO feed"""
        if not self.connected:
            print("⚠️ Not connected to Adafruit IO")
            return False
        
        topic = f"{AIO_USERNAME}/feeds/{feed}"
        self.client.publish(topic, str(value))
        print(f"📤 Published: {topic} = {value}")
        return True

# Global instance
mqtt_client = AdafruitMQTTClient()
