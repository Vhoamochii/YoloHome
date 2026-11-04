// Host tests for the control logic (control.cpp): plain C++, scripted sensor readings.
#include <math.h>
#include <stdio.h>
#include <string.h>
#include <functional>
#include <string>
#include <vector>

#include "control.h"

using namespace ctl;
static int failures = 0, checks = 0;
#define CHECK(cond, ...) do { ++checks; if (!(cond)) { ++failures; \
  printf("FAIL %s:%d  ", __FILE__, __LINE__); printf(__VA_ARGS__); printf("\n"); } } while (0)

// a fresh controller + clock per scenario
struct Rig {
  Controller c;
  uint32_t ms = 1000;
  std::vector<std::string> events;
  bool cloud = true;
  // feed readings every 2 s for `seconds`, temperature given as a function of minutes elapsed
  void run(uint32_t seconds, std::function<float(float)> temp, bool pirValid = false,
           std::function<bool(float)> motion = nullptr) {
    uint32_t end = ms + seconds * 1000;
    static uint32_t t0 = ms;
    (void)t0;
    while (ms < end) {
      float minutes = ms / 60000.0f;
      Reading r{ms, temp(minutes), 60.0f, NAN, motion ? motion(minutes) : false, pirValid};
      c.reading(r);
      c.tick(ms, cloud);
      Event e;
      while (c.popEvent(e)) events.push_back(std::string(e.type) + ":" + e.data);
      ms += 2000;
    }
  }
  bool has(const char* prefix) const {
    for (auto& e : events) if (e.rfind(prefix, 0) == 0) return true;
    return false;
  }
};

static cloud::Command fanCmd(uint8_t pct, cloud::Actor a, uint16_t hold = 0) {
  cloud::Command c;
  c.device = cloud::Device::Fan;
  c.fanPct = pct;
  c.actor = a;
  c.holdMin = hold;
  return c;
}
static cloud::Command ledCmd(uint32_t rgb, cloud::Actor a = cloud::Actor::User) {
  cloud::Command c;
  c.device = cloud::Device::Led;
  c.rgb = rgb;
  c.actor = a;
  return c;
}
static auto constant(float v) { return [v](float) { return v; }; }

static void safety() {
  Rig r;
  r.c.command(ledCmd(0x00FF00), r.ms);
  r.run(10, constant(46.0f));
  CHECK(r.c.safety() && r.c.fan() == 100 && r.c.led() == 0xFF0000, "safety outputs");
  CHECK(r.has("SAFETY:46.0"), "SAFETY event");
  auto res = r.c.command(fanCmd(50, cloud::Actor::User), r.ms);
  CHECK(!res.ok && strcmp(res.reason, "SAFE") == 0, "user fan refused during safety");
  res = r.c.command(ledCmd(0x0000FF), r.ms);
  CHECK(!res.ok && strcmp(res.reason, "SAFE") == 0, "LED refused during safety");
  r.run(10, constant(44.0f));
  CHECK(r.c.safety(), "still active at 44 (releases below 43)");
  r.run(10, constant(42.9f));
  CHECK(!r.c.safety() && r.has("SAFETY_CLEAR"), "released below 43");
  CHECK(r.c.led() == 0x00FF00, "user LED colour back after the alarm: %06X", unsigned(r.c.led()));
}

static void lockdown() {
  Rig r;
  auto res = r.c.command(fanCmd(55, cloud::Actor::User), r.ms);
  r.c.tick(r.ms, true);
  CHECK(res.ok && r.c.mode() == Mode::ManualLockdown, "user command starts lockdown");
  r.run(300, constant(35.0f));                        // hot: AI would want 100 %
  CHECK(r.c.fan() == 55, "AI blocked during lockdown: fan %u", r.c.fan());
  res = r.c.command(fanCmd(20, cloud::Actor::Schedule), r.ms);
  CHECK(!res.ok && strcmp(res.reason, "LOCK") == 0, "schedule refused during lockdown");
  r.run(26 * 60, constant(35.0f));                    // 31 min after the command
  CHECK(r.c.mode() == Mode::AutoAi, "lockdown expired");
  CHECK(r.c.fan() >= 40, "AI starts cooling right after expiry: fan %u", r.c.fan());
  r.run(3 * 60, constant(35.0f));                     // speed steps wait 60 s each
  CHECK(r.c.fan() >= 90, "AI ramps up after expiry: fan %u", r.c.fan());

  Rig b;                                              // button cancels it early
  b.c.command(fanCmd(30, cloud::Actor::Voice), b.ms);
  b.c.tick(b.ms, true);
  b.c.cancelLockdown(b.ms);
  CHECK(b.c.mode() == Mode::AutoAi && !b.c.lockdownActive(b.ms), "button cancels lockdown");

  Rig s;                                              // a restore never locks
  res = s.c.command(fanCmd(40, cloud::Actor::Sync), s.ms);
  s.c.tick(s.ms, true);
  CHECK(res.ok && s.c.fan() == 40 && s.c.mode() == Mode::AutoAi, "SYNC applied without lockdown");
}

static void scheduleHold() {
  Rig r;
  auto res = r.c.command(fanCmd(20, cloud::Actor::Schedule, 20), r.ms);
  CHECK(res.ok && r.c.mode() == Mode::AutoAi, "schedule accepted, no lockdown");
  r.run(10 * 60, constant(35.0f));
  CHECK(r.c.fan() == 20, "AI paused by the schedule's hold: fan %u", r.c.fan());
  r.run(15 * 60, constant(35.0f));
  CHECK(r.c.fan() >= 90, "AI resumes after the hold: fan %u", r.c.fan());
}

static void predictiveCooling() {
  Rig r;
  float tempAtStart = NAN;
  // 27.0 degC rising 0.1 degC per minute
  auto ramp = [](float min) { return 27.0f + 0.1f * min; };
  while (r.ms < 60u * 60000) {
    r.run(2, ramp);
    if (r.c.fan() > 0) { tempAtStart = r.c.lastT(); break; }
  }
  CHECK(!isnan(tempAtStart), "fan never started");
  CHECK(tempAtStart < 30.0f, "fan started BEFORE comfort (30): at %.2f degC", double(tempAtStart));
  CHECK(r.has("AI:"), "AI event logged");
  printf("  predictive: fan started at %.2f degC, %.1f degC before the comfort threshold\n",
         double(tempAtStart), double(30.0f - tempAtStart));

  Rig p;                                              // same ramp, PIR present but no motion
  p.run(40 * 60, ramp, true, [](float) { return false; });
  CHECK(p.c.fan() == 0, "nobody present: no pre-cooling (eco), fan %u", p.c.fan());
  p.run(60, ramp, true, [](float) { return true; });
  CHECK(p.c.fan() > 0, "motion: cooling starts, fan %u", p.c.fan());
}

static void offline() {
  Rig r;
  r.cloud = false;
  r.run(20 * 60, constant(35.0f));
  CHECK(r.c.mode() == Mode::OfflineFailsafe, "offline mode");
  CHECK(r.c.fan() >= 90, "AI keeps cooling offline: fan %u", r.c.fan());
  r.cloud = true;
  r.run(4, constant(35.0f));
  CHECK(r.c.mode() == Mode::AutoAi, "back to AUTO_AI when the cloud returns");
}

static void noFlapping() {
  Rig r;
  int changes = 0;
  uint8_t last = r.c.fan();
  unsigned seed = 12345;
  auto noisy = [&seed](float) {
    seed = seed * 1103515245u + 12345u;
    return 29.4f + ((seed >> 16) % 100) / 1000.0f - 0.05f;   // 29.35..29.45
  };
  for (int i = 0; i < 60 * 30; ++i) {                // 60 minutes
    r.run(2, noisy);
    if (r.c.fan() != last) { ++changes; last = r.c.fan(); }
  }
  CHECK(changes <= 4, "fan changed %d times in an hour of near-threshold noise", changes);
}

static void anomaly() {
  Rig r;
  unsigned seed = 7;
  auto steady = [&seed](float) {
    seed = seed * 1103515245u + 12345u;
    return 28.0f + ((seed >> 16) % 100) / 500.0f - 0.1f;      // 27.9..28.1
  };
  r.run(70 * 60, steady);
  CHECK(!r.has("ANOM"), "no anomaly in a steady room");
  r.run(6 * 60, constant(33.0f));                    // window opened to a hot balcony
  CHECK(r.has("ANOM:"), "sudden +5 degC jump reported as an anomaly");
}

static void forecaster() {
  Forecaster f;
  for (uint32_t ms = 0; ms <= 20 * 60000; ms += 2000) f.add({ms, 25.0f + 0.2f * ms / 60000.0f, 60, NAN, false, false});
  float pred = f.predictT(15), last = f.lastT();
  CHECK(f.ready() && fabsf(pred - (last + 3.0f)) < 0.05f, "linear trend: last %.2f, +15 min %.2f", double(last), double(pred));
}

int main() {
  safety();
  lockdown();
  scheduleHold();
  predictiveCooling();
  offline();
  noFlapping();
  anomaly();
  forecaster();
  printf("control: %d checks, %d failures\n", checks, failures);
  return failures ? 1 : 0;
}
