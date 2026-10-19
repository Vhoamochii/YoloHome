// bareboard_demo.h — end-to-end test of the Adafruit IO link with NOTHING plugged in.
//
// Stands in for the sensor and control-logic tasks, using only what is on the board itself:
//   board -> Adafruit IO   the on-board LED blinks; the share of time it was lit in each 30 s
//                          window is published to yolohome-light (1 s on / 1 s off -> 50)
//   Adafruit IO -> board   a colour on yolohome-led ("#FF0000", "ON", "OFF") sets the RGB LED
//                          and is ACKed on yolohome-ack; fan commands are refused with "NOHW"
//
// Yolo Uno: the single LED (GPIO 48) blinks; the RGB LED (GPIO 45) shows the commanded colour.
// Yolo:Bit: no single LED, so the first pixel of the RGB matrix blinks in the commanded colour.
// Remove this file (and its task) once the real sensor and control tasks exist.
#pragma once

void bareboard_demo_setup();
void bareboard_demo_step();                 // call every DEMO_STEP_MS
void task_bareboard_demo(void* parameter);  // stack 4096 is plenty