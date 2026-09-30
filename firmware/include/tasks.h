#ifndef TASKS_H
#define TASKS_H

#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <freertos/queue.h>
#include <freertos/semphr.h>
#include <freertos/event_groups.h>
#include "types.h"

// Global queues
extern QueueHandle_t qSensorFrames;
extern QueueHandle_t qInferenceResults;
extern QueueHandle_t qUserCommands;
extern QueueHandle_t qActuatorCommands;

// Global mutexes
extern SemaphoreHandle_t xStateMutex;
extern SemaphoreHandle_t xConfigMutex;

// Event group bits
extern EventGroupHandle_t gSystemEvents;
#define EVT_WIFI_CONNECTED    (1 << 0)
#define EVT_AI_COOLING        (1 << 1)
#define EVT_MANUAL_LOCKDOWN   (1 << 2)
#define EVT_VOICE_ACTIVE      (1 << 3)

// Task function declarations
void task_sensor(void* parameter);
void task_tinyml(void* parameter);
void task_control_logic(void* parameter);
void task_actuator(void* parameter);
void task_adafruitio(void* parameter);
void task_status_led(void* parameter);
void task_boot_button(void* parameter);

#endif
