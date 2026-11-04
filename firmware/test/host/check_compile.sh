#!/usr/bin/env bash
# Compiles every firmware source file on a PC (syntax and types only, warnings = errors)
# for both chips and both Arduino core generations. Catches mistakes before PlatformIO does.
set -uo pipefail
cd "$(dirname "$0")"
FW=../..
fail=0
for chip in CONFIG_IDF_TARGET_ESP32S3 CONFIG_IDF_TARGET_ESP32; do
  for core in 2 3; do
    for f in $(find $FW/src -name '*.cpp' | sort); do
      if ! g++ -std=c++14 -Wall -Wextra -Werror -fsyntax-only -D$chip -DESP_ARDUINO_VERSION_MAJOR=$core \
           -include compile_shims/shim_all.h -Icompile_shims -Istubs -I$FW/include "$f" 2>/tmp/cc_err.txt; then
        echo "FAIL $chip core $core: ${f#$FW/}"; head -12 /tmp/cc_err.txt; fail=1
      fi
    done
  done
done
[ $fail = 0 ] && echo "compile check: $(find $FW/src -name '*.cpp' | wc -l) files x 2 chips x 2 cores OK"
exit $fail
