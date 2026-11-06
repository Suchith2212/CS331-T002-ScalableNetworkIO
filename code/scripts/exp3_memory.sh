#!/usr/bin/env bash
# ============================================================================
# exp3_memory.sh - Experiment 3: VmRSS & VmData Memory Allocation Breakdown
# ============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CODE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$CODE_DIR"

ulimit -n 65536
mkdir -p results

python3 scripts/exp3_runner.py
