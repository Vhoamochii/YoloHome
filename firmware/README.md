# YoloHome firmware

One codebase for the **Yolo Uno** (ESP32-S3) and the **Yolo:Bit** (ESP32). `include/config.h`
picks the pins from the chip being compiled for; you choose the board with the PlatformIO
environment.

| Environment | What it builds |
|---|---|
| `yolo_uno`, `yolobit` | Full firmware |
| `yolo_uno_demo`, `yolobit_demo` | Bare-board link test (`src/demo/`): nothing plugged in, LED blink → `yolohome-light`, colour commands → RGB LED |

```bash
pio run -e yolo_uno -t upload
pio device monitor -e yolo_uno
```

## Setup

1. **Board file (Yolo Uno only):** `boards/yolo_uno.json` comes from
   [nhanksd85/YoloUNO_PlatformIO](https://github.com/nhanksd85/YoloUNO_PlatformIO) (branch
   `LED_Blinky`), tested on a real board. It reuses the M5Stack AtomS3 pin names, so `SDA`,
   `SCL`, `LED_BUILTIN`, `D7`, `A0` … are **wrong** for the Yolo Uno: use only `config.h`.
2. **Credentials:** copy `include/secrets.h.example` to `include/secrets.h` and fill it in.
   WiFi must be 2.4 GHz without a login web page (a phone hotspot works).
3. **Adafruit IO feeds:** create these 10 keys (the free-tier maximum) —
   `yolohome-temperature`, `-humidity`, `-light`, `-presence`, `-fan`, `-led`, `-ack`, `-event`,
   `-mode`, `-fan-state`.
4. **Optional sensors:** once plugged in, add `-D SENSOR_HAS_LIGHT=1` / `-D SENSOR_HAS_PIR=1`
   to `build_flags` (see the comment in `platformio.ini`).

## Wiring

| Device | Yolo Uno | Yolo:Bit (expansion board) |
|---|---|---|
| DHT20 + LCD 16x2 (I2C) | I2C port: SDA 11, SCL 12 | I2C1 / I2C2: SDA 21, SCL 22 |
| Mini fan | D7 (GPIO 10) | P10/13 (GPIO 26) |
| 4-LED RGB modulepio device monitor -e yolo_uno | D9 (GPIO 18) | P0 (GPIO 32) |
| Light sensor (analog) | A0 (GPIO 1)* | P1 (GPIO 33) |
| PIR motion sensor | D3 (GPIO 6)* | P3/6 (GPIO 13) |
| Relay | D5 (GPIO 8)* | P14/15 (GPIO 19) |
| Buzzer | — (none) | on board (GPIO 25) |
| Button | D3–D4 (GPIO 0) | A (GPIO 35) |

\* Inferred from the board's port pairs; confirm against the connectors. Fan and LED pins on
the Yolo Uno match last year's working code. `config.h` refuses to compile with pins that are
unsafe on the chip (flash pins, strapping pins on I2C, light sensor on an ADC that WiFi blocks).

## What runs

| Task | Core | Role |
|---|---|---|
| `cloud` (`adafruitio_task`) | 0 | Adafruit IO: telemetry, commands, ACKs, offline backlog. Never blocks |
| `sensor` | 1 | DHT20 every 2 s (+ light, PIR); retries if the sensor is unplugged |
| `control` | 1 | Safety → manual lockdown → schedule → AI; drives the actuators; ACKs every command |
| `display` | 1 | LCD, on-board status LED, button |

**Behaviour** (`include/control.h`, ported from the gateway's reference logic):

- **Safety:** above 45 °C → fan 100 %, LEDs red, buzzer, mode `SAFETY_OVERRIDE`; released below
  43 °C. Fan/LED commands are refused with `SAFE` meanwhile.
- **Manual lockdown:** a user or voice fan command holds the fan for 30 min (or the command's
  `hold_min`). AI and schedules are refused with `LOCK`. The button cancels it.
- **Schedule:** applied without lockdown; with `hold_min` it pauses the AI that long.
- **Restore (`SYNC`):** after a reconnect the last commanded values are applied, never locking.
- **AI pre-cooling:** the 15-minute forecast drives a smoothed discomfort score with
  hysteresis; the fan runs 40–100 % in 10 % steps while someone is present (motion in the last
  10 min; always "present" without a PIR). In the host tests a room warming 0.1 °C/min starts
  the fan at 29.0 °C, one degree before the 30 °C comfort threshold.
- **Anomaly:** a temperature far from what was forecast 15 min earlier, 3 minutes in a row,
  is reported as `ANOM` (active after ~45 min of data).
- **Offline:** mode `OFFLINE_FAILSAFE`; local control continues and the backlog is replayed later.

Cloud messages (all ≤ 44 characters, no commas — see `adafruitio_task.h`): ACKs
`fan:<id>:1:70:U`, events `SAFETY:46.2`, `AI:70:31.2`, `ANOM:+3.1`, backlog `B:…`, mode text,
fan state.

## The forecast model

There is **no trained model yet**. The forecaster uses a measurable baseline — a least-squares
trend over the last 10 one-minute means — so the system runs end to end. To use the trained
network, put its exported weights in `include/forecast_model.h`; it is picked up
automatically. The required format and the exact input features are documented at the top of
`src/control.cpp`; the training script must build its features the same way.

## Tests (on a PC, no hardware)

```bash
test/host/run_tests.sh
```

Runs the message-format tests, simulations of the cloud task (outages, restores, rate limits),
the bare-board demo, the control logic, and a compile check of every source file for both
chips and both Arduino core generations. Needs only `g++`.

## Not yet verified on hardware

Tested on the real Yolo Uno so far: the cloud link and the bare-board demo. Not yet run on a
board: the sensor, control and display tasks, the Yolo:Bit build, and the inferred Yolo Uno
ports for light, PIR and relay. Expect the first full build to surface a few issues.
