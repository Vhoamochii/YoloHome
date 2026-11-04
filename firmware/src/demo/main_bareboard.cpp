// Example main.cpp for the bare-board test. Rename to main.cpp (or copy into yours).
#include <Arduino.h>

#include "adafruitio_task.h"
#include "bareboard_demo.h"

EventGroupHandle_t gSystemEvents = nullptr;   // your firmware may already define this

void setup() {
  Serial.begin(115200);
  gSystemEvents = xEventGroupCreate();
  cloud_init();                               // queues first, before any task uses them
  xTaskCreatePinnedToCore(task_adafruitio, "cloud", 8192, nullptr, 2, nullptr, 0);
  xTaskCreatePinnedToCore(task_bareboard_demo, "demo", 4096, nullptr, 1, nullptr, 1);
}

void loop() {
  static uint32_t last = 0;
  if (millis() - last > 5000) {               // progress report on the serial monitor
    last = millis();
    CloudStats s = cloud_stats();
    Serial.printf("cloud %s | published %lu | rate-dropped %lu | commands %lu (rejected %lu)\n",
                  (xEventGroupGetBits(gSystemEvents) & EVT_CLOUD_UP) ? "UP" : "down",
                  (unsigned long)s.published, (unsigned long)s.rateDropped,
                  (unsigned long)s.commandsIn, (unsigned long)s.commandsRejected);
  }
  vTaskDelay(pdMS_TO_TICKS(100));
}
