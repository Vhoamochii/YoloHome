// actuators.h — fan (PWM), 4-LED RGB module, relay, buzzer, on-board status LEDs.
// Fan/strip/relay/buzzer belong to the control task; status/heartbeat to the display task.
#pragma once
#include <stdint.h>

void actuators_init();
void act_fan(uint8_t pct);          // 0..100
void act_strip(uint32_t rgb);       // 0xRRGGBB on all LEDs of the module
void act_relay(bool on);
void act_buzzer(bool on);           // no-op on boards without a buzzer (Yolo Uno)
void act_status(uint32_t rgb);      // on-board RGB LED
void act_heartbeat(bool on);        // on-board single LED, if the board has one
