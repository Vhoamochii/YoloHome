// sensor_task.h — reads the DHT20 every 2 s (plus the light sensor and PIR when plugged in)
// and hands each reading to:
//   1. the cloud task            (cloud_post_sample -> Adafruit IO)
//   2. your existing pipeline    (SensorFrame -> qSensorFrames, if types.h defines them)
//   3. anyone else               (sensor_latest(): LCD, control logic)
#pragma once
#include <Arduino.h>
#include <freertos/FreeRTOS.h>
#include <freertos/queue.h>

// Optional sensors: set to 1 once the module is plugged in. An unplugged analog pin reads
// noise, and a missing PIR would read as "nobody home".
#ifndef SENSOR_HAS_LIGHT
#define SENSOR_HAS_LIGHT 0
#endif
#ifndef SENSOR_HAS_PIR
#define SENSOR_HAS_PIR 0
#endif
#ifndef SENSOR_LIGHT_INVERT
#define SENSOR_LIGHT_INVERT 0   // set to 1 if the reading goes DOWN when the room gets brighter
#endif
#ifndef SENSOR_PERIOD_MS
#define SENSOR_PERIOD_MS 2000   // the DHT20 needs at least 1 s between reads
#endif

// Your existing frame type and queue, if your project defines them in types.h.
#if __has_include("types.h")
#include "types.h"              // SensorFrame {temperature, humidity, timestamp}, qSensorFrames
#define SENSOR_FORWARD_FRAMES 1
#endif

struct SensorReading {
  float temperature;            // °C,      NaN if the DHT20 read failed
  float humidity;               // %RH,     NaN if the DHT20 read failed
  float light;                  // 0-100 %, NaN if no light sensor
  bool presence;                // motion detected (only meaningful if presenceValid)
  bool presenceValid;           // false when no PIR is plugged in
  uint32_t timestamp;           // millis() of the reading
};

bool sensor_latest(SensorReading& out);   // most recent reading; false before the first one
void task_sensor(void* parameter);         // stack 4096