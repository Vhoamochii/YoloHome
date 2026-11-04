// Stub mirroring Adafruit IO Arduino v4.3.7 + Adafruit MQTT Library signatures used by the task.
#pragma once
#include <stdint.h>
#include <cstdlib>
#include <cstring>
#include <string>
#include "Arduino.h"
typedef enum {
  AIO_IDLE = 0, AIO_NET_DISCONNECTED = 1, AIO_DISCONNECTED = 2, AIO_FINGERPRINT_UNKOWN = 3,
  AIO_NET_CONNECT_FAILED = 10, AIO_CONNECT_FAILED = 11, AIO_FINGERPRINT_INVALID = 12,
  AIO_AUTH_FAILED = 13, AIO_SSID_INVALID = 14,
  AIO_NET_CONNECTED = 20, AIO_CONNECTED = 21, AIO_CONNECTED_INSECURE = 22,
  AIO_FINGERPRINT_UNSUPPORTED = 23, AIO_FINGERPRINT_VALID = 24
} aio_status_t;
#define AIO_PING_INTERVAL 60000
#define AIO_DATA_LENGTH 45

class AdafruitIO_Data {
 public:
  char _value[AIO_DATA_LENGTH];
  char* value() { return _value; }
};
typedef void (*AdafruitIODataCallbackType)(AdafruitIO_Data* data);

class AdafruitIO_Feed {
 public:
  explicit AdafruitIO_Feed(const char* name) : name_(name) {}
  bool save(char* value, double lat = 0, double lon = 0, double ele = 0);
  bool get();
  void onMessage(AdafruitIODataCallbackType cb) { cb_ = cb; }
  std::string name_;
  AdafruitIODataCallbackType cb_ = nullptr;
};

class Adafruit_MQTT {
 public:
  void processPackets(int16_t timeout);
  bool ping(uint8_t n = 1) { (void)n; return true; }
  bool connected();
};

class AdafruitIO_WiFi {
 public:
  AdafruitIO_WiFi(const char*, const char*, const char*, const char*) : _mqtt(&mqtt_) {}
  virtual ~AdafruitIO_WiFi() {}
  void connect() {}
  AdafruitIO_Feed* feed(const char* name);
  aio_status_t networkStatus() { return sim::wifi ? AIO_NET_CONNECTED : AIO_NET_DISCONNECTED; }
  aio_status_t mqttStatus(bool fail_fast = false) {
    (void)fail_fast;
    return (sim::wifi && sim::broker) ? AIO_CONNECTED : AIO_DISCONNECTED;
  }
  // The real run() blocks or busy-spins while offline. The task must never call it.
  aio_status_t run(uint16_t = 0, bool = false) { ++sim::runCalls; std::abort(); }
 protected:
  Adafruit_MQTT* _mqtt;
  uint32_t _last_ping = 0;
 private:
  Adafruit_MQTT mqtt_;
};
