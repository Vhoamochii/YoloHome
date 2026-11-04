#pragma once
#include "sim.h"
enum { WL_IDLE_STATUS = 0, WL_CONNECTED = 3, WL_CONNECT_FAILED = 4, WL_DISCONNECTED = 6 };
struct WiFiClass {
  int status() { return sim::wifi ? WL_CONNECTED : WL_DISCONNECTED; }
  bool reconnect() { ++sim::reconnectCalls; return true; }
};
extern WiFiClass WiFi;
