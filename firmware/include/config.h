#ifndef CONFIG_H
#define CONFIG_H

// Credentials live in secrets.h (gitignored; copy secrets.h.example).
// It defines WIFI_SSID, WIFI_PASSWORD, AIO_USERNAME, AIO_KEY.
#include "secrets.h"

// ---------------------------------------------------------------------------------------
// GPIO Pin Configuration (Yolo Uno ESP32-S3 vs Yolo:Bit ESP32)
// ---------------------------------------------------------------------------------------
#if defined(CONFIG_IDF_TARGET_ESP32S3) || defined(BOARD_YOLO_UNO)
#define BOARD_NAME        "Yolo Uno"
#define DHT_SDA    11   // I2C: A4 = SDA 11, A5 = SCL 12
#define DHT_SCL    12
#define LCD_SDA    11
#define LCD_SCL    12
#define FAN_PIN    10   // D7
#define LED_PIN    18   // D9
#define LIGHT_PIN   1   // A0
#define PIR_PIN    38   // D11
#define RELAY_PIN   8   // D5
#define BUZZER_PIN -1
#define ONBOARD_LED_PIN  48
#define ONBOARD_RGB_PIN  45
#define SW1_PIN           6   // D3
#define SW2_PIN           7   // D4
#else
#define BOARD_NAME        "Yolo:Bit"
#define DHT_SDA    21
#define DHT_SCL    22
#define LCD_SDA    21
#define LCD_SCL    22
#define LED_PIN    32   // P0
#define LIGHT_PIN  33   // P1
#define PIR_PIN    13   // P3/6
#define FAN_PIN    26   // P10/13
#define RELAY_PIN  19   // P14/15
#define BUZZER_PIN 25
#define ONBOARD_LED_PIN  -1
#define ONBOARD_RGB_PIN   4
#define SW1_PIN          35
#define SW2_PIN          14
#endif

// ---- Shared by both boards --------------------------------------------------------------
#define STRIP_LED_COUNT   4       // the kit's 4-LED RGB module on LED_PIN
#define LCD_ADDR       0x21       // the kit's LCD 16x2 (last year's working value). If the boot
                                  // I2C scan shows 0x27 or 0x3F instead, use that.
#define TZ_OFFSET_S   25200       // UTC+7, for "MANUAL_LOCKDOWN until HH:MM"

// ---- No device may share a pin with the I2C bus ------------------------------------------
#define _YH_ON_I2C(p) ((p) >= 0 && ((p) == DHT_SDA || (p) == DHT_SCL))
#if _YH_ON_I2C(FAN_PIN) || _YH_ON_I2C(LED_PIN) || _YH_ON_I2C(LIGHT_PIN) || \
    _YH_ON_I2C(PIR_PIN) || _YH_ON_I2C(RELAY_PIN) || _YH_ON_I2C(BUZZER_PIN) || \
    _YH_ON_I2C(SW1_PIN) || _YH_ON_I2C(SW2_PIN)
#error "A device in config.h uses one of the I2C pins (DHT_SDA / DHT_SCL)"
#endif

#define _YH_ON_BTN(p) ((p) >= 0 && ((p) == SW1_PIN || (p) == SW2_PIN))
#if _YH_ON_BTN(FAN_PIN) || _YH_ON_BTN(LED_PIN) || _YH_ON_BTN(LIGHT_PIN) || \
    _YH_ON_BTN(PIR_PIN) || _YH_ON_BTN(RELAY_PIN) || _YH_ON_BTN(BUZZER_PIN)
#error "A device in config.h uses one of the button pins (SW1_PIN / SW2_PIN)"
#endif

// ---- Safety checks, per chip ----------------------------------------------------------
#define _YH_IN(p, lo, hi) ((p) >= (lo) && (p) <= (hi))
#define _YH_ANY_PIN(test) (test(DHT_SDA) || test(DHT_SCL) || test(FAN_PIN) || test(LED_PIN) || \
                           test(LCD_SDA) || test(LCD_SCL) || test(LIGHT_PIN) || test(PIR_PIN) || \
                           test(RELAY_PIN) || test(SW1_PIN) || test(SW2_PIN))
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
// Optimized for maximum output responsiveness:
// - Fast telemetry (temperature, humidity): every 30 s (4 publishes/min instead of 12)
// - Slow telemetry (light, presence): every 60 s (2 publishes/min instead of 4)
// Total telemetry = 6/min (reduced from 16/min), freeing 24 data points/min for commands & ACKs!
#define CLOUD_RATE_PER_MIN       24.0f
#define CLOUD_RATE_BURST         10.0f
#define CLOUD_TELEMETRY_RESERVE   3.0f   // telemetry leaves 3 tokens for ACKs/alerts
#define CLOUD_REPLAY_RESERVE      4.0f   // backlog replay only when >= 5 tokens are free
#define CLOUD_FAST_PERIOD_MS  30000      // temperature, humidity (mean of the window)
#define CLOUD_SLOW_PERIOD_MS  60000      // light (mean), presence (any motion)
#define CLOUD_SLOW_OFFSET_MS  15000      // stagger from the 30 s publishes
#define CLOUD_BACKLOG_MAX      1000      // minutes kept while offline (~16.7 h, 12 KB RAM)
#define CLOUD_SYNC_WINDOW_MS   3000      // values arriving this soon after connect = restore
#define CLOUD_WIFI_KICK_MS    30000
#define CLOUD_READ_MS            30      // processPackets() wait
#define CLOUD_LOOP_MS            20

#endif