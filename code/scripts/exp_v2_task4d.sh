#!/usr/bin/env bash
# TASK 4(d): Idle sweep benchmark with new C load generator
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

ulimit -n 65536
python3 scripts/task4_idle_sweep.py
