#!/usr/bin/env bash
# ============================================================================
# exp1_events_per_wait.sh - Experiment 1: Events per Wakeup & Waits per Request
# ============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CODE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$CODE_DIR"

ulimit -n 65536
mkdir -p results

# Ensure stats binaries exist
make stats

python3 scripts/exp1_runner.py
