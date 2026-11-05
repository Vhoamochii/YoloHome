#pragma once
#include <Arduino.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <stdio.h>
#include "fire_engine.h"

// Standalone firmware only: the sensor and LCD share one I2C bus in the same loop.
// Probe ONLY common LCD addresses. Never treat DHT20 at 0x38 as an LCD.
class FireLcd {
 public:
  void begin(bool simulated) {
    simulated_ = simulated;
    tryConnect();  // Wire.begin(FIRE_SDA,FIRE_SCL) must have run first.
    tinyfire::Result initial;
    update(initial, NAN, NAN);
  }

  void update(const tinyfire::Result& result, float temperature, float humidity) {
    if (active_ && !responds(address_)) {
      active_ = nullptr;
      lastProbe_ = millis();
      Serial.println("[lcd] disconnected; retrying periodically");
    }
    if (!active_) {
      if (uint32_t(millis() - lastProbe_) >= 5000u) tryConnect();
      if (!active_) return;  // LCD failure must not stop sensing/inference/USB.
    }

    char values[24], state[24];
    if (result.valid && isfinite(temperature) && isfinite(humidity)) {
      // Fits 16 columns even at -40.0 C and 100 %RH.
      snprintf(values, sizeof values, "T:%5.1fC H:%3.0f%%", double(temperature), double(humidity));
    } else {
      snprintf(values, sizeof values, "T: --.-C H: --%%");
    }
    // SENSOR_ERROR is 12 chars, so prefix + state fits exactly in 16 columns.
    snprintf(state, sizeof state, "%s%s", simulated_ ? "SIM:" : "ST: ", result.state);
    writeLine(0, values);
    writeLine(1, state);
  }

 private:
  LiquidCrystal_I2C lcd21_{0x21, 16, 2};
  LiquidCrystal_I2C lcd27_{0x27, 16, 2};
  LiquidCrystal_I2C lcd3f_{0x3F, 16, 2};
  LiquidCrystal_I2C* active_ = nullptr;
  uint8_t address_ = 0;
  uint32_t lastProbe_ = 0;
  bool simulated_ = false;

  bool responds(uint8_t address) {
    Wire.beginTransmission(address);
    return Wire.endTransmission() == 0;
  }

  void tryConnect() {
    lastProbe_ = millis();
    const uint8_t addresses[] = {0x21, 0x27, 0x3F};
    LiquidCrystal_I2C* displays[] = {&lcd21_, &lcd27_, &lcd3f_};
    for (unsigned i = 0; i < 3; ++i) {
      if (!responds(addresses[i])) continue;
      address_ = addresses[i];
      active_ = displays[i];
      active_->init();
      active_->backlight();
      Serial.printf("[lcd] 16x2 detected at 0x%02X\n", address_);
      return;
    }
    Serial.println("[lcd] no LCD at 0x21/0x27/0x3F; sensing continues");
  }

  void writeLine(uint8_t row, const char* text) {
    char padded[17];
    snprintf(padded, sizeof padded, "%-16.16s", text);
    active_->setCursor(0, row);
    active_->print(padded); // Overwrite old characters; avoid clear() flicker.
  }
};
