// Host unit tests for the message formats and helpers (Part 1 of adafruitio_task). See run_tests.sh
#include <math.h>
#include <stdio.h>
#include <string.h>

#include <fstream>
#include <sstream>
#include <string>
#include <vector>

#include "adafruitio_task.h"

using namespace cloud;
EventGroupHandle_t gSystemEvents = nullptr;   // required by the task source
static int failures = 0, checks = 0;
#define CHECK(cond, ...)                                                   \
  do {                                                                     \
    ++checks;                                                              \
    if (!(cond)) { ++failures; printf("FAIL %s:%d  ", __FILE__, __LINE__); \
                   printf(__VA_ARGS__); printf("\n"); }                    \
  } while (0)

static std::vector<std::string> split(const std::string& s) {
  std::vector<std::string> out;
  std::string cur;
  for (char c : s) { if (c == '|') { out.push_back(cur); cur.clear(); } else cur += c; }
  out.push_back(cur);
  return out;
}

static Device dev(const std::string& s) {
  return s == "fan" ? Device::Fan : s == "led" ? Device::Led : Device::Relay;
}
static Actor actor(char c) {
  switch (c) { case 'V': return Actor::Voice; case 'S': return Actor::Schedule;
               case 'Y': return Actor::Sync; case 'A': return Actor::Ai;
               case 'X': return Actor::System; default: return Actor::User; }
}

static void contractVectors(const char* path) {
  std::ifstream f(path);
  CHECK(f.good(), "cannot open %s", path);
  std::string line;
  int cmd = 0, ack = 0, buf = 0;
  while (std::getline(f, line)) {
    if (line.empty() || line[0] == '#') continue;
    auto v = split(line);
    if (v[0] == "CMD") {
      ++cmd;
      Command c;
      ParseError e = parseCommand(dev(v[1]), v[3].c_str(), v[2] == "1", c);
      CHECK(std::string(parseErrorName(e)) == v[4], "[%s] status %s, want %s", line.c_str(),
            parseErrorName(e), v[4].c_str());
      if (e == ParseError::None) {
        char val[16];
        formatValue(c, val, sizeof val);
        CHECK(v[5] == val, "[%s] value %s, want %s", line.c_str(), val, v[5].c_str());
        CHECK(c.holdMin == atoi(v[8].c_str()), "[%s] hold %u", line.c_str(), c.holdMin);
      }
      CHECK(v[6] == c.id, "[%s] id '%s', want '%s'", line.c_str(), c.id, v[6].c_str());
      CHECK(actorCode(c.actor) == v[7][0], "[%s] actor %c, want %c", line.c_str(),
            actorCode(c.actor), v[7][0]);
    } else if (v[0] == "ACK") {
      ++ack;
      char out[64];
      size_t n = formatAck(out, sizeof out, dev(v[1]), v[2].c_str(), v[3] == "1", v[4].c_str(),
                           actor(v[5][0]), v[6].empty() ? nullptr : v[6].c_str());
      CHECK(n && v[7] == out, "[%s] got '%s'", line.c_str(), out);
    } else if (v[0] == "BUF") {
      ++buf;
      Buffered b{uint32_t(strtoul(v[1].c_str(), nullptr, 10)), int16_t(atoi(v[2].c_str())),
                 uint16_t(atoi(v[3].c_str())), uint16_t(atoi(v[4].c_str())),
                 uint8_t(atoi(v[5].c_str()))};
      char out[64];
      size_t n = formatBuffered(out, sizeof out, b);
      CHECK(n && v[6] == out, "[%s] got '%s'", line.c_str(), out);
    }
  }
  CHECK(cmd >= 20 && ack >= 5 && buf >= 3, "too few vectors: %d %d %d", cmd, ack, buf);
  printf("  contract vectors: %d CMD, %d ACK, %d BUF\n", cmd, ack, buf);
}

static void lengthAndCharacterRules() {
  // 45+ characters would overflow the library's 45-byte buffer: must be refused.
  std::string longPayload(45, '7');
  Command c;
  CHECK(parseCommand(Device::Fan, longPayload.c_str(), false, c) == ParseError::TooLong, "long");
  CHECK(parseCommand(Device::Fan, nullptr, false, c) == ParseError::Empty, "null");

  char out[64];
  CHECK(formatAck(out, sizeof out, Device::Fan, "a,b", true, "70", Actor::User) == 0, "comma in id");
  CHECK(formatEvent(out, sizeof out, "X", "has\"quote") == 0, "quote");
  CHECK(formatEvent(out, sizeof out, "SAFETY", "46.2") && strcmp(out, "SAFETY:46.2") == 0, "event");
  std::string text44(44, 'a'), text45(45, 'a');
  CHECK(formatText(out, sizeof out, text44.c_str()) == 44, "44 fits");
  CHECK(formatText(out, sizeof out, text45.c_str()) == 0, "45 refused");
  CHECK(formatText(out, sizeof out, "MANUAL_LOCKDOWN until 15:12") > 0, "mode text");
  char tiny[4];
  CHECK(formatAck(tiny, sizeof tiny, Device::Fan, "a1b2c3d4", true, "70", Actor::User) == 0 && tiny[0] == 0,
        "truncation is refused, not silently cut");
}

static void tokenBucket() {
  // Worst case in any 60 s window must be burst + rate.
  TokenBucket b(20, 5);
  int maxWindow = 0;
  std::vector<uint32_t> sent;
  for (uint32_t t = 0; t < 600000; t += 50) {
    if (b.tryAcquire(t)) sent.push_back(t);
    int inWindow = 0;
    for (uint32_t s : sent) if (t - s < 60000) ++inWindow;
    if (inWindow > maxWindow) maxWindow = inWindow;
  }
  CHECK(maxWindow <= 25, "max %d in 60 s, want <= 25", maxWindow);
  CHECK(maxWindow >= 24, "suspiciously low: %d", maxWindow);

  TokenBucket r(20, 5);       // reserve keeps tokens for high priority
  int low = 0;
  while (r.tryAcquire(0, 3)) ++low;
  CHECK(low == 2, "low priority took %d, want 2 (5 - reserve 3)", low);
  CHECK(r.tryAcquire(0, 0), "high priority still has tokens");

  TokenBucket p(20, 5);       // pause, and the millis() wrap-around
  p.tryAcquire(0xFFFFFF00u);
  p.pause(0xFFFFFF00u, 1000);
  CHECK(!p.tryAcquire(0xFFFFFF00u + 500), "paused");
  CHECK(p.tryAcquire(0xFFFFFF00u + 4000), "resumes after wrap (0x%x)", 0xFFFFFF00u + 4000);
}

static void aggregatorAndRing() {
  Aggregator a;
  a.add({30, 70, 40, false});
  a.add({NAN, 72, NAN, true});         // a failed temperature read must not poison the mean
  a.add({32, NAN, 60, false});
  Sample m;
  CHECK(a.mean(m), "mean");
  CHECK(fabsf(m.temp - 31) < 1e-4 && fabsf(m.humi - 71) < 1e-4 && fabsf(m.light - 50) < 1e-4,
        "mean %.2f %.2f %.2f", m.temp, m.humi, m.light);
  CHECK(m.presence, "any motion in the window counts");
  a.reset();
  CHECK(!a.mean(m) && a.count() == 0, "reset");

  Ring<int, 3> r;
  for (int i = 1; i <= 5; ++i) r.push(i);
  int x;
  CHECK(r.size() == 3 && r.dropped() == 2, "size %zu dropped %u", r.size(), r.dropped());
  CHECK(r.front(x) && x == 3, "oldest dropped first, front=%d", x);

  Buffered b = pack(1760000000, {30.524f, 71.25f, 45.4f, true});
  char out[64];
  formatBuffered(out, sizeof out, b);
  CHECK(strcmp(out, "B:1760000000:30.52:71.3:45:1") == 0 || strcmp(out, "B:1760000000:30.52:71.2:45:1") == 0,
        "pack/format: %s", out);
}

static void recentIds() {
  RecentIds r;
  CHECK(!r.seenOrAdd("a1b2c3d4") && r.seenOrAdd("a1b2c3d4"), "duplicate detected");
  CHECK(!r.seenOrAdd("") && !r.seenOrAdd(""), "empty ids never duplicates");
  for (int i = 0; i < 8; ++i) { char id[16]; snprintf(id, sizeof id, "%08u", unsigned(i)); r.seenOrAdd(id); }
  CHECK(!r.seenOrAdd("a1b2c3d4"), "evicted after 8 newer ids");
}

int main(int argc, char** argv) {
  contractVectors(argc > 1 ? argv[1] : "../../../contract/cloud_vectors.txt");
  lengthAndCharacterRules();
  tokenBucket();
  aggregatorAndRing();
  recentIds();
  printf("codec: %d checks, %d failures\n", checks, failures);
  return failures ? 1 : 0;
}
