# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

YoloHome: a smart-home student project. Components:

- **FastAPI backend:** `backend/`.
- **React/Vite frontend:** `frontend/`.
- **ESP32 FreeRTOS firmware:** `firmware/`, for the Yolo Uno (ESP32-S3) and Yolo:Bit (ESP32).
- **Standalone TinyML fire-detection subproject:** `tinyml-fire/`.
- **AI prototype scripts:** `ai-models/`.

The backend and the board never talk directly. Everything goes through **Adafruit IO MQTT feeds**.

User-facing strings (API error messages, UI) and docs (`Guide.md`, `tinyml-fire/`, `LICH_SU_THAY_DOI.md`) are in Vietnamese. Keep new user-facing text in Vietnamese. `Guide.md` walks through the whole system end to end, and `LICH_SU_THAY_DOI.md` is the change history.

The code and `Guide.md` are the source of truth:

- There are 5 FreeRTOS tasks, not 7.
- The database defaults to SQLite, not PostgreSQL.
- There are 10 feeds, not 4.
- Credentials go in `firmware/include/secrets.h`, not `config.h`.
- The live test script is `backend_gateway_test/live_test.py`.

## Commands

Backend (run from `backend/` with the repo-root `.venv`; on Windows a bare `python` can resolve to an interpreter without the packages, so use `..\.venv\Scripts\python.exe` or activate first):
```bash
uvicorn main:app --reload                       # API on :8000, docs at /docs
python -m pytest -q tests                       # full suite (what CI runs)
python -m pytest -q tests/test_backend.py::test_timeout_does_not_overwrite_ack   # single test
python -m compileall .                          # CI syntax check
```
Tests don't need the face ONNX models: `tests/test_face.py` overrides the `get_face_engine` dependency with a fake engine. `tests/conftest.py` stubs `cv2` if it is missing, and the face tests then skip.

Frontend (from `frontend/`): `npm install --legacy-peer-deps`, `npm run dev` (:5173; Vite proxies `/api` to :8000), `npm run build` (`tsc && vite build`). The build is the only check: there is no lint and no test runner.

Firmware (from `firmware/`, PlatformIO):
```bash
pio run -e yolo_uno                 # build (CI does this); yolobit = Yolo:Bit
pio run -e yolo_uno -t upload
pio run -e yolo_uno_demo -t upload  # bare-board link test (src/demo/), nothing plugged in
pio device monitor -e yolo_uno
```
`firmware/README.md` describes host tests at `test/host/run_tests.sh`, but that directory does not exist. CI skips the step when the file is absent.

TinyML fire (from `tinyml-fire/`): `python -m unittest discover tests` (protocol tests). `tests/host_engine.cpp` is a g++ host check of `fire_engine.h`.

## Architecture

### Adafruit IO is the only link between the backend and the board
There are 10 feeds (the free-tier maximum): `yolohome-temperature`, `-humidity`, `-light`, `-presence`, `-ack`, `-event`, `-mode` and `-fan-state` (board → cloud), plus `-fan` and `-led` (commands, cloud → board). Feed keys can be overridden in the backend with `AIO_FEED_<NAME>` env vars.

The wire protocol is a shared contract between `backend/adafruit_mqtt.py` and `firmware/include/adafruitio_task.h`. Change both sides together:

- **Command:** `<value>:<cmd_id>:<actorCode>[:hold_min]`, for example `70:a1b2c3d4:U`. The board ACKs with `<dev>:<cmd_id>:<ok>:<value>:<actor>[:<reason>]`. Rejection reasons are `LOCK` (manual lockdown), `SAFE` (safety override), and others.
- **Size and characters:** every payload is ≤ 44 characters, with no commas or quotes. `feed_safe()` enforces this.
- **Actor codes:** `U V S Y A X` = USER, VOICE, SCHEDULE, SYNC, AI, SYSTEM. A `SYNC` command restores state after a reconnect and must never start a lockdown.
- **Events:** `KIND:data`, for example `SAFETY:46.2`, `AI:70:31.2`, `ANOM:+3.1`, `TINYML:ALERT:0.95`, and backlog replay `B:…`.

### Backend command lifecycle (three threads)
`main.py`'s `lifespan` runs these steps in order:

1. `create_all()` and `upgrade_schema()`.
2. `seed_default_devices()`: the fan and the LED.
3. `register_handlers()`.
4. Connect the MQTT client.
5. Start the scheduler thread.

A command goes through these steps:

1. `device_control.dispatch()` writes an `ActivityLog` row with status `PENDING`. It **commits before publishing**, because the ACK can arrive on the paho network thread at any moment.
2. It then calls `mqtt_client.send_command()`.
3. ACK, timeout and event handlers are registered via `mqtt_client.on(kind, fn)`. They run on the MQTT thread and open their own `SessionLocal()`.
4. Unanswered commands time out after 30 s. `scheduler.py` calls `expire_pending()` on every tick. A timeout only overwrites rows that are still `PENDING`.
5. If the client is offline, the row becomes `OFFLINE`.

Each ACK round-trip is appended to `data/command_latency.csv` (relative to the working directory; override with `AIO_LATENCY_LOG`). The CSV is the NFR-01 latency evidence and is tracked in git, so local runs show it as modified. Tests redirect it to a temp file.

Board data arrives only over MQTT. `routes/webhook.py` (`/api/webhook/adafruit`) is an unused stub.

Shared state (`_pending`, `_state`, `stats`) is guarded by `mqtt_client._lock`. Handlers are emitted outside the lock.

`backend_gateway_test/` holds an **older, diverged copy** of `adafruit_mqtt.py` together with `live_test.py`. Edit `backend/adafruit_mqtt.py`, not that copy.

### Database
- **Engine:** `DATABASE_URL` defaults to SQLite (`backend/yolohome.db`). `database.init_engine()` falls back to SQLite, with an error log, if a PostgreSQL URL can't connect.
- **Schema:** there are no migrations. `models.py` plus `create_all()` is what runs. New columns on an *existing* table need an `ALTER` in `database.upgrade_schema()`. Table names are Vietnamese (`lich_su_cam_bien` = sensor history, `lich_trinh` = schedules, `thiet_bi` = devices). `database/schema.sql` is a separate PostgreSQL script.
- **Time convention** (`timeutil.py`): the DB stores naive UTC, and API responses use `iso_utc()` (appends `Z`). Schedules and CSV export use local time, via `APP_UTC_OFFSET_HOURS` (default 7).

### Tests
`tests/conftest.py` sets `DATABASE_URL` to a temp SQLite file and blanks the Adafruit IO credentials **before importing `main`**. The `board` fixture marks the client connected and records publishes instead of sending them. The `client` fixture drops all tables and runs the app lifespan.

### Firmware
`main.cpp` starts these tasks:

| Task | Core | Priority |
|---|---|---|
| `cloud` | 0 | 2 |
| `sensor` | 1 | 3 |
| `control` | 1 | 4 |
| `display` | 1 | 1 |
| `tinyml` | 1 | 2 |

Only `adafruitio_task.cpp` touches the Adafruit IO library. Other tasks use its queue API (`cloud_post_sample`, `cloud_post_ack`, `qCloudCommands`, …). The `EVT_CLOUD_UP` bit in `gSystemEvents` signals the link state.

Control priority (`control.h`/`control.cpp`) is: safety (>45 °C on, <43 °C off), then manual lockdown (30 min or `hold_min`), then schedule, then AI pre-cooling. Every command gets an ACK, rejections included.

- **Pins:** use only the numeric pins in `include/config.h`. `boards/yolo_uno.json` reuses M5Stack AtomS3 pin names (`SDA`, `LED_BUILTIN`, `A0`…), which are wrong for this board.
- **Optional sensors:** enable them with `-D SENSOR_HAS_LIGHT=1` and `-D SENSOR_HAS_PIR=1`.
- **Platform pin:** `espressif32 @ 7.1.2` (Arduino core 2.x) is pinned on purpose. `lib_ignore = WiFiNINA_-_Adafruit_Fork` is required.
- **Forecast model:** the 15-minute forecast uses a linear trend unless an exported network exists at `include/forecast_model.h`. No training script for it is in the repo. The feature format is documented at the top of `src/control.cpp`.

### TinyML fire detection
`tinyml-fire/` is a self-contained subproject with its own PlatformIO project, scripts and Vietnamese docs. The main firmware builds **its own copies** in `firmware/include/`:

- `fire_engine.h`
- `temperature_model.h`
- `alarm_config.h`
- `fire_serial.h`

These copies have diverged from the `tinyml-fire/firmware/include/` versions; for example, the alarm thresholds differ. Edit the `firmware/include/` copies for the shipped firmware.

The board publishes `TINYML:<state>:<score>` events. The backend stores them in `FireAlertHistory` and serves them at `GET /api/sensors/fire-status`.

### AI scripts (`ai-models/`)
`main.py`, `register-face.py` and `speech.py` are standalone OpenCV/`face_recognition` prototypes. Face login in the app is server-side: `frontend/src/components/FaceCapture.tsx` sends JPEG frames to `backend/routes/auth.py`. The route stores raw SFace vectors in `face_templates` (the old dlib `face_profiles` table is unused) and decides with `face_engine.match()`. Thresholds (plain 0.60, mask 0.65, plus a 0.05 margin the best match must beat the runner-up by) live in `backend/face_models/thresholds.json`; they come from a leave-one-person-out test (`HUONG_FACE_ID.md` 4.4), and OpenCV's 0.363 let strangers in. Users enroll their bare face only; synthetic-mask templates let them log in masked. The engine loads lazily via the `get_face_engine` dependency and returns 503 if the ONNX files are missing. `face-api.js` is in `package.json` but unused.

The masked-face Face ID work is planned in `HUONG_FACE_ID.md`. Its training pipeline lives in `ai-models/face/` (`collect` → `extract_features` → `train_adapter`). The team records once (session 1) as phone videos or photos under `data/raw/<person>/<condition>/`, imported with `collect.py --import`. `evaluate.py` needs a second session and is not part of the current plan.

- **Shared preprocessing:** the scripts import `backend/face_engine.py` (YuNet + SFace via OpenCV, synthetic masks, adapter forward pass in numpy), so training and serving preprocess identically. Changing `AdapterNet` in `train_adapter.py` requires the matching change in `face_engine.apply_adapter`; the script checks parity on export.
- **Models and data:** model files come from `backend/download_face_models.py`. Team photos and features stay in the gitignored `ai-models/face/data/` and `out/`.

## Secrets
- **Backend:** credentials live in `backend/.env` (copy `.env.example`).
- **Firmware:** `firmware/include/secrets.h` (template: `secrets.h.example`) is **tracked in git despite `.gitignore`**. Don't commit edits to it.
