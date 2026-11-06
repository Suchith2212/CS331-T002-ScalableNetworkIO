#!/usr/bin/env bash
# Chain remaining Task 4c, 4d, and 6
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

ulimit -n 65536

echo "=== Running Task 4(c): Events per Wait ==="
python3 scripts/task4_events_per_wait.py

echo "=== Running Task 4(d): Idle Sweep ==="
python3 scripts/task4_idle_sweep.py

echo "=== Running Task 6: Memory Profiling ==="
python3 scripts/task6_memory.py

echo "=== ALL EXPERIMENTS COMPLETE ==="
