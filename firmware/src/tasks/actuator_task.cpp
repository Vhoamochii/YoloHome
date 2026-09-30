#include "actuator_task.h"
#include <Adafruit_NeoPixel.h>

#define LED_PIN 9
#define LED_COUNT 4
#define FAN_PIN 7

Adafruit_NeoPixel strip(LED_COUNT, LED_PIN, NEO_GRB + NEO_KHZ800);

void task_actuator(void* parameter) {
  strip.begin();
  pinMode(FAN_PIN, OUTPUT);
  
  while (1) {
    ActuatorCommand cmd;
    if (xQueueReceive(qActuatorCommands, &cmd, portMAX_DELAY)) {
      
      if (cmd.device == DEVICE_FAN) {
        // Control fan with PWM
        analogWrite(FAN_PIN, map(cmd.speed, 0, 100, 0, 255));
      }
      else if (cmd.device == DEVICE_LED) {
        // Control LED strip
        for(int i=0; i<LED_COUNT; i++) {
          strip.setPixelColor(i, strip.Color(cmd.r, cmd.g, cmd.b));
        }
        strip.show();
      }
    }
  }
}
