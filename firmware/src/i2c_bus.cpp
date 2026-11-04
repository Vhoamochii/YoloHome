// i2c_bus.cpp — see i2c_bus.h.
#include "i2c_bus.h"

#include <Arduino.h>
#include <Wire.h>

#include "config.h"

SemaphoreHandle_t gI2cMutex = nullptr;

void i2c_bus_init() {
  if (!gI2cMutex) gI2cMutex = xSemaphoreCreateMutex();
  Wire.begin(DHT_SDA, DHT_SCL);
}

void i2c_scan() {
  I2cLock lock;
  Serial.printf("I2C scan (SDA %d, SCL %d):", DHT_SDA, DHT_SCL);
  int found = 0;
  for (uint8_t addr = 1; addr < 127; ++addr) {
    Wire.beginTransmission(addr);
    if (Wire.endTransmission() == 0) {
      Serial.printf(" 0x%02X", addr);
      ++found;
    }
  }
  Serial.println(found ? "   (DHT20 = 0x38)" : " nothing answered: check the I2C port");
}
