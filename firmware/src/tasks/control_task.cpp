// control_task.cpp — see control_task.h. Owns the Controller; nothing else touches it.
#include "control_task.h"

#include <Arduino.h>
#include <freertos/semphr.h>
#include <math.h>
#include <string.h>
#include <time.h>

#include "actuators.h"
#include "adafruitio_task.h"
#include "config.h"
#include "sensor_task.h"

namespace {
ctl::Controller controller;
SemaphoreHandle_t statusMutex = nullptr;
ControlStatus snapshot = {};
volatile bool cancelRequested = false;
volatile bool fanStepRequested = false;
char lastModeText[cloud::kMaxValue + 1] = "";
bool fanPending = true;
uint32_t lastFanPost = 0;

bool clockSynced() { return time(nullptr) > 1700000000; }

void formatMode(char* buf, size_t n, uint32_t now) {
  if (controller.safety()) {
    snprintf(buf, n, "SAFETY_OVERRIDE");
  } else if (controller.mode() == ctl::Mode::ManualLockdown) {
    uint32_t left = controller.lockRemainingMs(now);
    if (clockSynced()) {
      time_t until = time(nullptr) + time_t(left / 1000) + TZ_OFFSET_S;
      struct tm t;
      gmtime_r(&until, &t);
      snprintf(buf, n, "MANUAL_LOCKDOWN until %02d:%02d", t.tm_hour, t.tm_min);
    } else {
      snprintf(buf, n, "MANUAL_LOCKDOWN %lu min", (unsigned long)((left + 59999) / 60000));
    }
  } else {
    snprintf(buf, n, "%s", ctl::modeName(controller.mode()));
  }
}

void handleCommands(uint32_t now) {
  CloudCommandMsg m;
  char val[12];
  while (xQueueReceive(qCloudCommands, &m, 0) == pdTRUE) {
    ctl::Controller::Result r = controller.command(m.cmd, now);
    cloud::formatValue(m.cmd, val, sizeof val);
    cloud_post_ack(m.cmd.device, m.cmd.id, r.ok, val, m.cmd.actor, r.reason);
    Serial.printf("[ctl] %s %s from %c -> %s%s%s\n", cloud::deviceName(m.cmd.device), val,
                  cloud::actorCode(m.cmd.actor), r.ok ? "accepted" : "refused",
                  r.reason ? ": " : "", r.reason ? r.reason : "");
    if (r.ok && m.cmd.device == cloud::Device::Fan) lastFanPost = 0;   // report right away
  }
}

void publishState(uint32_t now) {
  ctl::Event e;
  while (controller.popEvent(e)) {
    cloud_post_event(e.type, e.data);
    Serial.printf("[ctl] event %s:%s\n", e.type, e.data);
  }
  if (controller.takeModeChanged()) {
    char text[cloud::kMaxValue + 1];
    formatMode(text, sizeof text, now);
    if (strcmp(text, lastModeText) != 0) {
      strncpy(lastModeText, text, sizeof lastModeText);
      cloud_post_mode(text);
      Serial.printf("[ctl] mode %s\n", text);
    }
  }
  if (controller.takeFanChanged()) fanPending = true;
  // fan state at most every 15 s (AI ramps would otherwise eat the rate budget), commands at once
  if (fanPending && (lastFanPost == 0 || now - lastFanPost >= 15000)) {
    cloud_post_fan_state(controller.fan());
    fanPending = false;
    lastFanPost = now ? now : 1;
  }
}
}  // namespace

bool control_status(ControlStatus& out) {
  if (!statusMutex || xSemaphoreTake(statusMutex, pdMS_TO_TICKS(10)) != pdTRUE) return false;
  out = snapshot;
  xSemaphoreGive(statusMutex);
  return true;
}

void control_request_cancel_lockdown() { cancelRequested = true; }
void control_request_fan_step() { fanStepRequested = true; }

void task_control(void* parameter) {
  (void)parameter;
  statusMutex = xSemaphoreCreateMutex();
  actuators_init();
  uint32_t lastSensorTs = 0;
  for (;;) {
    uint32_t now = millis();
    bool cloudUp = gSystemEvents && (xEventGroupGetBits(gSystemEvents) & EVT_CLOUD_UP);

    handleCommands(now);
    if (cancelRequested) {                              // SW2
      cancelRequested = false;
      controller.cancelLockdown(now);
      cloud_post_event("BTN", "AUTO");
      Serial.println("[ctl] SW2: back to AUTO");
    }
    if (fanStepRequested) {                             // SW1
      fanStepRequested = false;
      ctl::Controller::Result r = controller.localFanStep(now);
      char data[16];
      snprintf(data, sizeof data, "FAN:%u", controller.fan());
      if (r.ok) {
        cloud_post_event("BTN", data);
        lastFanPost = 0;                                  // report the new speed right away
      }
      Serial.printf("[ctl] SW1: fan %u%%%s%s\n", controller.fan(), r.ok ? "" : " (refused: ",
                    r.ok ? "" : r.reason);
      if (!r.ok) Serial.println(")");
    }
    SensorReading s;
    if (sensor_latest(s) && s.timestamp != lastSensorTs) {
      lastSensorTs = s.timestamp;
      if (clockSynced()) {
        time_t local = time(nullptr) + TZ_OFFSET_S;
        struct tm t;
        gmtime_r(&local, &t);
        controller.setHourOfDay(t.tm_hour + t.tm_min / 60.0f);
      }
      controller.reading({s.timestamp, s.temperature, s.humidity, s.light, s.presence,
                          s.presenceValid});
    }
    controller.tick(now, cloudUp);

    act_fan(controller.fan());
    act_strip(controller.led());
    act_relay(controller.relay());
    act_buzzer(controller.buzzer(now));
    publishState(now);

    if (xSemaphoreTake(statusMutex, pdMS_TO_TICKS(10)) == pdTRUE) {
      const ctl::Forecaster& f = controller.forecaster();
      snapshot = {controller.mode(), controller.safety(), controller.hot(), controller.anomaly(), cloudUp,
                  f.ready(), f.usesModel(), controller.fan(), controller.led(),
                  controller.lockRemainingMs(now), controller.lastT(), controller.lastH(),
                  f.minutes() ? f.predictT(15) : NAN};
      xSemaphoreGive(statusMutex);
    }
    vTaskDelay(pdMS_TO_TICKS(100));
  }
}