#ifndef TYPES_H
#define TYPES_H

#include <stdint.h>

// Sensor data frame
typedef struct {
    float temperature;
    float humidity;
    uint32_t timestamp;
} SensorFrame;

// AI inference result
typedef struct {
    float score;
    uint32_t timestamp;
    bool predictedHot;
} InferenceResult;

// User command from MQTT
typedef struct {
    uint8_t device;
    uint8_t action;
    uint8_t value;
    bool isManual;
} UserCommand;

// Actuator command
typedef struct {
    uint8_t device;
    uint8_t action;
    uint8_t speed;
    uint8_t r, g, b;
} ActuatorCommand;

// Device types
#define DEVICE_FAN 1
#define DEVICE_LED 2

// Actions
#define ACTION_OFF 0
#define ACTION_ON 1
#define ACTION_SET_SPEED 2
#define ACTION_SET_COLOR 3

// Override modes
#define OVERRIDE_MODE_AUTO 0
#define OVERRIDE_MODE_FORCE_ON 1
#define OVERRIDE_MODE_FORCE_OFF 2

#endif
