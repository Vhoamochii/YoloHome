#include <cstdio>
#include <cassert>
#include <cmath>
#include <limits>
#include "fire_engine.h"
int main(int argc, char**) {
  if (argc > 1) {
    float t, h;
    while (std::scanf("%f %f", &t, &h) == 2) std::printf("%.9g\n", double(tinyfire::infer(t, h)));
    return 0;
  }
  tinyfire::Engine e;
  auto r = e.update(33.74f, 51.034f);
  assert(r.valid && !r.alarm && r.score > 0.69f && r.score < 0.72f);
  r = e.update(38, 50);
  assert(!r.ml && !r.heat && !r.alarm);
  e.update(38, 50);
  r = e.update(38, 50);
  assert(r.ml && !r.heat && r.alarm); // ML alert below the separate 45 C guard.
  r = e.update(NAN, NAN);
  assert(!r.valid && r.alarm && r.ml);
  e.update(33, 50); e.update(33, 50);
  r = e.update(33, 50);
  assert(!r.ml && !r.alarm);
  assert(e.update(45, 50).heat);
  assert(e.update(44, 50).heat);
  assert(!e.update(43, 50).heat);
  assert(!e.update(20, 101).valid);
  assert(!e.update(std::numeric_limits<float>::infinity(), 20).valid);
  assert(std::isnan(tinyfire::infer(-41, 50)));
  for (int h = 0; h <= 100; h += 5) {
    float previous = -1;
    for (int t = -40; t <= 80; ++t) {
      float p = tinyfire::infer(float(t), float(h));
      assert(p >= 0 && p <= 1 && p >= previous);
      previous = p;
    }
  }
  assert(tinyfire::infer(34.486f,63.831f) > tinyfire::infer(33.74f,51.034f));
  std::puts("host_engine: temperature dominance, invalid samples, ML/heat hysteresis OK");
}
