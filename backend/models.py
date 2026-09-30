from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Time, LargeBinary
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class User(Base):
    __tablename__ = "nguoi_dung"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False)
    password = Column(String(255), nullable=False)
    name = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)

class FaceProfile(Base):
    __tablename__ = "face_profiles"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("nguoi_dung.id"))
    face_encoding = Column(LargeBinary)
    created_at = Column(DateTime, default=datetime.utcnow)

class Device(Base):
    __tablename__ = "thiet_bi"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    type = Column(String(50))
    location = Column(String(255))
    adafruit_feed = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)

class DeviceStatus(Base):
    __tablename__ = "trang_thai_thiet_bi"
    
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("thiet_bi.id"))
    status = Column(Boolean, default=False)
    speed = Column(Integer, default=0)
    color = Column(String(50))
    updated_at = Column(DateTime, default=datetime.utcnow)

class SensorHistory(Base):
    __tablename__ = "lich_su_cam_bien"
    
    id = Column(Integer, primary_key=True, index=True)
    temperature = Column(Float)
    humidity = Column(Float)
    recorded_at = Column(DateTime, default=datetime.utcnow)

class Schedule(Base):
    __tablename__ = "lich_trinh"
    
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("thiet_bi.id"))
    action = Column(String(50))
    scheduled_time = Column(Time)
    repeat_mode = Column(String(50))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
