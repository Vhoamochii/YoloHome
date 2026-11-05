#pragma once
#define FIRE_SDA 11
#define FIRE_SCL 12
#define FIRE_LED_PIN 48
// External ACTIVE buzzer, if fitted, must be wired to a free GPIO and GND.
// Use a driver for a load exceeding the GPIO rating. -1 disables it.
#define FIRE_BUZZER_PIN -1
#define FIRE_SAMPLE_MS 2000u
#ifndef TINYML_SIMULATED
#define TINYML_SIMULATED 0
#endif
