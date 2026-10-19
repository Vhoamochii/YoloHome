#ifndef CONFIG_H
#define CONFIG_H

// Credentials live in secrets.h (gitignored; copy secrets.h.example).
// It defines WIFI_SSID, WIFI_PASSWORD, AIO_USERNAME, AIO_KEY.
#include "secrets.h"

#define BOARD_YOLO_UNO

// ---------------------------------------------------------------------------------------
// GPIO Pin Configuration — chosen by the chip being compiled for, so switching boards only
// means switching the PlatformIO environment (see platformio.ini).
// Port -> GPIO maps come from OhStem's board package: github.com/AITT-VN/ohstem_arduino_board
// (variants/yolobit/ and variants/yolo_uno/pins_arduino.h). -1 = not present on this board.
#if defined(CONFIG_IDF_TARGET_ESP32S3) || defined(BOARD_YOLO_UNO)
// ===== Yolo Uno (ESP32-S3) =====
//   I2C: A4 = SDA = 11, A5 = SCL = 12.  Analog-capable with WiFi on: A0-A3 = GPIO 1-4.
//   With the yolo_uno.json board file the Arduino defaults are the M5Stack AtomS3's
//   (SDA 38, SCL 39, LED_BUILTIN = an RGB LED): call Wire.begin(DHT_SDA, DHT_SCL) BEFORE
//   any I2C library's begin(), and never use SDA/SCL/LED_BUILTIN/Dn/An by name.
//   D3=6 D4=7 D5=8 D6=9 D7=10 D8=17 D9=18 D10=21 D11=38 D12=47 D13=48
#define BOARD_NAME        "Yolo Uno"
#define DHT_SDA    11   // A4
#define DHT_SCL    12   // A5
#define LCD_SDA    11
#define LCD_SCL    12
#define FAN_PIN    10   // D7  (port D7-D8)  — used by last year's working code
#define LED_PIN    18   // D9  (port D9-D10) — used by last year's working code
#define LIGHT_PIN   1   // A0  (port A0-A1)  — inferred, confirm on your board
#define PIR_PIN     6   // D3  (port D3-D4)  — inferred, confirm on your board
#define RELAY_PIN   8   // D5  (port D5-D6)  — inferred, confirm on your board
#define BUZZER_PIN -1   // the Yolo Uno has no buzzer
#define ONBOARD_LED_PIN  48   // D13 / LED_BUILTIN
#define ONBOARD_RGB_PIN  45   // single RGB LED (NeoPixel)
#else
// ===== Yolo:Bit (ESP32) + expansion board =====
//   Single-signal slots: P0=32  P1=33  P2=27 (analog via GPIO39)
//   Two-signal slots (the FIRST signal is the one you drive):
//                        P16/12=5/2  P14/15=19/23  P10/13=26/18  P3/6=13/12
//   I2C1, I2C2:          P20=SDA=21  P19=SCL=22   (DHT20 and LCD must use these)
#define BOARD_NAME        "Yolo:Bit"
#define DHT_SDA    21   // I2C1 or I2C2
#define DHT_SCL    22
#define LCD_SDA    21   // same I2C bus as the DHT20
#define LCD_SCL    22
#define LED_PIN    32   // P0      4-LED RGB (book: P0)
#define LIGHT_PIN  33   // P1      analog; only P0/P1/P2 can read analog sensors
#define PIR_PIN    13   // P3/6    motion sensor (book: P3)
#define FAN_PIN    26   // P10/13  mini fan, PWM (book: P0 or P10/13; never the I2C slots)
#define RELAY_PIN  19   // P14/15
#define BUZZER_PIN 25   // on the Yolo:Bit itself, no slot needed
#define ONBOARD_LED_PIN  -1   // no single LED
#define ONBOARD_RGB_PIN   4   // the 5x5 RGB matrix; the demo lights only its first pixel
#endif

// ---- Safety checks, per chip ----------------------------------------------------------
#define _YH_IN(p, lo, hi) ((p) >= (lo) && (p) <= (hi))
#define _YH_ANY_PIN(test) (test(DHT_SDA) || test(DHT_SCL) || test(FAN_PIN) || test(LED_PIN) || \
                           test(LCD_SDA) || test(LCD_SCL) || test(LIGHT_PIN) || test(PIR_PIN) || \
                           test(RELAY_PIN))
#if defined(CONFIG_IDF_TARGET_ESP32)     // Yolo:Bit
#define _YH_FLASH(p) _YH_IN(p, 6, 11)
#if _YH_ANY_PIN(_YH_FLASH)
#error "GPIO 6-11 are the flash pins on ESP32: they cannot be used"
#endif
#if DHT_SDA == 12 || DHT_SCL == 12 || LCD_SDA == 12 || LCD_SCL == 12
#error "GPIO 12 is a strapping pin on ESP32; an I2C pull-up on it can prevent booting"
#endif
#if !_YH_IN(LIGHT_PIN, 32, 39)
#error "LIGHT_PIN must be an ADC1 pin (GPIO 32-39): ADC2 pins stop working once WiFi is on"
#endif
#elif defined(CONFIG_IDF_TARGET_ESP32S3) // Yolo Uno
#define _YH_FLASH(p) _YH_IN(p, 26, 32)
#if _YH_ANY_PIN(_YH_FLASH)
#error "GPIO 26-32 are the flash/PSRAM pins on ESP32-S3: they cannot be used"
#endif
#define _YH_STRAP(p) ((p) == 0 || (p) == 3 || (p) == 45 || (p) == 46)
#if _YH_STRAP(DHT_SDA) || _YH_STRAP(DHT_SCL) || _YH_STRAP(LCD_SDA) || _YH_STRAP(LCD_SCL)
#error "GPIO 0/3/45/46 are strapping pins on ESP32-S3; an I2C pull-up can change boot mode"
#endif
#if !_YH_IN(LIGHT_PIN, 1, 10)
#error "LIGHT_PIN must be an ADC1 pin (GPIO 1-10) on ESP32-S3: ADC2 conflicts with WiFi"
#endif
#endif

// ---------------------------------------------------------------------------------------
// Adafruit IO feed keys. Must match backend .env (AIO_FEED_*) — defaults are identical.
// Keys use dashes: a '/' is not part of a feed key (the topic is <user>/feeds/<key>).
// 10 feeds = the Adafruit IO free-tier maximum; adding one means dropping another.
#define FEED_TEMPERATURE "yolohome-temperature"
#define FEED_HUMIDITY    "yolohome-humidity"
#define FEED_LIGHT       "yolohome-light"
#define FEED_PRESENCE    "yolohome-presence"
#define FEED_FAN         "yolohome-fan"        // command: backend/dashboard -> board
#define FEED_LED         "yolohome-led"        // command
#define FEED_ACK         "yolohome-ack"        // board -> backend
#define FEED_EVENT       "yolohome-event"      // board -> backend (alerts + offline backlog)
#define FEED_MODE        "yolohome-mode"       // AUTO_AI / MANUAL_LOCKDOWN until HH:MM / ...
#define FEED_FAN_STATE   "yolohome-fan-state"  // actual fan %, not the last command

// ---------------------------------------------------------------------------------------
// AI Configuration
#define AI_THRESHOLD_HIGH 0.68
#define AI_THRESHOLD_LOW 0.48
#define MANUAL_LOCKDOWN_MS 1800000   // 30 minutes (a command may carry its own hold_min)

// ---------------------------------------------------------------------------------------
// Cloud link (adafruitio_task.cpp)
// Free tier: 30 data points/min for the whole ACCOUNT, backend commands included.
// A token bucket admits at most BURST + RATE messages in any 60 s window: 5 + 20 = 25,
// leaving >= 5/min for the backend. Live telemetry needs 16/min.
#define CLOUD_RATE_PER_MIN       20.0f
#define CLOUD_RATE_BURST          5.0f
#define CLOUD_TELEMETRY_RESERVE   1.0f   // telemetry leaves 1 token for ACKs/alerts
#define CLOUD_REPLAY_RESERVE      3.0f   // backlog replay only when >= 4 tokens are free
#define CLOUD_FAST_PERIOD_MS  10000      // temperature, humidity (mean of the window)
#define CLOUD_SLOW_PERIOD_MS  30000      // light (mean), presence (any motion)
#define CLOUD_SLOW_OFFSET_MS   5000      // stagger from the 10 s publishes
#define CLOUD_BACKLOG_MAX      1000      // minutes kept while offline (~16.7 h, 12 KB RAM)
#define CLOUD_SYNC_WINDOW_MS   3000      // values arriving this soon after connect = restore
#define CLOUD_WIFI_KICK_MS    30000
#define CLOUD_READ_MS            50      // processPackets() wait
#define CLOUD_LOOP_MS            50

#endif