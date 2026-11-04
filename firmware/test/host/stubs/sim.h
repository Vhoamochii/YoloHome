// Controls for the host simulation. Not part of any real API.
#pragma once
#include <stdint.h>
#include <map>
#include <string>
#include <vector>
namespace sim {
extern uint32_t ms;                       // fake millis()
extern bool wifi, broker;                 // WiFi associated / Adafruit IO reachable
extern int reconnectCalls, runCalls;
extern int ledLevel, ledToggles;          // on-board LED (digitalWrite)
extern uint32_t rgbColor;                  // last colour shown on the RGB LED
struct Saved { uint32_t ms; std::string feed, value; };
extern std::vector<Saved> saved;          // everything the board published
extern std::map<std::string, std::string> lastValue;   // what Adafruit would return for /get
void deliver(const std::string& feed, const std::string& value);  // queue an inbound message
void reset();
}
