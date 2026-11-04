// Stub mirroring the Adafruit NeoPixel signatures used by the demo.
#pragma once
#include <stdint.h>
#include "sim.h"
#define NEO_GRB 0x52
#define NEO_KHZ800 0x0000
class Adafruit_NeoPixel {
 public:
  Adafruit_NeoPixel(uint16_t n, int16_t pin, uint16_t type) : n_(n) { (void)pin; (void)type; }
  uint16_t numPixels() const { return n_; }
  void begin() {}
  void setBrightness(uint8_t) {}
  static uint32_t Color(uint8_t r, uint8_t g, uint8_t b) {
    return (uint32_t(r) << 16) | (uint32_t(g) << 8) | b;
  }
  void setPixelColor(uint16_t, uint32_t c) { pending_ = c; }
  void show() { sim::rgbColor = pending_; }
 private:
  uint16_t n_ = 1;
  uint32_t pending_ = 0;
};
