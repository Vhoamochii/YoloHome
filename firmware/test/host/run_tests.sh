#!/usr/bin/env bash
# Host tests for the firmware cloud link. Needs only g++ (C++14). Run from anywhere.
set -euo pipefail
cd "$(dirname "$0")"
FW=../..
OUT=$(mktemp -d)
FLAGS="-std=c++14 -Wall -Wextra -Werror -O1 -g -fsanitize=address,undefined -fno-sanitize-recover=all"

g++ $FLAGS -Istubs -I$FW/include $FW/src/tasks/adafruitio_task.cpp stubs/sim.cpp test_cloud_codec.cpp -o $OUT/codec
VEC=../../../contract/cloud_vectors.txt; [ -f cloud_vectors.txt ] && VEC=cloud_vectors.txt
$OUT/codec $VEC

# The production task source, unmodified, against API-faithful stubs (stubs/ first on the path).
g++ $FLAGS -Istubs -I$FW/include $FW/src/tasks/adafruitio_task.cpp \
    stubs/sim.cpp test_task_sim.cpp -o $OUT/task
for s in steady commands restore outage wifi; do $OUT/task $s; done
# Bare-board demo on the Yolo Uno pin set, plus a syntax check on the Yolo:Bit pin set.
g++ $FLAGS -DBOARD_YOLO_UNO -Istubs -I$FW/include $FW/src/tasks/adafruitio_task.cpp \
    $FW/src/demo/bareboard_demo.cpp stubs/sim.cpp test_bareboard_sim.cpp -o $OUT/bareboard
$OUT/bareboard
g++ -std=c++14 -Wall -Wextra -Werror -fsyntax-only -Istubs -I$FW/include $FW/src/demo/bareboard_demo.cpp
# Control logic: safety, lockdown, schedule, AI policy, forecast, anomaly
g++ $FLAGS -Istubs -I$FW/include $FW/src/control.cpp test_control.cpp -o $OUT/control
$OUT/control
# Every firmware file compiles for both chips and both Arduino core generations
./check_compile.sh
echo "ALL HOST TESTS PASSED"
