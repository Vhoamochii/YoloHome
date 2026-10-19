// adafruitio_task.h — the only code on the board that talks to Adafruit IO.
//
// Other tasks never call the Adafruit IO library (it is not thread-safe). They use the
// cloud_post_*() functions below, which only enqueue, and they read commands from
// qCloudCommands. All of them are safe to call from any task; none of them block.
//
//   sensor task      -> cloud_post_sample()            every reading (2 s)
//   control logic    <- qCloudCommands                 commands from backend / dashboard
//   control logic    -> cloud_post_ack()               after arbitration (accepted or rejected)
//                    -> cloud_post_mode(), cloud_post_fan_state(), cloud_post_event()
//   anyone           <- EVT_CLOUD_UP in gSystemEvents  set while connected to Adafruit IO;
//                                                      clear => enter OFFLINE_FAILSAFE
#pragma once
#include <Arduino.h>
#include <freertos/FreeRTOS.h>
#include <freertos/event_groups.h>
#include <freertos/queue.h>
#include <stddef.h>
#include <stdint.h>

// =====================================================================================
// Part 1 — message formats and helpers (namespace cloud). Used by the task; declared
// here so the PC tests in test/host/ can exercise them directly.
// =====================================================================================
// WHY NOT JSON: the Adafruit IO Arduino library (v4.3.7) stores every feed value in a 45-byte
// buffer filled with strcpy() and no bounds check (AIO_DATA_LENGTH in AdafruitIO_Definitions.h),
// and it sends/receives values as CSV. A value of 45+ characters overflows memory on the board;
// a comma splits the value. So every payload here is colon-separated, <= kMaxValue characters,
// and never contains ',' or '"'. The backend (backend/adafruit_mqtt.py) enforces the same rules.
//
// Formats (same fields as the Python gateway's serial frames, minus the !…# wrapper):
//   command  backend -> board   "<value>[:<id>[:<actor>[:<hold_min>]]]"   e.g. "70:a1b2c3d4:S"
//            dashboard -> board "70", "ON", "#FF8800"   (no id, actor USER)
//   ack      board -> backend   "<dev>:<id|->:<1|0>:<value>:<actor>[:<reason>]"
//                                                          e.g. "fan:a1b2c3d4:1:70:S"
//   event    board -> backend   "<TYPE>:<data>"                           e.g. "SAFETY:46.2"
//   buffered board -> backend   "B:<epoch|0>:<temp>:<humi>:<light>:<presence>"
namespace cloud {

constexpr size_t kMaxValue = 44;   // 45-byte library buffer minus the terminating NUL
constexpr size_t kIdLen = 8;       // command ids are 8 hex chars, like the Python gateway

enum class Device : uint8_t { Fan, Led, Relay };
enum class Actor : uint8_t { User, Voice, Schedule, Sync, Ai, System };

char actorCode(Actor a);           // U V S Y A X
const char* deviceName(Device d);  // "fan" "led" "relay"

struct Command {
  Device device = Device::Fan;
  uint8_t fanPct = 0;              // Device::Fan   0..100
  uint32_t rgb = 0;                // Device::Led   0xRRGGBB
  bool relayOn = false;            // Device::Relay
  char id[kIdLen + 1] = {0};       // "" when the sender gave none (Adafruit dashboard)
  Actor actor = Actor::User;
  uint16_t holdMin = 0;            // 0 = use the configured lockdown length
};

enum class ParseError : uint8_t { None, Empty, TooLong, BadValue, BadId };
const char* parseErrorName(ParseError e);

// Parses a command payload. On BadValue, out.id and out.actor are still filled in so the
// caller can send a rejecting ACK that references the command.
// Semantics match aura_core.py: fan "ON"/"OFF"/0..100 (so "1" means 1 %, NOT on);
// led "ON"/"OFF"/"1"/"0"/"#RRGGBB" (also accepts bare "RRGGBB"); relay ON/OFF/1/0.
// Actors other than U/V/S cannot be claimed remotely and become USER. isSync forces SYNC.
ParseError parseCommand(Device dev, const char* payload, bool isSync, Command& out);

// Writes the canonical value of a command ("70", "FF8800", "1") into buf.
size_t formatValue(const Command& c, char* buf, size_t n);

// All formatters return the length written, or 0 if the result would not fit in
// min(n - 1, kMaxValue) or would contain a forbidden character.
size_t formatAck(char* buf, size_t n, Device dev, const char* id, bool ok, const char* value,
                 Actor actor, const char* reason = nullptr);
size_t formatEvent(char* buf, size_t n, const char* type, const char* data);
size_t formatText(char* buf, size_t n, const char* text);   // free text, e.g. mode
bool feedSafe(const char* text);   // fits kMaxValue, no ',' '"' or control characters

// ---- Telemetry ---------------------------------------------------------------------------
struct Sample {                    // one sensor reading; NaN means "read failed / no sensor"
  float temp = 0, humi = 0, light = 0;
  bool presence = false;
  bool presenceValid = true;       // false when the board has no motion sensor
};

class Aggregator {                 // mean per field over a window, NaN-tolerant
 public:
  void add(const Sample& s);
  bool mean(Sample& out) const;    // false if no valid temperature or humidity
  bool lightMean(float& out) const;          // independent of temperature/humidity
  bool presence(bool& out) const;            // false if no sample had a motion sensor
  uint16_t count() const { return n_; }
  void reset();
 private:
  double t_ = 0, h_ = 0, l_ = 0;
  uint16_t nt_ = 0, nh_ = 0, nl_ = 0, np_ = 0, n_ = 0;
  bool presence_ = false;          // any motion in the window
};

struct Buffered {                  // one minute while offline: 12 bytes
  uint32_t epoch;                  // UTC seconds; 0 if the clock was never synced
  int16_t temp_c100;
  uint16_t humi_10;
  uint16_t light;
  uint8_t presence;
};
Buffered pack(uint32_t epoch, const Sample& s);
size_t formatBuffered(char* buf, size_t n, const Buffered& b);

// Fixed-size FIFO. When full, push() overwrites the OLDEST entry and counts it as dropped:
// after a long outage the most recent hours matter more than the oldest minutes.
template <typename T, size_t N>
class Ring {
 public:
  void push(const T& v) {
    if (size_ == N) { head_ = (head_ + 1) % N; --size_; ++dropped_; }
    buf_[(head_ + size_) % N] = v;
    ++size_;
  }
  bool front(T& out) const { if (!size_) return false; out = buf_[head_]; return true; }
  void pop() { if (size_) { head_ = (head_ + 1) % N; --size_; } }
  size_t size() const { return size_; }
  uint32_t dropped() const { return dropped_; }
 private:
  T buf_[N];
  size_t head_ = 0, size_ = 0;
  uint32_t dropped_ = 0;
};

// ---- Rate limiting -----------------------------------------------------------------------
// Token bucket, same policy as the Python gateway's RateLimiter: low-priority traffic must
// leave `reserve` tokens for high-priority traffic (ACKs, alerts). Times are millis() and
// survive the 49-day wrap-around.
class TokenBucket {
 public:
  TokenBucket(float perMinute, float burst);
  bool tryAcquire(uint32_t nowMs, float reserve = 0);
  void pause(uint32_t nowMs, uint32_t ms);
 private:
  void refill(uint32_t nowMs);
  float ratePerMs_, cap_, tokens_;
  uint32_t last_ = 0, pausedUntil_ = 0;
  bool started_ = false, paused_ = false;
};

// Remembers the last few command ids so a QoS 1 redelivery is not executed twice.
class RecentIds {
 public:
  bool seenOrAdd(const char* id);  // true if id was already seen; "" is never a duplicate
 private:
  char ids_[8][kIdLen + 1] = {};
  uint8_t next_ = 0;
};

}  // namespace cloud

// =====================================================================================
// Part 2 — the task and the API other FreeRTOS tasks use
// =====================================================================================
// Bit on your existing system event group. CHECK that it does not collide with the bits
// already used in your firmware (EVT_WIFI_CONNECTED, EVT_AI_COOLING, ...) and change it if so.
#ifndef EVT_CLOUD_UP
#define EVT_CLOUD_UP (1 << 8)
#endif

extern EventGroupHandle_t gSystemEvents;   // defined elsewhere in your firmware

struct CloudCommandMsg {
  cloud::Command cmd;
  uint32_t receivedMs;                     // millis() when it arrived, for latency logging
};
extern QueueHandle_t qCloudCommands;       // cloud -> control logic (length 8)

struct CloudStats {
  uint32_t published, rateDropped, publishFailed, commandsIn, commandsRejected, duplicates,
      backlogSent, reconnects;
  size_t backlog;
  uint32_t backlogDropped;
};

void cloud_init();                         // create queues; call once BEFORE starting tasks
void task_adafruitio(void* parameter);     // stack >= 8192: TLS needs it

bool cloud_post_sample(const cloud::Sample& s);
bool cloud_post_ack(cloud::Device dev, const char* id, bool ok, const char* value,
                    cloud::Actor actor, const char* reason = nullptr);  // reason: LOCK, SAFE, BAD
bool cloud_post_event(const char* type, const char* data);
bool cloud_post_mode(const char* modeText);          // e.g. "MANUAL_LOCKDOWN until 15:12"
bool cloud_post_fan_state(uint8_t pct);
CloudStats cloud_stats();

// Split out so the loop can be unit-tested on a PC; task_adafruitio() just calls these.
void cloud_setup();
void cloud_step();