#include <deque>
#include <map>
#include <memory>
#include <string>
#include <vector>
#include "AdafruitIO_WiFi.h"
#include "WiFi.h"
#include "freertos/queue.h"
#include "sim.h"
WiFiClass WiFi;
SerialStub Serial;
namespace sim {
uint32_t ms = 0;
bool wifi = true, broker = true;
int reconnectCalls = 0, runCalls = 0;
int ledLevel = 0, ledToggles = 0;
uint32_t rgbColor = 0;
std::vector<Saved> saved;
std::map<std::string, std::string> lastValue;
std::map<std::string, AdafruitIO_Feed*> feeds;
std::deque<std::pair<std::string, std::string>> inbound;
void deliver(const std::string& f, const std::string& v) { inbound.push_back({f, v}); }
void reset() { ms = 0; wifi = broker = true; reconnectCalls = runCalls = 0; ledLevel = ledToggles = 0; rgbColor = 0; saved.clear(); lastValue.clear(); inbound.clear(); }
}
bool Adafruit_MQTT::connected() { return sim::wifi && sim::broker; }
void Adafruit_MQTT::processPackets(int16_t) {
  while (connected() && !sim::inbound.empty()) {
    auto m = sim::inbound.front(); sim::inbound.pop_front();
    auto it = sim::feeds.find(m.first);
    if (it == sim::feeds.end() || !it->second->cb_) continue;
    AdafruitIO_Data d;
    std::strncpy(d._value, m.second.c_str(), AIO_DATA_LENGTH - 1);
    d._value[AIO_DATA_LENGTH - 1] = 0;
    it->second->cb_(&d);
  }
}
AdafruitIO_Feed* AdafruitIO_WiFi::feed(const char* name) {
  auto* f = new AdafruitIO_Feed(name); sim::feeds[name] = f; return f;
}
bool AdafruitIO_Feed::save(char* value, double, double, double) {
  if (!(sim::wifi && sim::broker)) return false;
  if (std::strlen(value) >= AIO_DATA_LENGTH) std::abort();   // would overflow the real library
  sim::saved.push_back({sim::ms, name_, value});
  sim::lastValue[name_] = value;
  return true;
}
bool AdafruitIO_Feed::get() {
  auto it = sim::lastValue.find(name_);
  if (it != sim::lastValue.end()) sim::deliver(name_, it->second);
  return true;
}
struct SimQueue { size_t len, size; std::deque<std::vector<char>> items; };
QueueHandle_t xQueueCreate(UBaseType_t l, UBaseType_t s) { return new SimQueue{l, s, {}}; }
BaseType_t xQueueSend(QueueHandle_t q, const void* item, TickType_t) {
  if (q->items.size() >= q->len) return pdFALSE;
  const char* p = static_cast<const char*>(item);
  q->items.emplace_back(p, p + q->size); return pdTRUE;
}
BaseType_t xQueueReceive(QueueHandle_t q, void* item, TickType_t) {
  if (q->items.empty()) return pdFALSE;
  std::memcpy(item, q->items.front().data(), q->size); q->items.pop_front(); return pdTRUE;
}
