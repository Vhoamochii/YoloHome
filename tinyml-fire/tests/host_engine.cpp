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
  auto r = e.update(28, 65);
  assert(r.valid && !r.alarm);
  r = e.update(50, 20);
  assert(r.heat && !r.ml && r.alarm); // Guard is immediate; ML still needs 3 samples.
  e.update(50, 20);
  r = e.update(50, 20);
  assert(r.ml && r.heat);
  r = e.update(NAN, NAN);
  assert(!r.valid && r.alarm && r.ml && r.heat); // Fault must not clear a latched alert.
  e.update(28, 65);
  e.update(28, 65);
  r = e.update(28, 65);
  assert(!r.alarm && !r.ml && !r.heat);
  assert(!e.update(20, 101).valid);
  assert(!e.update(std::numeric_limits<float>::infinity(), 20).valid);
  assert(std::isnan(tinyfire::infer(-41, 50)));
  assert(e.update(60, 70).heat); // Original model misses this case; independent guard catches heat.
  assert(e.update(44, 70).heat);
  assert(!e.update(43, 70).heat);
  std::puts("host_engine: OK");
}
