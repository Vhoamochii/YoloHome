#pragma once
// Change these here, then rebuild/upload. Score is NOT a calibrated fire probability.
namespace tinyfire { namespace alarm_config {
constexpr float ml_on_score = 0.63f;
constexpr float ml_off_score = 0.615f;
constexpr unsigned consecutive_samples = 3;
// Separate deterministic heat guard, independent of the learned score.
constexpr float heat_on_c = 45.0f;
constexpr float heat_off_c = 43.0f;
static_assert(ml_off_score >= 0 && ml_off_score < ml_on_score && ml_on_score <= 1,
              "Require 0 <= off < on <= 1");
static_assert(consecutive_samples >= 1 && consecutive_samples <= 255, "Require 1..255 samples");
static_assert(heat_off_c < heat_on_c, "Heat release must be below heat alarm");
}}
