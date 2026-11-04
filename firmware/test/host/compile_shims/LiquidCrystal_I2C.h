// mirrors marcoschwartz LiquidCrystal_I2C 1.1.4
#pragma once
#include <cstdint>
#include <cstddef>
class LiquidCrystal_I2C { public: LiquidCrystal_I2C(uint8_t, uint8_t, uint8_t) {} void init() {} void backlight() {} void clear() {} void setCursor(uint8_t, uint8_t) {} size_t print(const char*) { return 0; } };
