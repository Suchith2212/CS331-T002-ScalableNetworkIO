#!/usr/bin/env bash
# ============================================================================
# exp2_cpu_per_req.sh - Experiment 2: CPU Cost per Request & Context Switches
# ============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CODE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$CODE_DIR"

ulimit -n 65536
mkdir -p results

python3 scripts/exp2_runner.py
