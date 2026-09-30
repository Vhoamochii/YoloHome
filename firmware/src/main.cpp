#include <Arduino.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <WiFi.h>
#include <AdafruitIO_WiFi.h>
#include "config.h"
#include "tasks/sensor_task.h"
#include "tasks/tinyml_task.h"
#include "tasks/control_logic_task.h"
#include "tasks/actuator_task.h"
#include "tasks/adafruitio_task.h"

// FreeRTOS queues and mutexes
QueueHandle_t qSensorFrames;
QueueHandle_t qInferenceResults;
QueueHandle_t qUserCommands;
QueueHandle_t qActuatorCommands;

SemaphoreHandle_t xStateMutex;
SemaphoreHandle_t xConfigMutex;

EventGroupHandle_t gSystemEvents;

void setup() {
  Serial.begin(115200);
  
  // Create queues
  qSensorFrames = xQueueCreate(10, sizeof(SensorFrame));
  qInferenceResults = xQueueCreate(10, sizeof(InferenceResult));
  qUserCommands = xQueueCreate(5, sizeof(UserCommand));
  qActuatorCommands = xQueueCreate(5, sizeof(ActuatorCommand));
  
  // Create mutexes
  xStateMutex = xSemaphoreCreateMutex();
  xConfigMutex = xSemaphoreCreateMutex();
  
  // Create event group
  gSystemEvents = xEventGroupCreate();
  
  // Create FreeRTOS tasks
  xTaskCreatePinnedToCore(task_sensor, "SensorTask", 4096, NULL, 3, NULL, 1);
  xTaskCreatePinnedToCore(task_tinyml, "TinyMLTask", 8192, NULL, 2, NULL, 1);
  xTaskCreatePinnedToCore(task_control_logic, "ControlTask", 4096, NULL, 4, NULL, 1);
  xTaskCreatePinnedToCore(task_actuator, "ActuatorTask", 4096, NULL, 3, NULL, 0);
  xTaskCreatePinnedToCore(task_adafruitio, "MQTTTask", 8192, NULL, 2, NULL, 0);
}

void loop() {
  vTaskDelay(portMAX_DELAY);
}
