#!/usr/bin/env bash
# TASK 6: Memory profiling including user-space and kernel socket buffers
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

ulimit -n 65536
python3 scripts/task6_memory.py
