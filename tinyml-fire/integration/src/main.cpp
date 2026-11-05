// Reuse the exact group's entry point, with setup renamed only in this translation unit.
#define setup yolohome_setup
#include "../../../firmware/src/main.cpp"
#undef setup
#include "fire_serial.h"
#include <string.h>

namespace {
void task_tinyml_fire(void*) {
  tinyfire::Engine engine;
  uint32_t lastSensor = 0, lastProcess = 0, seq = 0, lastEvent = 0;
  bool haveReading = false, sent = false, sawSensor = false;
  char reported[20] = "";
  for (;;) {
    SensorReading s;
    const uint32_t now = millis();
    bool got = sensor_latest(s);
    bool fresh = got && uint32_t(now - s.timestamp) <= 6000;
    bool changed = got && (!sawSensor || s.timestamp != lastSensor);
    if (changed || (!fresh && (!haveReading || uint32_t(now - lastProcess) >= 2000))) {
      const float t = fresh ? s.temperature : NAN;
      const float h = fresh ? s.humidity : NAN;
      if (got) { lastSensor = s.timestamp; sawSensor = true; }
      lastProcess = now;
      haveReading = true;
      const uint32_t beginUs = micros();
      tinyfire::Result r = engine.update(t, h);
      const uint32_t us = micros() - beginUs;
      tinyfire::emit(r, t, h, now, ++seq, us, false);
      // Existing cloud queue owns all MQTT. <=44 bytes; no new feed or network client.
      // Coalesce transitions/heartbeats to at most one event per 30 seconds.
      if (!sent || uint32_t(now - lastEvent) >= 30000) {
        char data[28];
        snprintf(data, sizeof data, "%s:%.3f", r.state, double(r.valid ? r.score : -1));
        if (strcmp(reported, r.state) || uint32_t(now - lastEvent) >= 60000) {
          if (cloud_post_event("TINYML", data)) {
            snprintf(reported, sizeof reported, "%s", r.state);
            lastEvent = now;
            sent = true;
          }
        }
      }
    }
    vTaskDelay(pdMS_TO_TICKS(100));
  }
}
}

void setup() {
  yolohome_setup();
  // No second Wire.begin(), no second sensor owner, no extra actuator writer.
  if (xTaskCreatePinnedToCore(task_tinyml_fire, "tinyml_fire", 4096, nullptr, 1,
                            nullptr, 1) != pdPASS) {
    Serial.println("[tinyml] ERROR: cannot create inference task");
  }
}
