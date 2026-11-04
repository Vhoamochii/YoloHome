// actuators.cpp — see actuators.h. Writes only on change.
#include "actuators.h"

#include <Adafruit_NeoPixel.h>
#include <Arduino.h>
#include <esp_arduino_version.h>

#include "config.h"

namespace {
Adafruit_NeoPixel strip(STRIP_LED_COUNT, LED_PIN, NEO_GRB + NEO_KHZ800);
Adafruit_NeoPixel status(1, ONBOARD_RGB_PIN, NEO_GRB + NEO_KHZ800);
constexpr uint32_t kFanHz = 25000;              // above hearing range
constexpr uint8_t kFanChannel = 0, kBuzzerChannel = 2;   // different LEDC timers
int lastFan = -1, lastRelay = -1, lastBuzz = -1;
uint32_t lastStrip = 0xFFFFFFFF, lastStatus = 0xFFFFFFFF;

void showAll(Adafruit_NeoPixel& px, uint32_t rgb) {
  for (uint16_t i = 0; i < px.numPixels(); ++i)
    px.setPixelColor(i, px.Color((rgb >> 16) & 0xFF, (rgb >> 8) & 0xFF, rgb & 0xFF));
  px.show();
}
}  // namespace

void actuators_init() {
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcAttach(FAN_PIN, kFanHz, 8);
#else
  ledcSetup(kFanChannel, kFanHz, 8);
  ledcAttachPin(FAN_PIN, kFanChannel);
#endif
#if RELAY_PIN >= 0
  pinMode(RELAY_PIN, OUTPUT);
#endif
#if BUZZER_PIN >= 0
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcAttach(BUZZER_PIN, 2000, 8);
#else
  ledcSetup(kBuzzerChannel, 2000, 8);
  ledcAttachPin(BUZZER_PIN, kBuzzerChannel);
#endif
#endif
#if ONBOARD_LED_PIN >= 0
  pinMode(ONBOARD_LED_PIN, OUTPUT);
#endif
  strip.begin();
  strip.setBrightness(60);
  status.begin();
  status.setBrightness(30);
  act_fan(0);
  act_strip(0);
  act_relay(false);
  act_buzzer(false);
  act_status(0);
}

void act_fan(uint8_t pct) {
  if (pct > 100) pct = 100;
  if (pct == lastFan) return;
  lastFan = pct;
  uint32_t duty = (uint32_t(pct) * 255 + 50) / 100;
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcWrite(FAN_PIN, duty);
#else
  ledcWrite(kFanChannel, duty);
#endif
}

void act_strip(uint32_t rgb) {
  if (rgb == lastStrip) return;
  lastStrip = rgb;
  showAll(strip, rgb);
}

void act_relay(bool on) {
#if RELAY_PIN >= 0
  if (int(on) == lastRelay) return;
  lastRelay = on;
  digitalWrite(RELAY_PIN, on ? HIGH : LOW);
#else
  (void)on;
#endif
}

void act_buzzer(bool on) {
#if BUZZER_PIN >= 0
  if (int(on) == lastBuzz) return;
  lastBuzz = on;
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcWriteTone(BUZZER_PIN, on ? 2000 : 0);
#else
  ledcWriteTone(kBuzzerChannel, on ? 2000 : 0);
#endif
#else
  (void)on;
#endif
}

void act_status(uint32_t rgb) {
  if (rgb == lastStatus) return;
  lastStatus = rgb;
  showAll(status, rgb);
}

void act_heartbeat(bool on) {
#if ONBOARD_LED_PIN >= 0
  digitalWrite(ONBOARD_LED_PIN, on ? HIGH : LOW);
#else
  (void)on;
#endif
}
