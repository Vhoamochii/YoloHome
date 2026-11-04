// control_task.h — runs the Controller (control.h): commands in, actuators and cloud out.
#pragma once
#include <stdint.h>

#include "control.h"

struct ControlStatus {
  ctl::Mode mode;
  bool safety, hot, anomaly, cloudUp, forecastReady, usesModel;
  uint8_t fan;
  uint32_t led;
  uint32_t lockRemainingMs;
  float temp, humi, t15;              // t15 = forecast for +15 min (NaN until available)
};

bool control_status(ControlStatus& out);       // snapshot for the display / serial log
void control_request_cancel_lockdown();        // button SW2, any task
void control_request_fan_step();               // button SW1, any task
void task_control(void* parameter);            // stack 6144