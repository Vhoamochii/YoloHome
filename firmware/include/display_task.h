// display_task.h — LCD 16x2, on-board status LEDs and the on-board button.
//   LCD line 1: temperature, humidity, fan        "29.8C 71% F 70"
//   LCD line 2: mode and the +15 min forecast      "AUTO t15 30.9C"
//   status RGB: green AUTO, blue LOCKDOWN, amber OFFLINE, flashing orange HOT (>= 33 C),
//               fast flashing red SAFETY
//   buttons:    SW1 = fan off -> 40 -> 70 -> 100 % (manual, starts the lockdown)
//               SW2 = back to AUTO (cancels the lockdown)
#pragma once

void task_display(void* parameter);   // stack 4096