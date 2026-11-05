// tinyml_task.cpp — FreeRTOS task for on-chip TinyML fire inference.
#include "tinyml_task.h"

#include <Arduino.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <string.h>

#include "adafruitio_task.h"
#include "fire_engine.h"
#include "fire_serial.h"
#include "sensor_task.h"

namespace {
portMUX_TYPE sMux = portMUX_INITIALIZER_UNLOCKED;
TinyMlStatus sStatus = {NAN, false, false, false, false, 0};
}  // namespace

bool tinyml_status(TinyMlStatus& out) {
  portENTER_CRITICAL(&sMux);
  out = sStatus;
  portEXIT_CRITICAL(&sMux);
  return out.lastUpdateMs != 0;
}

void task_tinyml_fire(void* parameter) {
  (void)parameter;
  tinyfire::Engine engine;
  uint32_t lastSensor = 0, lastProcess = 0, seq = 0, lastEvent = 0;
  bool haveReading = false, sent = false, sawSensor = false;
  char reportedState[20] = "";

  Serial.printf("[tinyml] task started. Model: %s (ml_on: %.2f, ml_off: %.2f)\n",
                tinyfire::weights::id,
                tinyfire::alarm_config::ml_on_score,
                tinyfire::alarm_config::ml_off_score);

  for (;;) {
    SensorReading s;
    const uint32_t now = millis();
    bool got = sensor_latest(s);
    bool fresh = got && uint32_t(now - s.timestamp) <= 6000;
    bool changed = got && (!sawSensor || s.timestamp != lastSensor);

    if (changed || (!fresh && (!haveReading || uint32_t(now - lastProcess) >= 2000))) {
      const float t = fresh ? s.temperature : NAN;
      const float h = fresh ? s.humidity : NAN;
      if (got) {
        lastSensor = s.timestamp;
        sawSensor = true;
      }
      lastProcess = now;
      haveReading = true;

      const uint32_t beginUs = micros();
      tinyfire::Result r = engine.update(t, h);
      const uint32_t us = micros() - beginUs;

      // Update thread-safe status for display and control
      portENTER_CRITICAL(&sMux);
      sStatus.score = r.score;
      sStatus.alarm = r.alarm;
      sStatus.ml = r.ml;
      sStatus.heat = r.heat;
      sStatus.valid = r.valid;
      sStatus.lastUpdateMs = now;
      portEXIT_CRITICAL(&sMux);

      // Emit JSON telemetry over Serial
      tinyfire::emit(r, t, h, now, ++seq, us, false);

      // Cloud event publication via existing Adafruit IO event queue
      // Immediate push on state change (OK <-> ALERT), rate-limited heartbeat every 60s
      bool stateChanged = strcmp(reportedState, r.state) != 0;
      bool heartbeatDue = uint32_t(now - lastEvent) >= 60000;

      if (!sent || stateChanged || heartbeatDue) {
        char data[28];
        snprintf(data, sizeof data, "%s:%.3f", r.state, double(r.valid ? r.score : -1.0f));
        if (cloud_post_event("TINYML", data)) {
          snprintf(reportedState, sizeof reportedState, "%s", r.state);
          lastEvent = now;
          sent = true;
        }
      }
    }
    vTaskDelay(pdMS_TO_TICKS(100));
  }
}

