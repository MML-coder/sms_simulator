#!/usr/bin/env bash
# Benchmarks for the SMS simulation. Prints one line per run: the final
# progress line plus peak RSS. Results and findings: performance/README.md.
#
# Usage: performance/bench.sh [python]     (default: .venv/bin/python)
#        SECTIONS=E performance/bench.sh   runs only the sections listed (default: ABCDE)
set -euo pipefail

PYTHON=${1:-.venv/bin/python}
SECTIONS=${SECTIONS:-ABCDE}
cd "$(dirname "$0")/.."
TIME_OUT=$(mktemp)
trap 'rm -f "$TIME_OUT"' EXIT

# Peak RSS in MB: macOS /usr/bin/time -l reports bytes, GNU time -f %M reports KB.
if [[ $(uname) == Darwin ]]; then
  TIME=(/usr/bin/time -l)
  rss_mb() { awk '/maximum resident/ {printf "%.1f", $1 / 1048576}' "$TIME_OUT"; }
else
  TIME=(/usr/bin/time -f "%M")
  rss_mb() { awk 'END {printf "%.1f", $1 / 1024}' "$TIME_OUT"; }
fi

# A monitor interval longer than any run keeps progress printing out of the measurement.
run() {
  local final
  final=$("${TIME[@]}" "$PYTHON" -m sms_sim --monitor-interval 1000 --seed 1 "$@" 2>"$TIME_OUT" | tail -1)
  echo "$final rss=$(rss_mb)MB"
}

echo "# $("$PYTHON" -V), $(uname -sm)"

if [[ $SECTIONS == *A* ]]; then
echo "## A: throughput vs senders, mean send time 10ms, 200 messages per sender"
for s in 1 10 100 1000 10000; do
  echo -n "senders=$s expected=$((s * 100))/s "
  run --senders "$s" --messages $((s * 200)) --mean-send-time 0.01
done
fi

if [[ $SECTIONS == *B* ]]; then
echo "## B: overhead ceiling, no send delay, 1M messages, 3 runs each"
for s in 1 10 100 1000 10000; do
  for r in 1 2 3; do
    echo -n "senders=$s run=$r "
    run --senders "$s" --messages 1000000 --mean-send-time 0
  done
done
fi

if [[ $SECTIONS == *C* ]]; then
echo "## C: memory vs messages, no send delay, 100 senders"
for n in 10000 100000 1000000 5000000; do
  echo -n "messages=$n "
  run --senders 100 --messages "$n" --mean-send-time 0
done
fi

if [[ $SECTIONS == *D* ]]; then
echo "## D: profile at the ceiling, 1000 senders, 1M messages, top functions by own time"
"$PYTHON" -m cProfile -s tottime -m sms_sim --monitor-interval 1000 --seed 1 \
  --senders 1000 --messages 1000000 --mean-send-time 0 | sed -n '1,25p'
fi

# The default queue holds 2 x senders. Sizes below are 0.01x to 100x the 100 senders.
if [[ $SECTIONS == *E* ]]; then
echo "## E: queue size, 100 senders"
for q in 1 10 50 100 200 1000 10000; do
  echo -n "queue=$q delay=10ms "
  run --senders 100 --messages 20000 --mean-send-time 0.01 --queue-size "$q"
done
for q in 1 10 50 100 200 1000 10000; do
  echo -n "queue=$q delay=0 "
  run --senders 100 --messages 1000000 --mean-send-time 0 --queue-size "$q"
done
fi
