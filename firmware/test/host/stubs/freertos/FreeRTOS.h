#pragma once
#include <stdint.h>
#include "../sim.h"
typedef uint32_t TickType_t;
typedef int BaseType_t;
typedef unsigned UBaseType_t;
#define pdTRUE 1
#define pdFALSE 0
#define pdMS_TO_TICKS(x) ((TickType_t)(x))
inline void vTaskDelay(TickType_t t) { sim::ms += t; }
