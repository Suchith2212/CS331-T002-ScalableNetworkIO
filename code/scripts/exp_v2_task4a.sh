#!/usr/bin/env bash
# TASK 4(a): Scenario 1 benchmark with the new C load generator
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

ulimit -n 65536
python3 scripts/task4_scenario1.py
