#!/usr/bin/env bash
# ============================================================================
# strace_check.sh - Measure System Calls Per Ping-Echo Request
# ============================================================================
# Runs 'strace -c -f -p <pid>' for 10 seconds under load for each server
# and prints syscalls per request.
# ============================================================================

set -e
ulimit -n 65536

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CODE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$CODE_DIR"

SERVERS=(
    "server_blocking"
    "server_select"
    "server_poll"
    "epoll_lt_server"
    "epoll_et_server"
    "io_uring_opt_server"
)

PORT=8085
DURATION=10
CONNS=100

mkdir -p results/strace_logs

echo "======================================================================"
echo " Syscall Efficiency Profiling (10s under 100 concurrent connections)"
echo " Server Core: 0 | Client Load Cores: 1-15"
echo "======================================================================"
printf "%-22s | %-15s | %-15s | %-18s\n" "Server" "Total Syscalls" "Total Requests" "Syscalls / Request"
echo "----------------------------------------------------------------------"

for server in "${SERVERS[@]}"; do
    bin_path="bin/$server"
    if [ ! -f "$bin_path" ]; then
        continue
    fi

    # Clean any dangling sockets on PORT
    fuser -k -n tcp $PORT >/dev/null 2>&1 || true
    sleep 0.2

    # Launch server pinned to Core 0
    taskset -c 0 "$bin_path" $PORT > /dev/null 2>&1 &
    SERVER_PID=$!
    sleep 0.5

    if ! kill -0 $SERVER_PID 2>/dev/null; then
        continue
    fi

    log_file="results/strace_logs/strace_${server}.log"
    rm -f "$log_file"

    # Start strace attached to server process using SIGINT timeout so it flushes summary
    sudo timeout -s INT ${DURATION} strace -c -f -p $SERVER_PID -o "$log_file" >/dev/null 2>&1 &
    STRACE_PID=$!

    # Run client load generator concurrently pinned to cores 1-15
    TOTAL_REQS=$(taskset -c 1-15 python3 scripts/load_worker.py $PORT $CONNS $DURATION 2>/dev/null || echo 0)

    # Wait for strace to detach and finish writing
    wait $STRACE_PID 2>/dev/null || true

    # Terminate server
    kill -TERM $SERVER_PID 2>/dev/null || true
    wait $SERVER_PID 2>/dev/null || true
    sleep 0.3

    # Extract total syscall count from bottom line of strace summary ($4 is calls in strace -c output)
    TOTAL_SYSCALLS=$(awk '/total$/ {print $4}' "$log_file" 2>/dev/null)
    if [ -z "$TOTAL_SYSCALLS" ]; then
        TOTAL_SYSCALLS=0
    fi

    if [ "$TOTAL_SYSCALLS" -gt 0 ] 2>/dev/null && [ "$TOTAL_REQS" -gt 0 ] 2>/dev/null; then
        RATIO=$(python3 -c "print(round($TOTAL_SYSCALLS / $TOTAL_REQS, 3))")
    else
        RATIO="N/A"
    fi

    printf "%-22s | %-15s | %-15s | %-18s\n" "$server" "$TOTAL_SYSCALLS" "$TOTAL_REQS" "$RATIO"
done

echo "======================================================================"
echo "Detailed strace logs saved to results/strace_logs/"
