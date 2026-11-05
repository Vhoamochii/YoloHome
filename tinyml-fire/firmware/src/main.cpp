#include <Arduino.h>
#include <Wire.h>
#include <DHT20.h>
#include "fire_config.h"
#include "fire_serial.h"
#include "fire_lcd.h"

namespace {
DHT20 sensor;
tinyfire::Engine engine;
FireLcd display;
bool ready = false;
uint32_t seq = 0, lastSample = 0;
}

void setup() {
  Serial.begin(115200);
  delay(1500);
  pinMode(FIRE_LED_PIN, OUTPUT);
#if FIRE_BUZZER_PIN >= 0
  pinMode(FIRE_BUZZER_PIN, OUTPUT);
  digitalWrite(FIRE_BUZZER_PIN, LOW);
#endif
  Wire.begin(FIRE_SDA, FIRE_SCL);
  Wire.setTimeOut(100);
  delay(150);
  Serial.printf("[tinyml] model=%s; I2C SDA=%d SCL=%d; simulated=%d\n",
                tinyfire::weights::id, FIRE_SDA, FIRE_SCL, TINYML_SIMULATED);
  for (uint8_t a = 1; a < 127; ++a) {
    Wire.beginTransmission(a);
    if (Wire.endTransmission() == 0) Serial.printf("[i2c] 0x%02X\n", a);
  }
  ready = sensor.begin();
  display.begin(TINYML_SIMULATED);
}

void loop() {
  uint32_t now = millis();
  if (uint32_t(now - lastSample) < FIRE_SAMPLE_MS) { delay(5); return; }
  lastSample = now;
  float t = NAN, h = NAN;
#if TINYML_SIMULATED
  // Test: normal -> hot -> invalid -> recovery. Never enabled in the real build.
  const uint32_t phase = (seq / 6) % 4;
  if (phase != 2) { t = phase == 1 ? 50.0f : 28.0f; h = phase == 1 ? 20.0f : 65.0f; }
#else
  if (!ready) ready = sensor.begin();
  if (ready) {
    int status = sensor.read();
    if (status == DHT20_OK) { t = sensor.getTemperature(); h = sensor.getHumidity(); }
    else { ready = false; Serial.printf("[sensor] read error %d\n", status); }
  }
#endif
  uint32_t beginUs = micros();
  tinyfire::Result r = engine.update(t, h);
  uint32_t inferenceUs = micros() - beginUs;
  tinyfire::emit(r, t, h, millis(), ++seq, inferenceUs, TINYML_SIMULATED);
  display.update(r, t, h);
  // Blink for missing sensor, steady light for alarm, off for normal operation.
  digitalWrite(FIRE_LED_PIN, r.alarm || (!r.valid && (seq % 2)) ? HIGH : LOW);
#if FIRE_BUZZER_PIN >= 0
  digitalWrite(FIRE_BUZZER_PIN, r.alarm ? HIGH : LOW);
#endif
}
