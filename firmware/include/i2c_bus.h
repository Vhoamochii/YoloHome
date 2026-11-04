// i2c_bus.h — one I2C bus shared by the DHT20 (sensor task) and the LCD (display task).
#pragma once
#include <freertos/FreeRTOS.h>
#include <freertos/semphr.h>

extern SemaphoreHandle_t gI2cMutex;

// Call FIRST in setup(), before any task or library touches I2C. Starts the bus on
// DHT_SDA/DHT_SCL: libraries that later call Wire.begin() without pins (the LCD library does)
// then leave it where it is. Do not rely on the names SDA/SCL with boards/yolo_uno.json.
void i2c_bus_init();
void i2c_scan();                 // prints every address that answers, for wiring checks

struct I2cLock {                 // RAII: hold the bus for one device transaction
  I2cLock() { if (gI2cMutex) xSemaphoreTake(gI2cMutex, portMAX_DELAY); }
  ~I2cLock() { if (gI2cMutex) xSemaphoreGive(gI2cMutex); }
  I2cLock(const I2cLock&) = delete;
  I2cLock& operator=(const I2cLock&) = delete;
};
