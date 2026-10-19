// main.cpp — integration test: real sensors -> sensor task -> cloud task -> Adafruit IO,
// and LED colour commands back from Adafruit IO to the on-board RGB LED.
//
// Prints a status line every 5 s. Plug the DHT20 into the I2C port; enable the light sensor and
// PIR with -D SENSOR_HAS_LIGHT=1 / -D SENSOR_HAS_PIR=1 in platformio.ini when they are attached.
// Do not also start the bare-board demo: both would feed readings to the cloud task.
#include <Arduino.h>
#include <Adafruit_NeoPixel.h>
#include <math.h>

#include "adafruitio_task.h"
#include "config.h"
#include "sensor_task.h"

// Weak: if your firmware already defines these, the linker uses yours instead.
__attribute__((weak)) EventGroupHandle_t gSystemEvents = nullptr;
#ifdef SENSOR_FORWARD_FRAMES
__attribute__((weak)) QueueHandle_t qSensorFrames = nullptr;   // null = not forwarded in this test
#endif

namespace {

Adafruit_NeoPixel rgb(1, ONBOARD_RGB_PIN, NEO_GRB + NEO_KHZ800);

// Stand-in for the control-logic task: LED commands drive the on-board RGB LED, everything
// else is refused, and every command is ACKed so the backend sees the result.
void handleCommands() {
  CloudCommandMsg m;
  char val[12];
  while (xQueueReceive(qCloudCommands, &m, 0) == pdTRUE) {
    cloud::formatValue(m.cmd, val, sizeof val);
    const char* id = m.cmd.id[0] ? m.cmd.id : "-";
    if (m.cmd.device == cloud::Device::Led) {
      uint32_t c = m.cmd.rgb;
      rgb.setPixelColor(0, rgb.Color((c >> 16) & 0xFF, (c >> 8) & 0xFF, c & 0xFF));
      rgb.show();
      cloud_post_ack(m.cmd.device, m.cmd.id, true, val, m.cmd.actor);
      Serial.printf("[cmd]  led -> #%s  (id %s, actor %c)\n", val, id, cloud::actorCode(m.cmd.actor));
    } else {
      cloud_post_ack(m.cmd.device, m.cmd.id, false, val, m.cmd.actor, "NOHW");
      Serial.printf("[cmd]  %s %s refused: no actuator in this test (id %s)\n",
                    cloud::deviceName(m.cmd.device), val, id);
    }
  }
}

const char* fmt(float v, const char* format, char* buf, size_t n) {
  if (isnan(v)) return "n/a";
  snprintf(buf, n, format, double(v));
  return buf;
}

void report() {
  bool up = gSystemEvents && (xEventGroupGetBits(gSystemEvents) & EVT_CLOUD_UP);
  CloudStats s = cloud_stats();
  SensorReading r;
  char t[12], h[12], l[12];
  if (sensor_latest(r)) {
    Serial.printf("[test] T=%s C  RH=%s %%  light=%s %%  motion=%s | cloud %s | published %lu, "
                  "rate-dropped %lu, backlog %u\n",
                  fmt(r.temperature, "%.2f", t, sizeof t), fmt(r.humidity, "%.1f", h, sizeof h),
                  fmt(r.light, "%.0f", l, sizeof l),
                  r.presenceValid ? (r.presence ? "yes" : "no") : "n/a", up ? "UP" : "down",
                  (unsigned long)s.published, (unsigned long)s.rateDropped, unsigned(s.backlog));
  } else {
    Serial.printf("[test] no sensor reading yet | cloud %s\n", up ? "UP" : "down");
  }
}

}  // namespace

void setup() {
  Serial.begin(115200);
  delay(1500);                                  // time for the USB serial monitor to attach
  Serial.println("\n=== YoloHome test: sensor task + Adafruit IO ===");
  Serial.printf("board %s | I2C SDA %d, SCL %d | light %s, PIR %s\n", BOARD_NAME, DHT_SDA, DHT_SCL,
                SENSOR_HAS_LIGHT ? "on" : "off", SENSOR_HAS_PIR ? "on" : "off");

  if (!gSystemEvents) gSystemEvents = xEventGroupCreate();
  cloud_init();                                 // queues first, before any task uses them
  rgb.begin();
  rgb.setBrightness(40);
  rgb.show();                                   // RGB LED off until a colour arrives

  xTaskCreatePinnedToCore(task_adafruitio, "cloud", 8192, nullptr, 2, nullptr, 0);
  xTaskCreatePinnedToCore(task_sensor, "sensor", 4096, nullptr, 3, nullptr, 1);
}

void loop() {
  handleCommands();
  static uint32_t lastReport = 0;
  if (millis() - lastReport >= 5000) {
    lastReport = millis();
    report();
  }
  vTaskDelay(pdMS_TO_TICKS(50));
}