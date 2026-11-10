// control.cpp — see control.h.
#include "control.h"

#include <math.h>
#include <stdio.h>
#include <string.h>

// ---- Optional trained model ---------------------------------------------------------------
// Put the exported weights of the trained network in include/forecast_model.h and it is used
// automatically. Expected contents (all const float, outputs in degC / %RH):
//   #define FM_IN 7, FM_H1, FM_H2, FM_OUT 4
//   fm_mean[FM_IN], fm_std[FM_IN]                  input normalisation from training
//   fm_w1[FM_H1][FM_IN], fm_b1[FM_H1]              Dense + ReLU
//   fm_w2[FM_H2][FM_H1], fm_b2[FM_H2]              Dense + ReLU
//   fm_w3[FM_OUT][FM_H2], fm_b3[FM_OUT]            Dense, linear: {T+15, RH+15, T+30, RH+30}
// Inputs, in this order, from 1-minute means: T, RH, light (or fm_mean when absent),
// T - T(10 min earlier), RH - RH(10 min earlier), sin(2*pi*h/24), cos(2*pi*h/24).
// The training script must build its features exactly this way.
#if __has_include("forecast_model.h")
#include "forecast_model.h"
#define YH_HAVE_MODEL 1
#endif

namespace ctl {
namespace {
float clampf(float v, float lo, float hi) { return v < lo ? lo : (v > hi ? hi : v); }
}  // namespace

const char* modeName(Mode m) {
  switch (m) {
    case Mode::AutoAi: return "AUTO_AI";
    case Mode::ManualLockdown: return "MANUAL_LOCKDOWN";
    case Mode::OfflineFailsafe: return "OFFLINE_FAILSAFE";
  }
  return "AUTO_AI";
}

// ---- Forecaster ---------------------------------------------------------------------------
bool Forecaster::add(const Reading& r) {
  if (!started_) {
    started_ = true;
    minuteStart_ = r.ms;
  }
  bool closed = false;
  if (r.ms - minuteStart_ >= 60000) {
    if (ct_ && ch_) {
      t_[head_] = float(st_ / ct_);
      h_[head_] = float(sh_ / ch_);
      l_[head_] = cl_ ? float(sl_ / cl_) : NAN;
      head_ = (head_ + 1) % kHistory;
      if (n_ < kHistory) ++n_;
      closed = true;
    }
    st_ = sh_ = sl_ = 0;
    ct_ = ch_ = cl_ = 0;
    minuteStart_ += 60000;
    if (r.ms - minuteStart_ >= 60000) minuteStart_ = r.ms;   // after a gap, restart cleanly
  }
  if (!isnan(r.temp)) { st_ += r.temp; ++ct_; }
  if (!isnan(r.humi)) { sh_ += r.humi; ++ch_; }
  if (!isnan(r.light)) { sl_ += r.light; ++cl_; }
  return closed;
}

float Forecaster::meanAgo(const float* buf, int ago) const {
  if (ago >= n_) ago = n_ - 1;
  return buf[(head_ - 1 - ago + 2 * kHistory) % kHistory];
}

float Forecaster::slope(const float* buf) const {        // per minute, least squares
  int k = n_ < kTrendWindow ? n_ : kTrendWindow;
  if (k < 2) return 0;
  double sx = 0, sy = 0, sxx = 0, sxy = 0;
  for (int i = 0; i < k; ++i) {                          // x = 0 oldest .. k-1 newest
    double y = meanAgo(buf, k - 1 - i);
    sx += i; sy += y; sxx += double(i) * i; sxy += i * y;
  }
  double d = k * sxx - sx * sx;
  return d == 0 ? 0 : float((k * sxy - sx * sy) / d);
}

float Forecaster::lastT() const { return n_ ? meanAgo(t_, 0) : NAN; }

bool Forecaster::usesModel() const {
#ifdef YH_HAVE_MODEL
  return true;
#else
  return false;
#endif
}

float Forecaster::predictT(int minutesAhead) const {
  if (!n_) return NAN;
  if (!ready()) return lastT();                          // persistence until enough history
#ifdef YH_HAVE_MODEL
  float x[FM_IN];
  float lnow = meanAgo(l_, 0);
  x[0] = meanAgo(t_, 0);
  x[1] = meanAgo(h_, 0);
  x[2] = isnan(lnow) ? fm_mean[2] : lnow;
  x[3] = meanAgo(t_, 0) - meanAgo(t_, 10);
  x[4] = meanAgo(h_, 0) - meanAgo(h_, 10);
  x[5] = sinf(2 * float(M_PI) * lastHourOfDay_ / 24);
  x[6] = cosf(2 * float(M_PI) * lastHourOfDay_ / 24);
  for (int i = 0; i < FM_IN; ++i) x[i] = (x[i] - fm_mean[i]) / fm_std[i];
  float a[FM_H1], b[FM_H2], y[FM_OUT];
  for (int j = 0; j < FM_H1; ++j) {
    float s = fm_b1[j];
    for (int i = 0; i < FM_IN; ++i) s += fm_w1[j][i] * x[i];
    a[j] = s > 0 ? s : 0;
  }
  for (int j = 0; j < FM_H2; ++j) {
    float s = fm_b2[j];
    for (int i = 0; i < FM_H1; ++i) s += fm_w2[j][i] * a[i];
    b[j] = s > 0 ? s : 0;
  }
  for (int j = 0; j < FM_OUT; ++j) {
    float s = fm_b3[j];
    for (int i = 0; i < FM_H2; ++i) s += fm_w3[j][i] * b[i];
    y[j] = s;
  }
  return minutesAhead >= 30 ? y[2] : y[0];
#else
  return lastT() + slope(t_) * float(minutesAhead);
#endif
}

// ---- Anomaly detector -----------------------------------------------------------------------
int AnomalyDetector::update(float actualT, float forecastNow) {
  int result = 0;
  uint32_t slot = minute_ % 64;
  if (havePred_[slot] && !isnan(actualT)) {
    float r = actualT - pred_[slot];
    lastR_ = r;
    bool learn = true;
    if (count_ >= c_.anomalyWarmup) {
      float sd = count_ > 1 ? float(sqrt(m2_ / (count_ - 1))) : 0;
      if (sd < 0.2f) sd = 0.2f;                           // floor: a perfectly steady room
      float z = fabsf(r - float(mean_)) / sd;
      streak_ = z > c_.anomalyTau ? uint8_t(streak_ < 255 ? streak_ + 1 : 255) : 0;
      bool now = streak_ >= c_.anomalyConsecutive;
      if (now && !active_) { active_ = true; result = +1; }
      else if (!now && active_) { active_ = false; result = -1; }
      learn = streak_ == 0;                               // don't learn from outliers
    }
    if (learn) {                                          // Welford running mean/variance
      ++count_;
      double d = r - mean_;
      mean_ += d / count_;
      m2_ += d * (r - mean_);
    }
  }
  havePred_[slot] = false;
  uint32_t future = (minute_ + c_.horizonMin) % 64;
  pred_[future] = forecastNow;
  havePred_[future] = !isnan(forecastNow);
  ++minute_;
  return result;
}

// ---- AI policy (reference AIPolicy.decide) --------------------------------------------------
bool AiPolicy::decide(uint32_t nowMs, float t15, bool present, uint8_t currentFan, uint8_t& target) {
  float y = clampf((t15 - (c_.comfortC - 1.0f)) / 2.0f, 0, 1);   // 0 at comfort-1, 1 at +1
  float w = y >= S_ ? c_.emaRising : c_.emaFalling;
  S_ = (1 - w) * S_ + w * y;
  if (!on_ && S_ >= c_.hystOn) {
    on_ = true;
    below_ = 0;
  } else if (on_) {
    below_ = S_ <= c_.hystOff ? uint8_t(below_ + 1) : 0;
    if (below_ >= c_.hystOffCycles) on_ = false;
  }
  uint8_t t = 0;
  if (on_ && present) {
    float span = (S_ - c_.hystOff) / (1 - c_.hystOff);
    t = uint8_t(nearbyintf(clampf(40 + 60 * span, 40, 100) / 10) * 10);   // 10 % steps
  }
  if (t == currentFan) return false;
  bool switching = (t == 0) != (currentFan == 0);
  if (!switching && changed_ && nowMs - lastChange_ < c_.aiMinDwellS * 1000UL) return false;
  changed_ = true;
  lastChange_ = nowMs;
  target = t;
  return true;
}

// ---- Controller -------------------------------------------------------------------------------
Controller::Controller(const Config& c) : c_(c), anomaly_(c_), ai_(c_) {}

bool Controller::lockdownActive(uint32_t nowMs) const {
  return lockActive_ && int32_t(lockUntil_ - nowMs) > 0;
}

uint32_t Controller::lockRemainingMs(uint32_t nowMs) const {
  return lockdownActive(nowMs) ? lockUntil_ - nowMs : 0;
}

bool Controller::present(uint32_t nowMs) const {
  if (!pirSeen_) return true;                  // no motion sensor: assume someone is there
  return motionSeen_ && nowMs - lastMotion_ <= c_.presenceHoldS * 1000UL;
}

void Controller::setFan(uint8_t pct) {
  if (pct == fan_) return;
  fan_ = pct;
  fanChanged_ = true;
}

void Controller::pushEvent(const char* type, const char* data) {
  Event& e = events_[(evHead_ + evCount_) % 8];
  if (evCount_ == 8) evHead_ = uint8_t((evHead_ + 1) % 8);   // full: drop the oldest
  else ++evCount_;
  snprintf(e.type, sizeof e.type, "%s", type);
  snprintf(e.data, sizeof e.data, "%s", data ? data : "");
}

bool Controller::popEvent(Event& e) {
  if (!evCount_) return false;
  e = events_[evHead_];
  evHead_ = uint8_t((evHead_ + 1) % 8);
  --evCount_;
  return true;
}

void Controller::refreshMode(uint32_t nowMs) {
  Mode m = !cloudUp_ ? Mode::OfflineFailsafe
                     : (lockdownActive(nowMs) ? Mode::ManualLockdown : Mode::AutoAi);
  if (m != mode_) {
    mode_ = m;
    modeChanged_ = true;
  }
}

Controller::Result Controller::command(const cloud::Command& cmd, uint32_t nowMs) {
  using cloud::Actor;
  bool system = cmd.actor == Actor::System;
  switch (cmd.device) {
    case cloud::Device::Fan: {
      uint8_t v = cmd.fanPct;
      if (v == 255) {
        cancelLockdown(nowMs);
        return {true, nullptr};
      }
      if (safety_ && !system && v < 100) return {false, "SAFE"};
      if (cmd.actor == Actor::Schedule) {
        setFan(v);
        lockActive_ = false;                                 // schedule overrides manual lockdown
        if (cmd.holdMin) {                                   // pause the AI for hold_min
          holdActive_ = true;
          holdUntil_ = nowMs + uint32_t(cmd.holdMin) * 60000UL;
        }
        modeChanged_ = true;
        refreshMode(nowMs);
        return {true, nullptr};
      }
      if (cmd.actor == Actor::Ai) {
        if (lockdownActive(nowMs)) return {false, "LOCK"};
        if (holdActive_ && int32_t(holdUntil_ - nowMs) > 0)
          return {false, "HOLD"};
        setFan(v);
        return {true, nullptr};
      }
      setFan(v);
      if (cmd.actor == Actor::User || cmd.actor == Actor::Voice) {   // manual: lockdown
        uint32_t minutes = cmd.holdMin ? cmd.holdMin : c_.lockdownMin;
        lockActive_ = true;
        lockUntil_ = nowMs + minutes * 60000UL;
        modeChanged_ = true;                                   // new or extended "until"
        refreshMode(nowMs);
      }
      return {true, nullptr};                                  // SYNC / SYSTEM: no lockdown
    }
    case cloud::Device::Led:
      if (safety_ && !system) return {false, "SAFE"};         // LEDs reserved for the alarm
      led_ = cmd.rgb;                                          // shown once a heat warning ends
      return {true, nullptr};
    case cloud::Device::Relay:
      relay_ = cmd.relayOn;
      return {true, nullptr};
  }
  return {false, "BAD"};
}

Controller::Result Controller::localFanStep(uint32_t nowMs) {
  uint8_t cur = fan();                                   // what the fan is actually doing
  uint8_t next = cur < 40 ? 40 : cur < 70 ? 70 : cur < 100 ? 100 : 0;
  cloud::Command c;
  c.device = cloud::Device::Fan;
  c.fanPct = next;
  c.actor = cloud::Actor::User;                          // a person at the device: lockdown
  return command(c, nowMs);
}

void Controller::cancelLockdown(uint32_t nowMs) {
  if (!lockActive_) return;
  lockActive_ = false;
  modeChanged_ = true;
  refreshMode(nowMs);
}

void Controller::tick(uint32_t nowMs, bool cloudUp) {
  if (lockActive_ && int32_t(nowMs - lockUntil_) >= 0) {
    lockActive_ = false;
    modeChanged_ = true;
  }
  if (holdActive_ && int32_t(nowMs - holdUntil_) >= 0) holdActive_ = false;
  cloudUp_ = cloudUp;
  refreshMode(nowMs);
}

void Controller::reading(const Reading& r) {
  if (!isnan(r.temp)) lastT_ = r.temp;
  if (!isnan(r.humi)) lastH_ = r.humi;
  if (r.presenceValid) {
    pirSeen_ = true;
    if (r.presence) {
      motionSeen_ = true;
      lastMotion_ = r.ms;
    }
  }
  char buf[28];
  if (!isnan(r.temp)) {                                       // safety first
    if (!safety_ && r.temp > c_.safetyC) {
      safety_ = true;
      modeChanged_ = fanChanged_ = true;
      snprintf(buf, sizeof buf, "%.1f", double(r.temp));
      pushEvent("SAFETY", buf);
    } else if (safety_ && r.temp < c_.safetyReleaseC) {
      safety_ = false;
      modeChanged_ = fanChanged_ = true;
      snprintf(buf, sizeof buf, "%.1f", double(r.temp));
      pushEvent("SAFETY_CLEAR", buf);
    }
    if (!hot_ && r.temp >= c_.warnC) {                        // heat warning (LEDs only)
      hot_ = true;
      snprintf(buf, sizeof buf, "%.1f", double(r.temp));
      pushEvent("HOT", buf);
    } else if (hot_ && r.temp < c_.warnReleaseC) {
      hot_ = false;
      snprintf(buf, sizeof buf, "%.1f", double(r.temp));
      pushEvent("HOT_CLEAR", buf);
    }
  }
  if (fc_.add(r)) {                                           // a minute closed
    int a = anomaly_.update(fc_.lastT(), fc_.predictT(c_.horizonMin));
    if (a > 0) {
      snprintf(buf, sizeof buf, "%+.1f", double(anomaly_.lastResidual()));
      pushEvent("ANOM", buf);
    } else if (a < 0) {
      pushEvent("ANOM_CLEAR", "");
    }
  }
  if (isnan(r.temp)) return;
  if (lockdownActive(r.ms)) return;                           // AI blocked by lockdown
  if (holdActive_ && int32_t(holdUntil_ - r.ms) > 0) return;  // ... or by a schedule hold
  float t15 = fc_.ready() ? fc_.predictT(c_.horizonMin) : r.temp;
  uint8_t target;
  if (ai_.decide(r.ms, t15, present(r.ms), fan_, target)) {
    setFan(target);
    snprintf(buf, sizeof buf, "%u:%.1f", unsigned(target), double(t15));
    pushEvent("AI", buf);
  }
}

}  // namespace ctl