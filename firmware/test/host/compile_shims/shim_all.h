// Force-included by check_compile.sh: the Arduino/ESP32 APIs the firmware uses, as declarations
// only, so every source file can be compiled on a PC. Signatures mirror Arduino-ESP32.
#pragma once
#include <cstddef>
#include <cstdint>
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/event_groups.h"
#define INPUT 0x01
#define INPUT_PULLUP 0x05
inline int digitalRead(uint8_t) { return 1; }
inline int analogRead(uint8_t) { return 0; }
inline void analogReadResolution(uint8_t) {}
inline TickType_t xTaskGetTickCount() { return 0; }
inline void vTaskDelayUntil(TickType_t*, TickType_t) {}
typedef void (*TaskFunction_t)(void*);
typedef void* TaskHandle_t;
inline BaseType_t xTaskCreatePinnedToCore(TaskFunction_t, const char*, uint32_t, void*, UBaseType_t, TaskHandle_t*, BaseType_t) { return pdTRUE; }
inline EventGroupHandle_t xEventGroupCreate() { return new SimEvents(); }
inline EventBits_t xEventGroupGetBits(EventGroupHandle_t g) { return g->bits; }
#include "esp_arduino_version.h"
#if ESP_ARDUINO_VERSION_MAJOR >= 3
inline bool ledcAttach(uint8_t, uint32_t, uint8_t) { return true; }
inline bool ledcWrite(uint8_t, uint32_t) { return true; }
inline uint32_t ledcWriteTone(uint8_t, uint32_t) { return 0; }
#else
inline uint32_t ledcSetup(uint8_t, uint32_t, uint8_t) { return 0; }
inline void ledcAttachPin(uint8_t, uint8_t) {}
inline void ledcWrite(uint8_t, uint32_t) {}
inline double ledcWriteTone(uint8_t, double) { return 0; }
#endif
