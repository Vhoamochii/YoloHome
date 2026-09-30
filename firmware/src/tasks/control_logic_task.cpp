#include "control_logic_task.h"

void task_control_logic(void* parameter) {
  while (1) {
    InferenceResult result;
    if (xQueueReceive(qInferenceResults, &result, portMAX_DELAY)) {
      
      // Check if manual lockdown is active
      // TODO: Implement auto cooling logic
      
      if (result.score > 0.68) {
        // Send command to turn on fan
        ActuatorCommand cmd;
        cmd.device = DEVICE_FAN;
        cmd.action = ACTION_ON;
        cmd.speed = 100;
        xQueueSend(qActuatorCommands, &cmd, 0);
      }
    }
  }
}
