#!/usr/bin/env bash
# ============================================================================
# run_bench.sh - Benchmark Hygiene Automation Suite
# ============================================================================
# - Pins server to Core 0 (taskset -c 0)
# - Pins load generator to Cores 1-15 (taskset -c 1-15)
# - Executes 5 trials per level, reporting MEDIAN throughput and p99 latency
# - Records VmRSS memory footprint
# - Sets ulimit -n 65536
# - Runs Scenario 1 (10 to 5,000 conns) and Scenario 2 (10,000 idle + 100 active)
# ============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CODE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$CODE_DIR"

# 1. Elevate file descriptor limit to 65,536
ulimit -n 65536

echo "======================================================================"
echo " Starting Benchmarking Suite with CPU Pinning & 5 Trials"
echo " OS Kernel: $(uname -r)"
echo " CPU Pinning: Server -> Core 0 | Client Load -> Cores 1-15"
echo " Active File Descriptor Limit: $(ulimit -n)"
echo "======================================================================"

mkdir -p results

# Run python benchmarking runner pinned to client cores 1-15
taskset -c 1-15 python3 scripts/bench_runner.py --scenario all

echo "======================================================================"
echo " Benchmarking Suite Completed Successfully!"
echo " Results stored in: results/bench_hygiene_summary.csv"
echo "                    results/bench_idle_scenario.csv"
echo "======================================================================"
