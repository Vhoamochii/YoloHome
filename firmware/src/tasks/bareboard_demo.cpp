// bareboard_demo.cpp — see bareboard_demo.h.
#include "bareboard_demo.h"

#include <Adafruit_NeoPixel.h>
#include <math.h>

#include "adafruitio_task.h"
#include "config.h"

#ifndef DEMO_BLINK_ON_MS
#define DEMO_BLINK_ON_MS  1000
#endif
#ifndef DEMO_BLINK_OFF_MS
#define DEMO_BLINK_OFF_MS 1000
#endif
#define DEMO_SAMPLE_MS 500     // how often the LED state is sampled into the cloud task
#define DEMO_STEP_MS    50

namespace {

constexpr bool kBlinkOnRgb = ONBOARD_LED_PIN < 0;   // Yolo:Bit has no single LED
Adafruit_NeoPixel rgb(1, ONBOARD_RGB_PIN, NEO_GRB + NEO_KHZ800);
bool ledOn = false;
uint32_t rgbColor = kBlinkOnRgb ? 0xFFFFFF : 0x000000;   // what yolohome-led last set
uint32_t nextToggle = 0, nextSample = 0;

void showRgb(uint32_t c) {
  rgb.setPixelColor(0, rgb.Color((c >> 16) & 0xFF, (c >> 8) & 0xFF, c & 0xFF));
  rgb.show();
}

void setLed(bool on) {
  ledOn = on;
#if ONBOARD_LED_PIN >= 0
  digitalWrite(ONBOARD_LED_PIN, on ? HIGH : LOW);
#else
  showRgb(on ? rgbColor : 0);
#endif
}

// What the real control-logic task will do: act on the command, then ACK it.
void handle(const cloud::Command& c) {
  char val[12];
  cloud::formatValue(c, val, sizeof val);
  if (c.device == cloud::Device::Led) {
    rgbColor = c.rgb;
    if (!kBlinkOnRgb) showRgb(rgbColor);
    else if (ledOn) showRgb(rgbColor);
    cloud_post_ack(c.device, c.id, true, val, c.actor);
  } else {
    cloud_post_ack(c.device, c.id, false, val, c.actor, "NOHW");   // no fan/relay attached
  }
}

}  // namespace

void bareboard_demo_setup() {
#if ONBOARD_LED_PIN >= 0
  pinMode(ONBOARD_LED_PIN, OUTPUT);
#endif
  rgb.begin();
  rgb.setBrightness(40);                      // full brightness is uncomfortable up close
  showRgb(kBlinkOnRgb ? 0 : rgbColor);
  nextToggle = nextSample = millis();
  cloud_post_mode("BAREBOARD_DEMO");          // queued until the link is up
}

void bareboard_demo_step() {
  uint32_t now = millis();
  if (int32_t(now - nextToggle) >= 0) {
    setLed(!ledOn);
    nextToggle = now + (ledOn ? DEMO_BLINK_ON_MS : DEMO_BLINK_OFF_MS);
  }
  if (int32_t(now - nextSample) >= 0) {
    nextSample += DEMO_SAMPLE_MS;
    cloud::Sample s;
    s.temp = NAN;                             // no DHT20: temperature/humidity not published
    s.humi = NAN;
    s.light = ledOn ? 100.0f : 0.0f;          // the light the board itself generates
    s.presenceValid = false;                  // no motion sensor: presence not published
    cloud_post_sample(s);
  }
  CloudCommandMsg m;
  while (xQueueReceive(qCloudCommands, &m, 0) == pdTRUE) handle(m.cmd);
}

void task_bareboard_demo(void* parameter) {
  (void)parameter;
  bareboard_demo_setup();
  for (;;) {
    bareboard_demo_step();
    vTaskDelay(pdMS_TO_TICKS(DEMO_STEP_MS));
  }
}