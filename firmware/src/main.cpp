// main.cpp — YoloHome firmware (Yolo Uno or Yolo:Bit: the pins come from config.h).
//
//   task          core  prio  role
//   cloud           0    2    Adafruit IO link (adafruitio_task)
//   sensor          1    3    DHT20 (+ light, PIR) every 2 s
//   control         1    4    safety / lockdown / schedule / AI, actuators, ACKs
//   display         1    1    LCD, status LEDs, button
#include <Arduino.h>
#include <math.h>

#include "adafruitio_task.h"
#include "config.h"
#include "control_task.h"
#include "display_task.h"
#include "i2c_bus.h"
#include "sensor_task.h"
#include "tinyml_task.h"

EventGroupHandle_t gSystemEvents = nullptr;

#define TOSTR_(x) #x
#define TOSTR(x) TOSTR_(x)

void setup() {
  Serial.begin(115200);
  delay(1500);                                  // time for the USB serial monitor to attach
  Serial.printf("\n=== YoloHome on %s ===\n", BOARD_NAME);

  Serial.printf("light sensor: %s | motion sensor: %s\n",
                SENSOR_HAS_LIGHT ? "on (LIGHT_PIN " TOSTR(LIGHT_PIN) ")" : "off (add -D SENSOR_HAS_LIGHT=1)",
                SENSOR_HAS_PIR ? "on (PIR_PIN " TOSTR(PIR_PIN) ")" : "off (add -D SENSOR_HAS_PIR=1)");

  i2c_bus_init();                               // FIRST: start I2C on the right pins
  i2c_scan();
  gSystemEvents = xEventGroupCreate();
  cloud_init();                                 // queues before any task uses them

  xTaskCreatePinnedToCore(task_adafruitio, "cloud", 8192, nullptr, 2, nullptr, 0);
  xTaskCreatePinnedToCore(task_sensor, "sensor", 4096, nullptr, 3, nullptr, 1);
  xTaskCreatePinnedToCore(task_control, "control", 6144, nullptr, 4, nullptr, 1);
  xTaskCreatePinnedToCore(task_display, "display", 4096, nullptr, 1, nullptr, 1);
  xTaskCreatePinnedToCore(task_tinyml_fire, "tinyml", 4096, nullptr, 2, nullptr, 1);
}

void loop() {
  static uint32_t last = 0;
  if (millis() - last >= 10000) {               // one status line every 10 s
    last = millis();
    ControlStatus s;
    CloudStats c = cloud_stats();
    SensorReading r;
    bool haveReading = sensor_latest(r);
    char light[12] = "n/a", motion[8] = "n/a";
    if (haveReading && !isnan(r.light)) snprintf(light, sizeof light, "%.0f%%", double(r.light));
    if (haveReading && r.presenceValid) snprintf(motion, sizeof motion, "%s", r.presence ? "yes" : "no");
    if (control_status(s)) {
      Serial.printf("[status] %s%s | T=%.1f RH=%.0f light=%s motion=%s t15=%.1f%s | fan %u%% | "
                    "cloud %s, published %lu, backlog %u\n",
                    s.safety ? "SAFETY " : "", ctl::modeName(s.mode), double(s.temp),
                    double(s.humi), light, motion, double(s.t15),
                    s.usesModel ? " (model)" : " (trend)", s.fan, s.cloudUp ? "UP" : "down",
                    (unsigned long)c.published, unsigned(c.backlog));
    }
  }
  vTaskDelay(pdMS_TO_TICKS(200));
}