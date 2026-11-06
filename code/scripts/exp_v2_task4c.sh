#!/usr/bin/env bash
# TASK 4(c): Events per wait and waits per request with new C load generator
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

ulimit -n 65536
python3 scripts/task4_events_per_wait.py
