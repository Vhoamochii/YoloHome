#pragma once
#include <math.h>
#include <stdint.h>
#include "model_weights.h"

// The trained Dense(2 -> 8 -> 1) network, with float32 weights in flash.
// No training on the MCU; no network connection needed for inference.
namespace tinyfire {
inline bool valid(float t, float h) {
  return isfinite(t) && isfinite(h) && t >= -40 && t <= 80 && h >= 0 && h <= 100;
}
inline float infer(float t, float h) {
  if (!valid(t, h)) return NAN;
  const float x[2] = {(t - weights::mean[0]) / weights::scale[0],
                      (h - weights::mean[1]) / weights::scale[1]};
  float z = weights::b2;
  for (int j = 0; j < 8; ++j) {
    float a = weights::b1[j];
    for (int i = 0; i < 2; ++i) a += x[i] * weights::w1[i][j];
    z += (a > 0 ? a : 0) * weights::w2[j];
  }
  // Stable sigmoid, including extreme finite activations.
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
    if (r_.score >= 0.8f) { if (high_ < 3) ++high_; low_ = 0; }
    else if (r_.score <= 0.5f) { if (low_ < 3) ++low_; high_ = 0; }
    else high_ = low_ = 0;
    if (high_ >= 3) r_.ml = true;
    if (low_ >= 3) r_.ml = false;
    // Separate deterministic high-temperature guard; never presented as ML output.
    if (t >= 45.0f) r_.heat = true;
    else if (t <= 43.0f) r_.heat = false;
    r_.alarm = r_.ml || r_.heat;
    r_.state = r_.alarm ? "ALERT" : "OK";
    return r_;
  }
 private:
  Result r_;
  uint8_t high_ = 0, low_ = 0;
};

}  // namespace tinyfire
