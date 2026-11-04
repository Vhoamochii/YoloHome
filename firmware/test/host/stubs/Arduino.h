#pragma once
#include <stdint.h>
#include <time.h>
#include "sim.h"
inline uint32_t millis() { return sim::ms; }
inline void delay(uint32_t d) { sim::ms += d; }
#define HIGH 1
#define LOW 0
#define OUTPUT 0x03
inline void pinMode(uint8_t, uint8_t) {}
inline void digitalWrite(uint8_t, uint8_t v) {
  if (int(v) != sim::ledLevel) { sim::ledLevel = v; ++sim::ledToggles; }
}
struct SerialStub {
  void begin(unsigned long) {}
  int printf(const char*, ...) { return 0; }
  size_t print(const char*) { return 0; }
  size_t println(const char*) { return 0; }
};
extern SerialStub Serial;
inline void configTime(long, int, const char*, const char* = nullptr, const char* = nullptr) {}
