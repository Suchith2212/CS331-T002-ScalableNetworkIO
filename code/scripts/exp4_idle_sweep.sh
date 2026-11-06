#!/usr/bin/env bash
# ============================================================================
# exp4_idle_sweep.sh - Experiment 4: Idle Connection Sweep & Crossover Search
# ============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CODE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$CODE_DIR"

ulimit -n 65536
mkdir -p results

python3 scripts/exp4_idle_sweep.py
