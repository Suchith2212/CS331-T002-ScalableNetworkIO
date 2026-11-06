#!/usr/bin/env bash
# TASK 1: Measure per-thread client CPU on old python client
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

ulimit -n 65536
python3 scripts/task1_bottleneck_check.py
