#pragma once
#include <Arduino.h>
#include <stdio.h>
#include "fire_engine.h"

namespace tinyfire {
// One atomic serial frame. null instead of NaN keeps the JSON valid.
inline void emit(const Result& r, float t, float h, uint32_t now, uint32_t seq,
                 uint32_t inferenceUs, bool simulated) {
  char ts[24] = "null", hs[24] = "null", ps[24] = "null";
  if (r.valid) {
    snprintf(ts, sizeof ts, "%.3f", double(t));
    snprintf(hs, sizeof hs, "%.3f", double(h));
    snprintf(ps, sizeof ps, "%.8g", double(r.score));
  }
  Serial.printf("{\"type\":\"tinyml_fire\",\"v\":1,\"seq\":%lu,\"uptime_ms\":%lu,"
                "\"temperature\":%s,\"humidity\":%s,\"score\":%s,"
                "\"valid\":%s,\"ml_alarm\":%s,\"heat_alarm\":%s,\"alarm\":%s,"
                "\"state\":\"%s\",\"model\":\"%s\",\"inference_us\":%lu,\"simulated\":%s}\n",
                (unsigned long)seq, (unsigned long)now, ts, hs, ps,
                r.valid ? "true" : "false", r.ml ? "true" : "false",
                r.heat ? "true" : "false", r.alarm ? "true" : "false", r.state,
                weights::id, (unsigned long)inferenceUs, simulated ? "true" : "false");
}
}  // namespace tinyfire

