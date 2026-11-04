#pragma once
#include <cstdint>
struct TwoWire { bool begin(int = -1, int = -1, uint32_t = 0) { return true; } void beginTransmission(uint8_t) {} uint8_t endTransmission(bool = true) { return 0; } };
extern TwoWire Wire;
