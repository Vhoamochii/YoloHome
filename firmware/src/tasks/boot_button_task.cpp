#include "boot_button_task.h"

#define BOOT_BUTTON_PIN 0
#define FACTORY_RESET_HOLD_MS 5000

void task_boot_button(void* parameter) {
  pinMode(BOOT_BUTTON_PIN, INPUT);
  
  uint32_t pressStartTime = 0;
  bool wasPressed = false;
  
  while (1) {
    bool isPressed = (digitalRead(BOOT_BUTTON_PIN) == LOW);
    
    if (isPressed && !wasPressed) {
      // Button just pressed
      pressStartTime = millis();
      wasPressed = true;
    }
    else if (!isPressed && wasPressed) {
      // Button just released
      uint32_t pressDuration = millis() - pressStartTime;
      
      if (pressDuration >= FACTORY_RESET_HOLD_MS) {
        // Factory reset
        Serial.println("Factory reset triggered!");
        // TODO: Clear config and restart
      }
      
      wasPressed = false;
    }
    
    vTaskDelay(pdMS_TO_TICKS(50));
  }
}
