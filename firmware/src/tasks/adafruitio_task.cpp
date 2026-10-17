// adafruitio_task.cpp — the board's link to Adafruit IO (replaces the TODO stub).
//
// Ported from the Python gateway (gateway.py / aura_core.py), minus what the direct link makes
// unnecessary (serial framing, LINK heartbeat). What carries over:
//   - token-bucket rate limiting under the free tier's 30 points/min, with priorities
//   - ACKs for every command (rejections included), duplicate suppression
//   - restoring the last commanded fan/LED state after (re)connect WITHOUT triggering lockdown
//   - offline backlog: one aggregate per minute while the cloud is unreachable, replayed later
//     WITH its original timestamp (the Python gateway re-published with the current time)
// Part 1 (formatting/parsing, rate limiting, buffering) is unit-tested on a PC: test/host/.
#include "adafruitio_task.h"

#include <AdafruitIO_WiFi.h>
#include <WiFi.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#include "config.h"    // feeds, tuning; includes secrets.h (credentials, gitignored)

// =====================================================================================
// Part 1 — message formats and helpers (formats and rationale: see adafruitio_task.h)
// =====================================================================================
namespace cloud {
namespace {

void trimCopy(const char* src, size_t len, char* dst, size_t cap) {
  while (len && (*src == ' ' || *src == '\t' || *src == '\r' || *src == '\n')) { ++src; --len; }
  while (len && (src[len - 1] == ' ' || src[len - 1] == '\t' || src[len - 1] == '\r' ||
                 src[len - 1] == '\n')) { --len; }
  if (len >= cap) len = cap - 1;
  memcpy(dst, src, len);
  dst[len] = '\0';
}

void upper(char* s) {
  for (; *s; ++s) if (*s >= 'a' && *s <= 'z') *s = char(*s - 'a' + 'A');
}

bool eq(const char* a, const char* b) { return strcmp(a, b) == 0; }

bool isHex6(const char* s) {
  if (strlen(s) != 6) return false;
  for (int i = 0; i < 6; ++i) {
    char c = s[i];
    if (!((c >= '0' && c <= '9') || (c >= 'A' && c <= 'F'))) return false;
  }
  return true;
}

// Python float() semantics for the inputs we care about; rejects hex floats ("0x1A"),
// which strtof would accept but float() would not.
bool parseNumber(const char* s, float& out) {
  if (!*s || strchr(s, 'x') || strchr(s, 'X')) return false;
  char* end = nullptr;
  float v = strtof(s, &end);
  if (end == s || *end != '\0' || isnan(v)) return false;
  out = v;
  return true;
}

// A value may go into a feed only if it fits the library buffer and survives CSV.
bool safeForFeed(const char* s, size_t n) {
  size_t len = strlen(s);
  size_t limit = (n ? n - 1 : 0) < kMaxValue ? (n ? n - 1 : 0) : kMaxValue;
  if (len == 0 || len > limit) return false;
  for (const char* p = s; *p; ++p)
    if (*p == ',' || *p == '"' || (unsigned char)*p < 0x20) return false;
  return true;
}

size_t finish(char* buf, size_t n, int written) {
  if (written <= 0 || size_t(written) >= n || !safeForFeed(buf, n)) {
    if (n) buf[0] = '\0';
    return 0;
  }
  return size_t(written);
}

}  // namespace

char actorCode(Actor a) {
  switch (a) {
    case Actor::User: return 'U';
    case Actor::Voice: return 'V';
    case Actor::Schedule: return 'S';
    case Actor::Sync: return 'Y';
    case Actor::Ai: return 'A';
    case Actor::System: return 'X';
  }
  return 'U';
}

const char* deviceName(Device d) {
  switch (d) {
    case Device::Fan: return "fan";
    case Device::Led: return "led";
    case Device::Relay: return "relay";
  }
  return "?";
}

const char* parseErrorName(ParseError e) {
  switch (e) {
    case ParseError::None: return "OK";
    case ParseError::Empty: return "EMPTY";
    case ParseError::TooLong: return "LONG";
    case ParseError::BadValue: return "BAD";
    case ParseError::BadId: return "BADID";
  }
  return "BAD";
}

ParseError parseCommand(Device dev, const char* payload, bool isSync, Command& out) {
  out = Command();
  out.device = dev;
  out.actor = isSync ? Actor::Sync : Actor::User;
  if (!payload) return ParseError::Empty;
  if (strlen(payload) > kMaxValue) return ParseError::TooLong;

  // Split into at most 4 fields: value, id, actor, hold_min.
  char field[4][kMaxValue + 1] = {{0}};
  int nf = 0;
  const char* start = payload;
  for (const char* p = payload;; ++p) {
    if (*p == ':' || *p == '\0') {
      if (nf < 4) trimCopy(start, size_t(p - start), field[nf], sizeof field[nf]);
      ++nf;
      if (*p == '\0') break;
      start = p + 1;
    }
  }
  if (nf > 4) return ParseError::BadValue;

  // id and actor first, so a rejected command can still be acknowledged by id.
  if (nf > 1 && field[1][0]) {
    size_t len = strlen(field[1]);
    if (len > kIdLen) return ParseError::BadId;
    for (size_t i = 0; i < len; ++i) {
      char c = field[1][i];
      bool alnum = (c >= '0' && c <= '9') || (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z');
      if (!alnum) return ParseError::BadId;
    }
    memcpy(out.id, field[1], len + 1);
  }
  if (!isSync && nf > 2) {
    char a[kMaxValue + 1];
    memcpy(a, field[2], sizeof a);
    upper(a);
    if (eq(a, "V") || eq(a, "VOICE")) out.actor = Actor::Voice;
    else if (eq(a, "S") || eq(a, "SCHEDULE")) out.actor = Actor::Schedule;
    else out.actor = Actor::User;     // AI / SYSTEM / unknown cannot be claimed remotely
  }

  char v[kMaxValue + 1];
  memcpy(v, field[0], sizeof v);
  upper(v);
  if (!v[0]) return ParseError::Empty;

  if (nf > 3 && field[3][0]) {
    float h;
    if (!parseNumber(field[3], h) || h < 0) return ParseError::BadValue;
    if (h > 1440) h = 1440;
    out.holdMin = uint16_t(nearbyintf(h));
  }

  switch (dev) {
    case Device::Fan: {
      if (eq(v, "ON") || eq(v, "TRUE")) { out.fanPct = 100; return ParseError::None; }
      if (eq(v, "OFF") || eq(v, "FALSE")) { out.fanPct = 0; return ParseError::None; }
      float f;
      if (!parseNumber(v, f)) return ParseError::BadValue;
      if (f < 0) f = 0;
      if (f > 100) f = 100;
      out.fanPct = uint8_t(nearbyintf(f));   // round-half-even, like Python's round()
      return ParseError::None;
    }
    case Device::Led: {
      if (eq(v, "OFF") || eq(v, "0") || eq(v, "FALSE")) { out.rgb = 0x000000; return ParseError::None; }
      if (eq(v, "ON") || eq(v, "1") || eq(v, "TRUE")) { out.rgb = 0xFFFFFF; return ParseError::None; }
      const char* hex = v[0] == '#' ? v + 1 : v;
      if (!isHex6(hex)) return ParseError::BadValue;
      out.rgb = uint32_t(strtoul(hex, nullptr, 16));
      return ParseError::None;
    }
    case Device::Relay: {
      if (eq(v, "ON") || eq(v, "1") || eq(v, "TRUE")) { out.relayOn = true; return ParseError::None; }
      if (eq(v, "OFF") || eq(v, "0") || eq(v, "FALSE")) { out.relayOn = false; return ParseError::None; }
      return ParseError::BadValue;
    }
  }
  return ParseError::BadValue;
}

size_t formatValue(const Command& c, char* buf, size_t n) {
  int w = 0;
  switch (c.device) {
    case Device::Fan: w = snprintf(buf, n, "%u", unsigned(c.fanPct)); break;
    case Device::Led: w = snprintf(buf, n, "%06lX", (unsigned long)(c.rgb & 0xFFFFFF)); break;
    case Device::Relay: w = snprintf(buf, n, "%u", c.relayOn ? 1u : 0u); break;
  }
  return finish(buf, n, w);
}

size_t formatAck(char* buf, size_t n, Device dev, const char* id, bool ok, const char* value,
                 Actor actor, const char* reason) {
  if (!buf || !n) return 0;
  const char* safeId = (id && *id) ? id : "-";
  if (strchr(safeId, ':') || !value || strchr(value, ':') || (reason && strchr(reason, ':'))) {
    buf[0] = '\0';
    return 0;
  }
  int w = (reason && *reason)
              ? snprintf(buf, n, "%s:%s:%d:%s:%c:%s", deviceName(dev), safeId, ok ? 1 : 0, value,
                         actorCode(actor), reason)
              : snprintf(buf, n, "%s:%s:%d:%s:%c", deviceName(dev), safeId, ok ? 1 : 0, value,
                         actorCode(actor));
  return finish(buf, n, w);
}

size_t formatEvent(char* buf, size_t n, const char* type, const char* data) {
  if (!buf || !n) return 0;
  if (!type || !*type || strchr(type, ':')) { buf[0] = '\0'; return 0; }
  int w = (data && *data) ? snprintf(buf, n, "%s:%s", type, data) : snprintf(buf, n, "%s", type);
  return finish(buf, n, w);
}

size_t formatText(char* buf, size_t n, const char* text) {
  if (!buf || !n) return 0;
  int w = snprintf(buf, n, "%s", text ? text : "");
  return finish(buf, n, w);
}

bool feedSafe(const char* text) { return text && safeForFeed(text, kMaxValue + 1); }

// ---- Telemetry ---------------------------------------------------------------------------
void Aggregator::add(const Sample& s) {
  ++n_;
  if (!isnan(s.temp)) { t_ += s.temp; ++nt_; }
  if (!isnan(s.humi)) { h_ += s.humi; ++nh_; }
  if (!isnan(s.light)) { l_ += s.light; ++nl_; }
  if (s.presenceValid) { ++np_; presence_ = presence_ || s.presence; }
}

bool Aggregator::lightMean(float& out) const {
  if (!nl_) return false;
  out = float(l_ / nl_);
  return true;
}

bool Aggregator::presence(bool& out) const {
  if (!np_) return false;
  out = presence_;
  return true;
}

bool Aggregator::mean(Sample& out) const {
  if (!nt_ || !nh_) return false;
  out.temp = float(t_ / nt_);
  out.humi = float(h_ / nh_);
  out.light = nl_ ? float(l_ / nl_) : NAN;
  out.presence = presence_;
  return true;
}

void Aggregator::reset() { *this = Aggregator(); }

static long clampRound(float v, long lo, long hi) {
  if (isnan(v)) return lo;
  long r = lroundf(v);
  return r < lo ? lo : (r > hi ? hi : r);
}

Buffered pack(uint32_t epoch, const Sample& s) {
  Buffered b;
  b.epoch = epoch;
  b.temp_c100 = int16_t(clampRound(s.temp * 100.0f, -32768, 32767));
  b.humi_10 = uint16_t(clampRound(s.humi * 10.0f, 0, 1000));
  b.light = uint16_t(clampRound(s.light, 0, 65535));
  b.presence = s.presence ? 1 : 0;
  return b;
}

size_t formatBuffered(char* buf, size_t n, const Buffered& b) {
  // Integer formatting: no dependence on printf float support on the MCU.
  int t = b.temp_c100;
  const char* sign = t < 0 ? "-" : "";
  unsigned ta = unsigned(t < 0 ? -t : t);
  int w = snprintf(buf, n, "B:%lu:%s%u.%02u:%u.%u:%u:%u", (unsigned long)b.epoch, sign, ta / 100,
                   ta % 100, unsigned(b.humi_10 / 10), unsigned(b.humi_10 % 10), unsigned(b.light),
                   unsigned(b.presence));
  return finish(buf, n, w);
}

// ---- Rate limiting -----------------------------------------------------------------------
TokenBucket::TokenBucket(float perMinute, float burst)
    : ratePerMs_(perMinute / 60000.0f), cap_(burst), tokens_(burst) {}

void TokenBucket::refill(uint32_t nowMs) {
  if (!started_) { last_ = nowMs; started_ = true; return; }
  uint32_t elapsed = nowMs - last_;   // unsigned subtraction survives the millis() wrap
  last_ = nowMs;
  tokens_ += float(elapsed) * ratePerMs_;
  if (tokens_ > cap_) tokens_ = cap_;
}

bool TokenBucket::tryAcquire(uint32_t nowMs, float reserve) {
  refill(nowMs);
  if (paused_) {
    if (int32_t(nowMs - pausedUntil_) < 0) return false;
    paused_ = false;
  }
  if (tokens_ < 1.0f + reserve) return false;
  tokens_ -= 1.0f;
  return true;
}

void TokenBucket::pause(uint32_t nowMs, uint32_t ms) {
  refill(nowMs);
  paused_ = true;
  pausedUntil_ = nowMs + ms;
  tokens_ = 0;
}

bool RecentIds::seenOrAdd(const char* id) {
  if (!id || !*id) return false;
  for (auto& s : ids_) if (strcmp(s, id) == 0) return true;
  strncpy(ids_[next_], id, kIdLen);
  ids_[next_][kIdLen] = '\0';
  next_ = uint8_t((next_ + 1) % 8);
  return false;
}

}  // namespace cloud

// =====================================================================================
// Part 2 — the task
// =====================================================================================
using namespace cloud;

QueueHandle_t qCloudCommands = nullptr;

namespace {

// AdafruitIO::run() is unsafe in a FreeRTOS task: when WiFi is down it blocks up to 60 s, and
// when WiFi is up but Adafruit IO is unreachable it busy-spins
//     while (mqttStatus(fail_fast) != AIO_CONNECTED && millis() - start < 60000) {}
// because mqttStatus() returns immediately between its once-per-60-s reconnect attempts.
// That starves other tasks on this core and can trip the task watchdog. So we never call
// run(); service() does the same work (connect, read packets, keep-alive) without blocking.
class YoloHomeIO : public AdafruitIO_WiFi {
 public:
  YoloHomeIO(const char* user, const char* key, const char* ssid, const char* pass)
      : AdafruitIO_WiFi(user, key, ssid, pass) {}

  aio_status_t service(uint16_t readMs) {
    if (networkStatus() != AIO_NET_CONNECTED) return AIO_NET_DISCONNECTED;
    // fail_fast = true: never delay(60 s) when throttled. The library itself limits
    // reconnect attempts to one per 60 s, so this is cheap while disconnected.
    aio_status_t m = mqttStatus(true);
    if (m != AIO_CONNECTED) return m;
    _mqtt->processPackets(readMs);
    if (uint32_t(millis() - _last_ping) > AIO_PING_INTERVAL) {
      _mqtt->ping();
      _last_ping = millis();
    }
    return AIO_CONNECTED;
  }
};

YoloHomeIO io(AIO_USERNAME, AIO_KEY, WIFI_SSID, WIFI_PASSWORD);

enum class OutKind : uint8_t { Ack, Event, Mode, FanState };
struct OutMsg {
  OutKind kind;
  char text[kMaxValue + 1];
};
enum class Pub : uint8_t { Ok, Rate, Failed };

QueueHandle_t qSamples = nullptr;   // sensor task -> here
QueueHandle_t qOut = nullptr;       // control logic -> here

AdafruitIO_Feed *fTemp, *fHumi, *fLight, *fPresence, *fFan, *fLed, *fAck, *fEvent, *fMode,
    *fFanState;

TokenBucket bucket(CLOUD_RATE_PER_MIN, CLOUD_RATE_BURST);
Aggregator aggFast, aggSlow, aggMinute;
Ring<Buffered, CLOUD_BACKLOG_MAX> backlog;
Ring<OutMsg, 8> pendingOut;          // ACKs/events that could not be sent while offline
char pendingMode[kMaxValue + 1] = "";
char pendingFanState[kMaxValue + 1] = "";
RecentIds recent;
CloudStats stats = {};

OutMsg holding;                      // outbox item waiting for a rate-limit token
bool haveHolding = false;
bool up = false, everUp = false, timeStarted = false, minuteDirty = false;
uint32_t syncUntil = 0, nextFast = 0, nextSlow = 0, nextMinute = 0, wifiDownSince = 0,
         lastWifiKick = 0;

uint32_t nowEpoch() {
  time_t t = time(nullptr);
  return t > 1700000000 ? uint32_t(t) : 0;   // 0 = clock never synced; backend uses arrival time
}

AdafruitIO_Feed* feedFor(OutKind k) {
  switch (k) {
    case OutKind::Ack: return fAck;
    case OutKind::Event: return fEvent;
    case OutKind::Mode: return fMode;
    case OutKind::FanState: return fFanState;
  }
  return nullptr;
}

Pub publish(AdafruitIO_Feed* f, const char* text, float reserve) {
  if (!f || !text || !*text) return Pub::Failed;
  if (!bucket.tryAcquire(millis(), reserve)) { ++stats.rateDropped; return Pub::Rate; }
  char buf[kMaxValue + 1];                 // save() takes a non-const char*
  strncpy(buf, text, kMaxValue);
  buf[kMaxValue] = '\0';
  if (!f->save(buf)) { ++stats.publishFailed; return Pub::Failed; }
  ++stats.published;
  return Pub::Ok;
}

bool enqueueOut(OutKind kind, const char* text) {
  if (!qOut || !text || !*text) return false;
  OutMsg m;
  m.kind = kind;
  strncpy(m.text, text, kMaxValue);
  m.text[kMaxValue] = '\0';
  return xQueueSend(qOut, &m, 0) == pdTRUE;
}

// Offline: keep the latest mode/fan state, and the most recent ACKs/events.
void stash(const OutMsg& m) {
  if (m.kind == OutKind::Mode) strncpy(pendingMode, m.text, sizeof pendingMode);
  else if (m.kind == OutKind::FanState) strncpy(pendingFanState, m.text, sizeof pendingFanState);
  else pendingOut.push(m);
}

// ---- inbound commands (called from processPackets(), i.e. on this task) ------------------
void handleCommand(Device dev, AdafruitIO_Data* d) {
  ++stats.commandsIn;
  const char* raw = d ? d->value() : nullptr;
  bool isSync = int32_t(millis() - syncUntil) < 0;
  Command c;
  ParseError e = parseCommand(dev, raw, isSync, c);
  char ack[kMaxValue + 1];
  if (e != ParseError::None) {                     // answer invalid commands, like the gateway
    ++stats.commandsRejected;
    if (formatAck(ack, sizeof ack, dev, c.id, false, "?", c.actor, parseErrorName(e)))
      enqueueOut(OutKind::Ack, ack);
    return;
  }
  if (recent.seenOrAdd(c.id)) { ++stats.duplicates; return; }
  CloudCommandMsg m;
  m.cmd = c;
  m.receivedMs = millis();
  if (xQueueSend(qCloudCommands, &m, 0) != pdTRUE) {   // control logic not keeping up
    ++stats.commandsRejected;
    char val[12];
    formatValue(c, val, sizeof val);
    if (formatAck(ack, sizeof ack, dev, c.id, false, val, c.actor, "BUSY"))
      enqueueOut(OutKind::Ack, ack);
  }
  // Accepted commands are ACKed by control logic after arbitration (lockdown, safety).
}
void onFan(AdafruitIO_Data* d) { handleCommand(Device::Fan, d); }
void onLed(AdafruitIO_Data* d) { handleCommand(Device::Led, d); }

// ---- link state ----------------------------------------------------------------------------
void linkChanged(bool nowUp, uint32_t now) {
  up = nowUp;
  if (up) {
    if (gSystemEvents) xEventGroupSetBits(gSystemEvents, EVT_CLOUD_UP);
    if (!timeStarted) {                    // UTC epoch for backlog timestamps
      configTime(0, 0, "pool.ntp.org", "time.google.com");
      timeStarted = true;
    }
    if (everUp) ++stats.reconnects;
    everUp = true;
    // Ask Adafruit for the last commanded values. Whatever arrives in the next few seconds
    // is a restore (actor SYNC): applied, but it must not start a Manual Lockdown.
    syncUntil = now + CLOUD_SYNC_WINDOW_MS;
    if (fFan) fFan->get();
    if (fLed) fLed->get();
  } else {
    if (gSystemEvents) xEventGroupClearBits(gSystemEvents, EVT_CLOUD_UP);
  }
}

// ESP32 WiFi reconnects by itself; nudge it if it has been down for a while.
void kickWifi(uint32_t now) {
  if (WiFi.status() == WL_CONNECTED) { wifiDownSince = 0; return; }
  if (!wifiDownSince) wifiDownSince = now;
  if (now - wifiDownSince > CLOUD_WIFI_KICK_MS && now - lastWifiKick > CLOUD_WIFI_KICK_MS) {
    WiFi.reconnect();
    lastWifiKick = now;
  }
}

// ---- outbound ------------------------------------------------------------------------------
void serviceOutbox() {
  // While anything stashed offline is still unsent, fold fresh items into the stash first,
  // so a newer mode / fan state replaces a stale one instead of both being published
  // (otherwise "OFFLINE_FAILSAFE" would appear on the dashboard right after reconnecting).
  if (pendingOut.size() || pendingFanState[0] || pendingMode[0]) {
    OutMsg m;
    while (xQueueReceive(qOut, &m, 0) == pdTRUE) stash(m);
  }
  // Stashed ACKs/events first (in order), then latest fan state and mode, then fresh items.
  // All high priority (reserve 0).
  for (int i = 0; i < 4; ++i) {
    if (!haveHolding) {
      if (pendingOut.front(holding)) { pendingOut.pop(); haveHolding = true; }
      else if (pendingFanState[0]) {
        holding.kind = OutKind::FanState;
        strncpy(holding.text, pendingFanState, sizeof holding.text);
        pendingFanState[0] = '\0';
        haveHolding = true;
      } else if (pendingMode[0]) {
        holding.kind = OutKind::Mode;
        strncpy(holding.text, pendingMode, sizeof holding.text);
        pendingMode[0] = '\0';
        haveHolding = true;
      } else if (xQueueReceive(qOut, &holding, 0) == pdTRUE) {
        haveHolding = true;
      } else {
        return;
      }
    }
    Pub r = publish(feedFor(holding.kind), holding.text, 0);
    if (r == Pub::Rate) return;                      // keep it, retry next step
    if (r == Pub::Failed) stash(holding);            // connection broke mid-publish
    haveHolding = false;
  }
}

void stashOutbox() {
  if (haveHolding) { stash(holding); haveHolding = false; }
  OutMsg m;
  while (xQueueReceive(qOut, &m, 0) == pdTRUE) stash(m);
}

bool publishNumber(AdafruitIO_Feed* f, float v, const char* fmt, float reserve) {
  if (v != v) return false;                          // NaN: sensor read failed
  char buf[16];
  snprintf(buf, sizeof buf, fmt, double(v));
  return publish(f, buf, reserve) == Pub::Ok;
}

void drainSamples() {
  Sample s;
  while (xQueueReceive(qSamples, &s, 0) == pdTRUE) {
    aggFast.add(s);
    aggSlow.add(s);
    aggMinute.add(s);
  }
}

bool due(uint32_t now, uint32_t& next, uint32_t period) {
  if (int32_t(now - next) < 0) return false;
  next += period;
  if (int32_t(now - next) >= 0) next = now + period;  // fell behind: don't burst to catch up
  return true;
}

void telemetry(uint32_t now) {
  Sample m;
  if (due(now, nextFast, CLOUD_FAST_PERIOD_MS)) {    // temperature + humidity
    bool sent = false;
    if (aggFast.mean(m) && up) {
      bool t = publishNumber(fTemp, m.temp, "%.2f", CLOUD_TELEMETRY_RESERVE);
      bool h = publishNumber(fHumi, m.humi, "%.1f", CLOUD_TELEMETRY_RESERVE);
      sent = t && h;
    }
    if (aggFast.count() && !sent) minuteDirty = true; // this minute needs a backlog entry
    aggFast.reset();
  }
  if (due(now, nextSlow, CLOUD_SLOW_PERIOD_MS)) {    // light + presence, each on its own:
    float light;                                     // a failed DHT20 must not silence them
    bool motion;
    if (up && aggSlow.lightMean(light)) publishNumber(fLight, light, "%.0f", CLOUD_TELEMETRY_RESERVE);
    if (up && aggSlow.presence(motion)) publish(fPresence, motion ? "1" : "0", CLOUD_TELEMETRY_RESERVE);
    aggSlow.reset();
  }
  if (due(now, nextMinute, 60000)) {
    if (minuteDirty && aggMinute.mean(m)) backlog.push(pack(nowEpoch(), m));
    aggMinute.reset();
    minuteDirty = false;
  }
}

void replayBacklog() {
  Buffered b;
  if (!backlog.front(b)) return;
  char txt[kMaxValue + 1];
  if (!formatBuffered(txt, sizeof txt, b)) { backlog.pop(); return; }
  if (publish(fEvent, txt, CLOUD_REPLAY_RESERVE) == Pub::Ok) {   // lowest priority
    backlog.pop();
    ++stats.backlogSent;
  }
}

}  // namespace

// ---- public API ------------------------------------------------------------------------------
void cloud_init() {
  if (!qCloudCommands) qCloudCommands = xQueueCreate(8, sizeof(CloudCommandMsg));
  if (!qSamples) qSamples = xQueueCreate(16, sizeof(Sample));
  if (!qOut) qOut = xQueueCreate(16, sizeof(OutMsg));
}

bool cloud_post_sample(const Sample& s) {
  return qSamples && xQueueSend(qSamples, &s, 0) == pdTRUE;
}

bool cloud_post_ack(Device dev, const char* id, bool ok, const char* value, Actor actor,
                    const char* reason) {
  char buf[kMaxValue + 1];
  return formatAck(buf, sizeof buf, dev, id, ok, value, actor, reason) &&
         enqueueOut(OutKind::Ack, buf);
}

bool cloud_post_event(const char* type, const char* data) {
  char buf[kMaxValue + 1];
  return formatEvent(buf, sizeof buf, type, data) && enqueueOut(OutKind::Event, buf);
}

bool cloud_post_mode(const char* modeText) {
  char buf[kMaxValue + 1];
  return formatText(buf, sizeof buf, modeText) && enqueueOut(OutKind::Mode, buf);
}

bool cloud_post_fan_state(uint8_t pct) {
  char buf[8];
  snprintf(buf, sizeof buf, "%u", unsigned(pct > 100 ? 100 : pct));
  return enqueueOut(OutKind::FanState, buf);
}

CloudStats cloud_stats() {                // counters are read without a lock: approximate
  CloudStats s = stats;
  s.backlog = backlog.size();
  s.backlogDropped = backlog.dropped();
  return s;
}

void cloud_setup() {
  cloud_init();
  fTemp = io.feed(FEED_TEMPERATURE);
  fHumi = io.feed(FEED_HUMIDITY);
  fLight = io.feed(FEED_LIGHT);
  fPresence = io.feed(FEED_PRESENCE);
  fFan = io.feed(FEED_FAN);
  fLed = io.feed(FEED_LED);
  fAck = io.feed(FEED_ACK);
  fEvent = io.feed(FEED_EVENT);
  fMode = io.feed(FEED_MODE);
  fFanState = io.feed(FEED_FAN_STATE);
  fFan->onMessage(onFan);
  fLed->onMessage(onLed);
  io.connect();                            // only starts WiFi; service() completes the link
  uint32_t now = millis();
  nextFast = now + CLOUD_FAST_PERIOD_MS;
  nextSlow = now + CLOUD_SLOW_PERIOD_MS + CLOUD_SLOW_OFFSET_MS;
  nextMinute = now + 60000;
}

void cloud_step() {
  uint32_t now = millis();
  kickWifi(now);
  bool nowUp = io.service(CLOUD_READ_MS) == AIO_CONNECTED;
  if (nowUp != up) linkChanged(nowUp, now);
  drainSamples();
  if (up) serviceOutbox();
  else stashOutbox();
  telemetry(now);
  if (up) replayBacklog();
}

void task_adafruitio(void* parameter) {
  (void)parameter;
  cloud_setup();
  for (;;) {
    cloud_step();
    vTaskDelay(pdMS_TO_TICKS(CLOUD_LOOP_MS));
  }
}