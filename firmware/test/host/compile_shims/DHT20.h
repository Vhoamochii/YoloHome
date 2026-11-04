// mirrors RobTillaart DHT20 0.3.x
#pragma once
#include "Wire.h"
#define DHT20_OK 0
#define DHT20_ERROR_CONNECT -11
class DHT20 { public: DHT20(TwoWire* wire = &Wire) { (void)wire; } bool begin() { return true; } int read() { return DHT20_OK; } float getTemperature() { return 0; } float getHumidity() { return 0; } };
