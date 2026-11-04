#pragma once
#include "FreeRTOS.h"
typedef uint32_t EventBits_t;
struct SimEvents { EventBits_t bits = 0; };
typedef SimEvents* EventGroupHandle_t;
inline EventBits_t xEventGroupSetBits(EventGroupHandle_t g, const EventBits_t b) { return g->bits |= b; }
inline EventBits_t xEventGroupClearBits(EventGroupHandle_t g, const EventBits_t b) { EventBits_t o = g->bits; g->bits &= ~b; return o; }
