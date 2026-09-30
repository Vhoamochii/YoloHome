#include "tinyml_task.h"
#include "tensorflow/lite/micro/micro_interpreter.h"

const int kTensorArenaSize = 40 * 1024;
uint8_t tensor_arena[kTensorArenaSize];

void task_tinyml(void* parameter) {
  // TODO: Load TFLite model and setup interpreter
  
  while (1) {
    SensorFrame frame;
    if (xQueueReceive(qSensorFrames, &frame, portMAX_DELAY)) {
      // TODO: Run inference
      float score = 0.0f; // Placeholder
      
      InferenceResult result;
      result.score = score;
      result.timestamp = millis();
      
      xQueueSend(qInferenceResults, &result, 0);
    }
  }
}
