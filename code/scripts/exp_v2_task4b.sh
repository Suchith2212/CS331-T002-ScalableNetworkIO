#!/usr/bin/env bash
# TASK 4(b): Server CPU cost per request and context switches
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

ulimit -n 65536
python3 scripts/task4_cpu_per_req.py
