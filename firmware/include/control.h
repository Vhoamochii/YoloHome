// control.h — YoloHome device logic. Plain C++ (no I/O): unit-tested on a PC in test/host/.
//
// Ported from the reference implementation in the Python gateway (aura_core.py):
//   arbitration   Safety -> Manual lockdown -> Schedule -> AI   (first objection wins)
//   safety        T > 45 °C: fan 100 %, LEDs red, buzzer; released below 43 °C
//   heat warning  T >= 33 °C: LEDs orange (no fan change); released below 32.5 °C
//   lockdown      a USER/VOICE fan command holds the fan for 30 min (or its hold_min);
//                 AI and SCHEDULE commands are refused meanwhile ("LOCK")
//   schedule      applied without lockdown; with hold_min it pauses the AI for that long
//   sync          restore after reconnect: applied, never starts a lockdown
//   AI policy     15-min forecast -> discomfort score -> asymmetric EMA -> hysteresis latch
//                 -> fan 40..100 % in 10 % steps, only while someone is present
//   anomaly       |actual - forecast made 15 min earlier| far outside its usual spread
//
// One deliberate difference: presence holds for 10 minutes after the last motion (UC-17 in the
// requirements) instead of the reference's 60 s, so a person sitting still is not "absent".
#pragma once
#include <stddef.h>
#include <stdint.h>

#include "adafruitio_task.h"   // cloud::Command, cloud::Device, cloud::Actor

namespace ctl {

struct Config {
  float comfortC = 30.0f;          // pre-cool when the 15-min forecast approaches this
  float safetyC = 45.0f;
  float safetyReleaseC = 43.0f;
  float warnC = 33.0f;               // heat warning: LEDs show warnColor from here ...
  float warnReleaseC = 32.5f;        // ... until below this (the gap stops flickering)
  uint32_t warnColor = 0xFF6000;     // orange
  uint16_t lockdownMin = 30;
  uint32_t presenceHoldS = 600;
  float emaRising = 0.35f, emaFalling = 0.65f;
  float hystOn = 0.68f, hystOff = 0.48f;
  uint8_t hystOffCycles = 3;
  uint32_t aiMinDwellS = 60;       // speed tweaks at most once a minute (fewer ACKs, less jitter)
  float anomalyTau = 2.5f;         // in standard deviations of the forecast residual
  uint8_t anomalyConsecutive = 3;  // minutes in a row
  uint16_t anomalyWarmup = 30;     // residuals collected before anomalies are reported
  uint8_t horizonMin = 15;
};

enum class Mode : uint8_t { AutoAi, ManualLockdown, OfflineFailsafe };
const char* modeName(Mode m);

struct Reading {
  uint32_t ms;
  float temp, humi, light;         // NaN = unavailable
  bool presence, presenceValid;
};

// 1-minute means of temperature/humidity, and a forecast from them.
// Baseline: least-squares trend over the last 10 minutes (needs >= 5).
// If include/forecast_model.h exists (exported weights of the trained network), it is used
// instead — see control.cpp for the expected format.
class Forecaster {
 public:
  static constexpr int kHistory = 60;      // minutes kept
  static constexpr int kTrendWindow = 10;
  static constexpr int kMinMinutes = 5;
  bool add(const Reading& r);              // true when this reading closed a minute
  bool ready() const { return n_ >= kMinMinutes; }
  float predictT(int minutesAhead) const;  // persistence (last value) until ready()
  float lastT() const;
  int minutes() const { return n_; }
  bool usesModel() const;
 private:
  float meanAgo(const float* buf, int ago) const;
  float slope(const float* buf) const;
  float t_[kHistory] = {}, h_[kHistory] = {}, l_[kHistory] = {};
  int head_ = 0, n_ = 0;
  uint32_t minuteStart_ = 0;
  bool started_ = false;
  double st_ = 0, sh_ = 0, sl_ = 0;
  uint16_t ct_ = 0, ch_ = 0, cl_ = 0;
  float lastHourOfDay_ = 0;
 public:
  void setHourOfDay(float h) { lastHourOfDay_ = h; }   // for the model's time features
};

// Residual between each minute's actual temperature and the forecast made 15 min earlier.
class AnomalyDetector {
 public:
  explicit AnomalyDetector(const Config& c) : c_(c) {}
  // Called once per closed minute. Returns +1 when an anomaly starts, -1 when it clears.
  int update(float actualT, float forecastNow);
  bool active() const { return active_; }
  float lastResidual() const { return lastR_; }
 private:
  const Config& c_;
  float pred_[64] = {};
  bool havePred_[64] = {};
  uint32_t minute_ = 0;
  double mean_ = 0, m2_ = 0;
  uint32_t count_ = 0;
  uint8_t streak_ = 0;
  bool active_ = false;
  float lastR_ = 0;
};

// The reference AIPolicy: forecast -> score -> EMA -> latch -> set-point.
class AiPolicy {
 public:
  explicit AiPolicy(const Config& c) : c_(c) {}
  // Returns true and sets target when the fan should change.
  bool decide(uint32_t nowMs, float t15, bool present, uint8_t currentFan, uint8_t& target);
  float score() const { return S_; }
  bool latched() const { return on_; }
 private:
  const Config& c_;
  float S_ = 0;
  bool on_ = false;
  uint8_t below_ = 0;
  bool changed_ = false;
  uint32_t lastChange_ = 0;
};

struct Event {
  char type[16];
  char data[28];
};

class Controller {
 public:
  explicit Controller(const Config& c = Config());
  Controller(const Controller&) = delete;            // members hold references to c_
  Controller& operator=(const Controller&) = delete;

  struct Result {
    bool ok;
    const char* reason;            // nullptr, "SAFE" or "LOCK"
  };
  Result command(const cloud::Command& cmd, uint32_t nowMs);
  void reading(const Reading& r);              // every new sensor reading
  void tick(uint32_t nowMs, bool cloudUp);     // timers and link state, every loop
  void cancelLockdown(uint32_t nowMs);         // button SW2: back to AUTO
  Result localFanStep(uint32_t nowMs);         // button SW1: off -> 40 -> 70 -> 100 -> off
  void setHourOfDay(float h) { fc_.setHourOfDay(h); }   // local time, for a trained model

  // Outputs (what the actuators should show now)
  uint8_t fan() const { return safety_ ? 100 : fan_; }
  uint32_t led() const { return safety_ ? 0xFF0000 : (hot_ ? c_.warnColor : led_); }
  bool relay() const { return relay_; }
  bool buzzer(uint32_t nowMs) const { return safety_ && (nowMs / 500) % 4 == 0; }

  // State
  Mode mode() const { return mode_; }
  bool safety() const { return safety_; }
  bool hot() const { return hot_; }                       // heat warning active
  bool anomaly() const { return anomaly_.active(); }
  bool lockdownActive(uint32_t nowMs) const;
  uint32_t lockRemainingMs(uint32_t nowMs) const;
  bool present(uint32_t nowMs) const;
  const Forecaster& forecaster() const { return fc_; }
  const AiPolicy& policy() const { return ai_; }
  float lastT() const { return lastT_; }
  float lastH() const { return lastH_; }

  // Change notifications for the cloud (each returns true once per change)
  bool takeModeChanged() { bool c = modeChanged_; modeChanged_ = false; return c; }
  bool takeFanChanged() { bool c = fanChanged_; fanChanged_ = false; return c; }
  bool popEvent(Event& e);

 private:
  void setFan(uint8_t pct);
  void pushEvent(const char* type, const char* data);
  void refreshMode(uint32_t nowMs);
  Config c_;
  Forecaster fc_;
  AnomalyDetector anomaly_;
  AiPolicy ai_;
  Mode mode_ = Mode::AutoAi;
  bool cloudUp_ = true, safety_ = false, hot_ = false;
  uint8_t fan_ = 0;
  uint32_t led_ = 0x000000;
  bool relay_ = false;
  bool lockActive_ = false;
  uint32_t lockUntil_ = 0;
  bool holdActive_ = false;
  uint32_t holdUntil_ = 0;
  bool motionSeen_ = false, pirSeen_ = false;
  uint32_t lastMotion_ = 0;
  uint32_t lastReadingMs_ = 0;
  float lastT_ = 0, lastH_ = 0;
  bool modeChanged_ = true, fanChanged_ = true;
  Event events_[8];
  uint8_t evHead_ = 0, evCount_ = 0;
};

}  // namespace ctl