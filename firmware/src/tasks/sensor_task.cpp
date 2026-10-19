// sensor_task.cpp — see sensor_task.h.
#include "sensor_task.h"

#include <DHT20.h>      // lib_deps: robtillaart/DHT20 (I2C). NOT <DHT.h>: that one has no DHT20.
#include <Wire.h>
#include <freertos/semphr.h>
#include <math.h>

#include "adafruitio_task.h"
#include "config.h"

namespace {

DHT20 dht;                                   // uses Wire, started below on the right pins
SemaphoreHandle_t latestMutex = nullptr;
SensorReading latest = {NAN, NAN, NAN, false, false, 0};
bool haveLatest = false;
bool dhtReady = false;
uint32_t lastBeginTry = 0;

#if SENSOR_HAS_LIGHT
float readLightPercent() {
  int raw = analogRead(LIGHT_PIN);           // 12-bit: 0..4095
  float pct = raw * 100.0f / 4095.0f;
  return SENSOR_LIGHT_INVERT ? 100.0f - pct : pct;
}
#endif

void tryStartDht() {
  lastBeginTry = millis();
  dhtReady = dht.begin();                    // just checks the sensor answers on I2C
  Serial.println(dhtReady ? "[sensor] DHT20 found"
                          : "[sensor] DHT20 not found: check it is on the I2C port (SDA 11, SCL 12)");
}

}  // namespace

bool sensor_latest(SensorReading& out) {
  if (!latestMutex || xSemaphoreTake(latestMutex, pdMS_TO_TICKS(10)) != pdTRUE) return false;
  bool ok = haveLatest;
  if (ok) out = latest;
  xSemaphoreGive(latestMutex);
  return ok;
}

void task_sensor(void* parameter) {
  (void)parameter;
  latestMutex = xSemaphoreCreateMutex();

  // FIRST, before any I2C device: with boards/yolo_uno.json the names SDA/SCL mean 38/39
  // (M5Stack AtomS3), and DHT20::begin() does not start the bus itself.
  Wire.begin(DHT_SDA, DHT_SCL);
#if SENSOR_HAS_PIR
  pinMode(PIR_PIN, INPUT);
#endif
#if SENSOR_HAS_LIGHT
  analogReadResolution(12);
#endif
  vTaskDelay(pdMS_TO_TICKS(100));            // the DHT20 needs ~100 ms after power-up
  tryStartDht();

  TickType_t lastWake = xTaskGetTickCount();
  for (;;) {
    SensorReading r = {NAN, NAN, NAN, false, false, millis()};

    if (!dhtReady && millis() - lastBeginTry > 5000) tryStartDht();   // plugged in later
    if (dhtReady) {
      int status = dht.read();
      if (status == DHT20_OK) {
        r.temperature = dht.getTemperature();
        r.humidity = dht.getHumidity();
      } else {
        Serial.printf("[sensor] DHT20 read error %d\n", status);
        if (status == DHT20_ERROR_CONNECT) dhtReady = false;          // unplugged: re-detect
      }
    }
#if SENSOR_HAS_LIGHT
    r.light = readLightPercent();
#endif
#if SENSOR_HAS_PIR
    r.presence = digitalRead(PIR_PIN) == HIGH;
    r.presenceValid = true;
#endif

    // 1. cloud task: NaN fields are simply not published
    cloud::Sample s;
    s.temp = r.temperature;
    s.humi = r.humidity;
    s.light = r.light;
    s.presence = r.presence;
    s.presenceValid = r.presenceValid;
    cloud_post_sample(s);

    // 2. latest reading for other tasks
    if (latestMutex && xSemaphoreTake(latestMutex, pdMS_TO_TICKS(10)) == pdTRUE) {
      latest = r;
      haveLatest = true;
      xSemaphoreGive(latestMutex);
    }

#ifdef SENSOR_FORWARD_FRAMES
    // 3. your existing pipeline (TinyML / control): only complete readings, never blocking,
    //    so a stalled consumer cannot stop the sensing.
    if (qSensorFrames && !isnan(r.temperature) && !isnan(r.humidity)) {
      SensorFrame frame = {};
      frame.temperature = r.temperature;
      frame.humidity = r.humidity;
      frame.timestamp = r.timestamp;
      xQueueSend(qSensorFrames, &frame, 0);
    }
#endif

    vTaskDelayUntil(&lastWake, pdMS_TO_TICKS(SENSOR_PERIOD_MS));   // steady 2 s, no drift
  }
}