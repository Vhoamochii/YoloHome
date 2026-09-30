#ifndef CONFIG_H
#define CONFIG_H

// WiFi Configuration
#define WIFI_SSID "your_wifi_ssid"
#define WIFI_PASSWORD "your_wifi_password"

// Adafruit IO Configuration
#define AIO_USERNAME "your_adafruit_username"
#define AIO_KEY "your_adafruit_key"

// GPIO Pin Configuration
#define DHT_SDA 11
#define DHT_SCL 12
#define FAN_PIN 7
#define LED_PIN 9
#define LCD_SDA 11
#define LCD_SCL 12

// MQTT Topics
#define FEED_TEMPERATURE "yolohome/temperature"
#define FEED_HUMIDITY "yolohome/humidity"
#define FEED_FAN "yolohome/fan"
#define FEED_LED "yolohome/led"

// AI Configuration
#define AI_THRESHOLD_HIGH 0.68
#define AI_THRESHOLD_LOW 0.48
#define MANUAL_LOCKDOWN_MS 1800000 // 30 minutes

#endif
