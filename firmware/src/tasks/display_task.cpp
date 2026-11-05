// display_task.cpp — see display_task.h.
#include "display_task.h"

#include <Arduino.h>
#include <LiquidCrystal_I2C.h>
#include <Wire.h>
#include <math.h>
#include <string.h>

#include "actuators.h"
#include "config.h"
#include "control_task.h"
#include "i2c_bus.h"
#include "tinyml_task.h"

namespace {
LiquidCrystal_I2C lcd(LCD_ADDR, 16, 2);
bool lcdOk = false;
uint32_t lastProbe = 0;

// A button input. The pressed level is learned at boot from the idle level, so modules that
// read HIGH when pressed and modules that read LOW both work. Don't hold a button at boot.
struct Button {
  int pin;
  void (*onPress)();
  bool pressedLevel = true, lastLevel = false, pressed = false;
  uint32_t lastChange = 0;
  Button(int p, void (*f)()) : pin(p), onPress(f) {}   // C++11 (the ESP32 toolchain) needs it
  void begin() {
    pinMode(pin, INPUT_PULLDOWN);               // a module with its own pull-up still reads HIGH
    delay(5);
    lastLevel = digitalRead(pin) == HIGH;
    pressedLevel = !lastLevel;                  // idle LOW -> pressed HIGH, and vice versa
  }
  void poll(uint32_t now) {
    bool level = digitalRead(pin) == HIGH;
    if (level != lastLevel) { lastLevel = level; lastChange = now; }
    bool down = level == pressedLevel;
    if (down && !pressed && now - lastChange > 50) {   // debounced press
      pressed = true;
      onPress();
    }
    if (!down) pressed = false;
  }
};
Button sw1{SW1_PIN, control_request_fan_step};
Button sw2{SW2_PIN, control_request_cancel_lockdown};

bool probeLcd() {
  I2cLock lock;
  Wire.beginTransmission(LCD_ADDR);
  return Wire.endTransmission() == 0;
}

void startLcd() {
  lastProbe = millis();
  if (!probeLcd()) return;                      // absent: try again in 10 s
  I2cLock lock;
  lcd.init();                                   // calls Wire.begin(): harmless, bus already up
  lcd.backlight();
  lcdOk = true;
}

void writeLine(uint8_t row, const char* text) {
  char padded[17];
  snprintf(padded, sizeof padded, "%-16s", text);   // overwrite the whole line, no flicker
  I2cLock lock;
  lcd.setCursor(0, row);
  lcd.print(padded);
}

void temp(char* b, size_t n, float v) {
  if (isnan(v)) snprintf(b, n, "--.-");
  else snprintf(b, n, "%.1f", double(v));
}

void refresh(const ControlStatus& s, uint32_t now) {
  char t[8], f[8], l1[24], l2[24];
  temp(t, sizeof t, s.temp);
  if (isnan(s.humi)) snprintf(l1, sizeof l1, "%sC --%% F%3u", t, s.fan);
  else snprintf(l1, sizeof l1, "%sC %2.0f%% F%3u", t, double(s.humi), s.fan);
  temp(f, sizeof f, s.t15);
  TinyMlStatus ml;
  bool haveMl = tinyml_status(ml);
  if (haveMl && ml.alarm && !isnan(ml.score)) {
    snprintf(l2, sizeof l2, "FIRE! Score:%.2f", double(ml.score));
  } else if (s.safety) snprintf(l2, sizeof l2, "SAFETY! %sC", t);
  else if (s.hot && s.mode != ctl::Mode::ManualLockdown) snprintf(l2, sizeof l2, "HOT! t15 %sC", f);
  else if (s.mode == ctl::Mode::ManualLockdown)
    snprintf(l2, sizeof l2, "LOCK %lum left", (unsigned long)((s.lockRemainingMs + 59999) / 60000));
  else if (s.mode == ctl::Mode::OfflineFailsafe) snprintf(l2, sizeof l2, "OFF  t15 %sC", f);
  else snprintf(l2, sizeof l2, "AUTO t15 %sC", f);
  if (!(haveMl && ml.alarm) && s.anomaly) { size_t k = strlen(l2); if (k < 15) { l2[k] = ' '; l2[k + 1] = '!'; l2[k + 2] = 0; } }
  if (lcdOk) {
    writeLine(0, l1);
    writeLine(1, l2);
  }
  uint32_t color = (s.safety || (haveMl && ml.alarm)) ? (((now / 250) % 2) ? 0xFF0000 : 0)
                 : s.hot ? (((now / 500) % 2) ? 0xFF6000 : 0)       // heat warning: slow orange
                 : s.mode == ctl::Mode::ManualLockdown ? 0x0040FF
                 : s.mode == ctl::Mode::OfflineFailsafe ? 0xFF8000 : 0x00FF00;
  act_status(color);
}
}  // namespace

void task_display(void* parameter) {
  (void)parameter;
  sw1.begin();
  sw2.begin();
  Serial.printf("[btn] SW1 (GPIO %d) and SW2 (GPIO %d): pressed = %s / %s\n", SW1_PIN, SW2_PIN,
                sw1.pressedLevel ? "HIGH" : "LOW", sw2.pressedLevel ? "HIGH" : "LOW");
  startLcd();
  Serial.println(lcdOk ? "[lcd] found" : "[lcd] not found at LCD_ADDR (see the boot I2C scan)");
  uint32_t lastRefresh = 0;
  for (;;) {
    uint32_t now = millis();
    sw1.poll(now);
    sw2.poll(now);

    if (!lcdOk && now - lastProbe > 10000) startLcd();   // plugged in later
    if (now - lastRefresh >= 250) {                       // 4 Hz: smooth red flashing
      lastRefresh = now;
      ControlStatus s;
      if (control_status(s)) refresh(s, now);
      act_heartbeat((now / 1000) % 2);
    }
    vTaskDelay(pdMS_TO_TICKS(20));
  }
}