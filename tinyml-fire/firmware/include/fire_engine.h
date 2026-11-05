#pragma once
#include <math.h>
#include <stdint.h>
#include "temperature_model.h"
#include "alarm_config.h"

// Constrained logistic regression, trained from labeled data on a PC.
namespace tinyfire {
inline bool valid(float t, float h) {
  return isfinite(t) && isfinite(h) && t >= -40 && t <= 80 && h >= 0 && h <= 100;
}
inline float infer(float t, float h) {
  if (!valid(t, h)) return NAN;
  const float z = weights::a * ((t - 35.0f) / 10.0f)
                + weights::c * ((h - 50.0f) / 50.0f) + weights::b;
  if (z >= 0) return 1.0f / (1.0f + expf(-z));
  const float e = expf(z);
  return e / (1.0f + e);
}

struct Result {
  float score = NAN;
  bool ml = false, heat = false, alarm = false, valid = false;
  const char* state = "WARMUP";
};

class Engine {
 public:
  Result update(float t, float h) {
    r_.valid = tinyfire::valid(t, h);
    r_.score = r_.valid ? infer(t, h) : NAN;
    if (!r_.valid || !isfinite(r_.score)) {
      // A failed reading must never clear an existing alert.
      high_ = low_ = 0;
      r_.state = "SENSOR_ERROR";
      return r_;
    }
    if (r_.score >= alarm_config::ml_on_score) { if (high_ < alarm_config::consecutive_samples) ++high_; low_ = 0; }
    else if (r_.score <= alarm_config::ml_off_score) { if (low_ < alarm_config::consecutive_samples) ++low_; high_ = 0; }
    else high_ = low_ = 0;
    if (high_ >= alarm_config::consecutive_samples) r_.ml = true;
    if (low_ >= alarm_config::consecutive_samples) r_.ml = false;
    // Separate deterministic high-temperature guard; never presented as ML output.
    if (t >= alarm_config::heat_on_c) r_.heat = true;
    else if (t <= alarm_config::heat_off_c) r_.heat = false;
    r_.alarm = r_.ml || r_.heat;
    r_.state = r_.alarm ? "ALERT" : "OK";
    return r_;
  }
 private:
  Result r_;
  uint8_t high_ = 0, low_ = 0;
};

}  // namespace tinyfire
