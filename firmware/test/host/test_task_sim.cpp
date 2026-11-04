// Runs the real src/tasks/adafruitio_task.cpp against stubs (stubs/) with a fake clock.
// Each scenario runs in a fresh process (see run_tests.sh) because the task keeps static state.
#include <math.h>
#include <stdio.h>
#include <string.h>

#include <algorithm>
#include <string>
#include <vector>

#include "adafruitio_task.h"
#include "config.h"
#include "sim.h"

EventGroupHandle_t gSystemEvents = new SimEvents();
static int failures = 0, checks = 0;
#define CHECK(cond, ...)                                                   \
  do {                                                                     \
    ++checks;                                                              \
    if (!(cond)) { ++failures; printf("FAIL %s:%d  ", __FILE__, __LINE__); \
                   printf(__VA_ARGS__); printf("\n"); }                    \
  } while (0)

using cloud::Sample;
static uint32_t nextSample = 0;
static float roomTemp = 30.0f;

// Advance simulated time, posting a sensor sample every 2 s like the sensor task does.
static void runFor(uint32_t ms) {
  uint32_t end = sim::ms + ms;
  while (int32_t(sim::ms - end) < 0) {
    if (int32_t(sim::ms - nextSample) >= 0) {
      cloud_post_sample(Sample{roomTemp, 70.0f, 40.0f, false});
      nextSample += 2000;
    }
    cloud_step();
    sim::ms += CLOUD_LOOP_MS;
  }
}

static std::vector<sim::Saved> on(const char* feed, uint32_t from = 0, uint32_t to = UINT32_MAX) {
  std::vector<sim::Saved> v;
  for (auto& s : sim::saved) if (s.feed == feed && s.ms >= from && s.ms < to) v.push_back(s);
  return v;
}

static bool popCommand(CloudCommandMsg& m) { return xQueueReceive(qCloudCommands, &m, 0) == pdTRUE; }
static bool cloudUp() { return gSystemEvents->bits & EVT_CLOUD_UP; }

static void steadyTelemetry() {
  runFor(600000);                                       // 10 minutes online
  auto temps = on(FEED_TEMPERATURE, 60000), hums = on(FEED_HUMIDITY, 60000);
  CHECK(temps.size() == 54 && hums.size() == 54, "temp %zu humi %zu, want 54 each (every 10 s)",
        temps.size(), hums.size());
  CHECK(on(FEED_LIGHT, 60000).size() == 18 && on(FEED_PRESENCE, 60000).size() == 18,
        "light %zu presence %zu, want 18 (every 30 s)", on(FEED_LIGHT, 60000).size(),
        on(FEED_PRESENCE, 60000).size());
  CHECK(!temps.empty() && temps.back().value == "30.00", "mean value %s", temps.back().value.c_str());
  // never more than burst + rate in any 60 s window
  size_t worst = 0;
  for (auto& a : sim::saved) {
    size_t n = std::count_if(sim::saved.begin(), sim::saved.end(),
                             [&](const sim::Saved& b) { return b.ms >= a.ms && b.ms < a.ms + 60000; });
    worst = std::max(worst, n);
  }
  CHECK(worst <= 25, "worst 60 s window %zu > 25", worst);
  CHECK(cloud_stats().rateDropped == 0, "telemetry was rate-dropped %u times", cloud_stats().rateDropped);
  CHECK(cloud_stats().backlog == 0, "no backlog while online");
  CHECK(cloudUp(), "EVT_CLOUD_UP set");
  printf("  steady: %zu publishes in 10 min, worst 60 s window %zu\n", sim::saved.size(), worst);
}

static void commandsAndAcks() {
  runFor(5000);                                         // past the sync window
  sim::deliver(FEED_FAN, "70:a1b2c3d4:S");
  runFor(200);
  CloudCommandMsg m;
  CHECK(popCommand(m), "command reached control logic");
  CHECK(m.cmd.fanPct == 70 && m.cmd.actor == cloud::Actor::Schedule &&
        strcmp(m.cmd.id, "a1b2c3d4") == 0, "parsed %u %c %s", m.cmd.fanPct,
        cloud::actorCode(m.cmd.actor), m.cmd.id);
  cloud_post_ack(m.cmd.device, m.cmd.id, true, "70", m.cmd.actor);    // what control logic does
  cloud_post_fan_state(70);
  runFor(200);
  CHECK(!on(FEED_ACK).empty() && on(FEED_ACK).back().value == "fan:a1b2c3d4:1:70:S", "ack %s",
        on(FEED_ACK).empty() ? "(none)" : on(FEED_ACK).back().value.c_str());
  CHECK(!on(FEED_FAN_STATE).empty() && on(FEED_FAN_STATE).back().value == "70", "fan state");

  sim::deliver(FEED_FAN, "70:a1b2c3d4:S");              // QoS 1 redelivery
  runFor(200);
  CHECK(!popCommand(m), "duplicate executed");
  CHECK(cloud_stats().duplicates == 1, "duplicates %u", cloud_stats().duplicates);

  sim::deliver(FEED_FAN, "banana:dead0001:V");          // invalid: rejected with an ACK
  runFor(200);
  CHECK(!popCommand(m), "invalid command forwarded");
  CHECK(on(FEED_ACK).back().value == "fan:dead0001:0:?:V:BAD", "reject ack %s",
        on(FEED_ACK).back().value.c_str());

  sim::deliver(FEED_LED, "#00FF00");                    // Adafruit dashboard colour picker
  runFor(200);
  CHECK(popCommand(m) && m.cmd.device == cloud::Device::Led && m.cmd.rgb == 0x00FF00 &&
        m.cmd.actor == cloud::Actor::User && m.cmd.id[0] == 0, "dashboard led");
}

static void restoreOnReconnectIsSync() {
  runFor(5000);
  sim::lastValue[FEED_FAN] = "55";                      // last commanded value on Adafruit
  sim::broker = false;
  runFor(5000);
  CHECK(!cloudUp(), "EVT_CLOUD_UP cleared when offline");
  sim::broker = true;
  runFor(500);
  CloudCommandMsg m;
  CHECK(popCommand(m), "restore delivered after reconnect");
  CHECK(m.cmd.fanPct == 55 && m.cmd.actor == cloud::Actor::Sync,
        "restore is SYNC (no lockdown): actor %c", cloud::actorCode(m.cmd.actor));
  runFor(4000);                                         // after the window: a real user command
  sim::deliver(FEED_FAN, "60");
  runFor(200);
  CHECK(popCommand(m) && m.cmd.actor == cloud::Actor::User, "later command is USER");
  CHECK(cloud_stats().reconnects == 1, "reconnects %u", cloud_stats().reconnects);
}

static void outageBacklogAndReplay() {
  runFor(120000);                                       // 2 min online
  sim::broker = false;                                  // WiFi up, Adafruit IO unreachable
  roomTemp = 33.0f;
  cloud_post_event("SAFETY", "46.2");                   // happens during the outage
  cloud_post_mode("OFFLINE_FAILSAFE");
  runFor(30 * 60000);                                   // 30 min outage
  CHECK(cloud_stats().backlog >= 29 && cloud_stats().backlog <= 31, "backlog %zu, want ~30",
        cloud_stats().backlog);
  CHECK(on(FEED_TEMPERATURE, 120000 + 1000, 120000 + 30 * 60000).empty(), "nothing published offline");
  cloud_post_mode("AUTO_AI");                           // latest mode wins
  sim::broker = true;
  uint32_t back = sim::ms;
  runFor(15 * 60000);
  auto ev = on(FEED_EVENT, back);
  size_t replayed = std::count_if(ev.begin(), ev.end(), [](const sim::Saved& s) {
    return s.value.rfind("B:", 0) == 0; });
  CHECK(cloud_stats().backlog == 0, "backlog drained, %zu left", cloud_stats().backlog);
  CHECK(replayed >= 29, "replayed %zu", replayed);
  bool safetyKept = std::any_of(ev.begin(), ev.end(), [](const sim::Saved& s) {
    return s.value == "SAFETY:46.2"; });
  CHECK(safetyKept, "alert raised offline was delivered after reconnect");
  auto modes = on(FEED_MODE, back);
  CHECK(modes.size() == 1 && modes[0].value == "AUTO_AI", "mode after reconnect: %zu, %s",
        modes.size(), modes.empty() ? "-" : modes[0].value.c_str());
  CHECK(ev.size() && (ev[0].value == "SAFETY:46.2"), "alert sent before backlog, first=%s",
        ev.empty() ? "-" : ev[0].value.c_str());
  auto temps = on(FEED_TEMPERATURE, back + 60000);
  CHECK(temps.size() >= 6 * 13, "live telemetry kept flowing during replay: %zu", temps.size());
  bool outageValue = std::any_of(ev.begin(), ev.end(), [](const sim::Saved& s) {
    return s.value.rfind("B:", 0) == 0 && s.value.find(":33.00:70.0:40:0") != std::string::npos; });
  CHECK(outageValue, "backlog carries the readings taken during the outage");
  printf("  outage: 30 min -> %zu backlog entries replayed in <= 15 min\n", replayed);
}

static void wifiDownIsNonBlocking() {
  runFor(10000);
  sim::wifi = false;
  uint32_t before = sim::ms;
  for (int i = 0; i < 100; ++i) cloud_step();           // must return immediately
  CHECK(sim::ms == before, "cloud_step blocked for %u ms with WiFi down", sim::ms - before);
  runFor(60000);
  CHECK(sim::reconnectCalls >= 1, "WiFi reconnect nudged (%d)", sim::reconnectCalls);
  CHECK(!cloudUp(), "offline");
  sim::wifi = true;
  runFor(1000);
  CHECK(cloudUp(), "back online");
  CHECK(sim::runCalls == 0, "AdafruitIO::run() was called");
}

int main(int argc, char** argv) {
  sim::reset();
  cloud_setup();
  std::string which = argc > 1 ? argv[1] : "";
  if (which == "steady") steadyTelemetry();
  else if (which == "commands") commandsAndAcks();
  else if (which == "restore") restoreOnReconnectIsSync();
  else if (which == "outage") outageBacklogAndReplay();
  else if (which == "wifi") wifiDownIsNonBlocking();
  else { printf("usage: %s steady|commands|restore|outage|wifi\n", argv[0]); return 2; }
  printf("task[%s]: %d checks, %d failures\n", which.c_str(), checks, failures);
  return failures ? 1 : 0;
}
