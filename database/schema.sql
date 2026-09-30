-- Users table
CREATE TABLE nguoi_dung (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    name VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Face profiles table
CREATE TABLE face_profiles (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES nguoi_dung(id),
    face_encoding BYTEA,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Devices table
CREATE TABLE thiet_bi (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(50), -- 'fan', 'led', 'sensor'
    location VARCHAR(255),
    adafruit_feed VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Device status table
CREATE TABLE trang_thai_thiet_bi (
    id SERIAL PRIMARY KEY,
    device_id INTEGER REFERENCES thiet_bi(id),
    status BOOLEAN DEFAULT false,
    speed INTEGER DEFAULT 0,
    color VARCHAR(50),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Sensor history table
CREATE TABLE lich_su_cam_bien (
    id SERIAL PRIMARY KEY,
    temperature FLOAT,
    humidity FLOAT,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Schedule table
CREATE TABLE lich_trinh (
    id SERIAL PRIMARY KEY,
    device_id INTEGER REFERENCES thiet_bi(id),
    action VARCHAR(50), -- 'on', 'off'
    scheduled_time TIME,
    repeat_mode VARCHAR(50), -- 'daily', 'weekly'
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
