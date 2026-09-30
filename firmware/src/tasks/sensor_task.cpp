#include "sensor_task.h"
#include <DHT.h>

#define DHTPIN 11
#define DHTTYPE DHT20

DHT dht(DHTPIN, DHTTYPE);

void task_sensor(void* parameter) {
  dht.begin();
  
  SensorFrame frame;
  
  while (1) {
    frame.temperature = dht.readTemperature();
    frame.humidity = dht.readHumidity();
    frame.timestamp = millis();
    
    if (!isnan(frame.temperature) && !isnan(frame.humidity)) {
      xQueueSend(qSensorFrames, &frame, portMAX_DELAY);
    }
    
    vTaskDelay(pdMS_TO_TICKS(2000)); // Read every 2 seconds
  }
}
