#include "status_led_task.h"

#define STATUS_LED_PIN 18
#define RGB_LED_PIN 48

void task_status_led(void* parameter) {
  pinMode(STATUS_LED_PIN, OUTPUT);
  
  while (1) {
    EventBits_t bits = xEventGroupGetBits(gSystemEvents);
    
    if (bits & EVT_WIFI_CONNECTED) {
      // Solid on when connected
      digitalWrite(STATUS_LED_PIN, HIGH);
    } else {
      // Blink when disconnected
      digitalWrite(STATUS_LED_PIN, !digitalRead(STATUS_LED_PIN));
    }
    
    vTaskDelay(pdMS_TO_TICKS(500));
  }
}
