#!/usr/bin/env bash
# TASK 3: Calibrate new C load generator against reference server
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

ulimit -n 65536
python3 scripts/task3_calibration.py
