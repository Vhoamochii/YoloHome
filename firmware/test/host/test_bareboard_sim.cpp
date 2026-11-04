// The real adafruitio_task.cpp + bareboard_demo.cpp, nothing plugged in, fake clock.
#include <stdio.h>
#include <string.h>
#include <string>
#include <vector>

#include "adafruitio_task.h"
#include "bareboard_demo.h"
#include "config.h"
#include "sim.h"

EventGroupHandle_t gSystemEvents = new SimEvents();
static int failures = 0, checks = 0;
#define CHECK(cond, ...) do { ++checks; if (!(cond)) { ++failures; \
  printf("FAIL %s:%d  ", __FILE__, __LINE__); printf(__VA_ARGS__); printf("\n"); } } while (0)

static void runFor(uint32_t ms) {
  uint32_t end = sim::ms + ms;
  while (int32_t(sim::ms - end) < 0) { bareboard_demo_step(); cloud_step(); sim::ms += 50; }
}
static std::vector<std::string> on(const char* feed) {
  std::vector<std::string> v;
  for (auto& s : sim::saved) if (s.feed == feed) v.push_back(s.value);
  return v;
}

int main() {
  sim::reset();
  cloud_setup();
  bareboard_demo_setup();
  runFor(125000);                                   // ~2 minutes, nothing plugged in

  auto light = on(FEED_LIGHT);
  CHECK(light.size() >= 3, "light published %zu times, want >= 3 (every 30 s)", light.size());
  CHECK(light.size() >= 2 && light[light.size() - 1] == "50" && light[light.size() - 2] == "50",
        "1 s on / 1 s off should read 50, got %s", light.empty() ? "-" : light.back().c_str());
  CHECK(on(FEED_TEMPERATURE).empty() && on(FEED_HUMIDITY).empty() && on(FEED_PRESENCE).empty(),
        "no DHT20 / PIR: nothing should be published for them");
  CHECK(!on(FEED_MODE).empty() && on(FEED_MODE)[0] == "BAREBOARD_DEMO", "mode announced");
  CHECK(sim::ledToggles >= 120, "LED toggled %d times in ~2 min", sim::ledToggles);
  CHECK(cloud_stats().backlog == 0, "no backlog while online (backlog %zu)", cloud_stats().backlog);

  sim::deliver(FEED_LED, "#FF0000:abcd1234:U");     // colour from the backend / dashboard
  runFor(500);
  CHECK(sim::rgbColor == 0xFF0000, "RGB LED colour %06X, want FF0000", (unsigned)sim::rgbColor);
  CHECK(!on(FEED_ACK).empty() && on(FEED_ACK).back() == "led:abcd1234:1:FF0000:U", "ack %s",
        on(FEED_ACK).empty() ? "-" : on(FEED_ACK).back().c_str());

  sim::deliver(FEED_FAN, "70:dead0001:V");          // no fan on a bare board
  runFor(500);
  CHECK(on(FEED_ACK).back() == "fan:dead0001:0:70:V:NOHW", "fan refused: %s", on(FEED_ACK).back().c_str());

  printf("  bareboard: light %s, %zu publishes, LED toggles %d\n",
         light.empty() ? "-" : light.back().c_str(), sim::saved.size(), sim::ledToggles);
  printf("bareboard: %d checks, %d failures\n", checks, failures);
  return failures ? 1 : 0;
}
