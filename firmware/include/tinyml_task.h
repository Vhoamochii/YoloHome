#pragma once
#include <stdint.h>

struct TinyMlStatus {
  float score;
  bool alarm;
  bool ml;
  bool heat;
  bool valid;
  uint32_t lastUpdateMs;
};

// Thread-safe snapshot for display / control
bool tinyml_status(TinyMlStatus& out);

// FreeRTOS task function
void task_tinyml_fire(void* parameter);

