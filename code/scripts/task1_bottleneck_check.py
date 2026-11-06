#!/usr/bin/env python3
"""
TASK 1: Prove or disprove the client bottleneck on the OLD Python asyncio client.
Measures CPU per process/thread over a 10s steady-state window.
Records mpstat -P ALL 1 and per-thread utilization via /proc/<pid>/task/*/stat.
"""
import os
import sys
import time
import socket
import subprocess
import signal
import statistics
import csv
import re

PORT = 8089
SERVERS = ["server_poll", "epoll_lt_server", "io_uring_opt_server"]
CONNS = [100, 1000, 5000]
TRIALS = 5
STEADY_WINDOW_S = 10
WARMUP_S = 1.0

def is_port_open(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(('127.0.0.1', port)) == 0

def wait_for_server(port, timeout=3.0):
    start = time.time()
    while time.time() - start < timeout:
        if is_port_open(port):
            return True
        time.sleep(0.05)
    return False

def get_cpu0_ticks():
    """Read CPU 0 total and busy ticks from /proc/stat."""
    try:
        with open("/proc/stat", "r") as f:
            for line in f:
                if line.startswith("cpu0 "):
                    parts = [int(p) for p in line.split()[1:]]
                    user, nice, system, idle, iowait = parts[0], parts[1], parts[2], parts[3], parts[4]
                    irq = parts[5] if len(parts) > 5 else 0
                    softirq = parts[6] if len(parts) > 6 else 0
                    steal = parts[7] if len(parts) > 7 else 0
                    total = sum(parts)
                    busy = total - idle - iowait
                    return total, busy
    except Exception:
        pass
    return 0, 0

def get_thread_ticks(pid):
    """Read utime and stime for all threads of a process from /proc/<pid>/task/*/stat."""
    thread_ticks = {}
    task_dir = f"/proc/{pid}/task"
    if not os.path.exists(task_dir):
        return thread_ticks
    try:
        for tid in os.listdir(task_dir):
            stat_file = os.path.join(task_dir, tid, "stat")
            if os.path.exists(stat_file):
                with open(stat_file, "r") as f:
                    content = f.read()
                # Field 14 is utime, 15 is stime (after the comm field in parens)
                idx = content.rfind(')')
                if idx != -1:
                    rest = content[idx+2:].split()
                    utime = int(rest[11])
                    stime = int(rest[12])
                    thread_ticks[int(tid)] = utime + stime
    except Exception:
        pass
    return thread_ticks

def run_single_trial(server_name, num_conns):
    bin_path = os.path.join("bin", server_name)
    total_duration = int(WARMUP_S + STEADY_WINDOW_S + 2)

    # 1. Start server pinned to Core 0
    server_proc = subprocess.Popen(
        ["taskset", "-c", "0", bin_path, str(PORT)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    if not wait_for_server(PORT):
        server_proc.kill()
        return None, None

    # 2. Start old Python client pinned to Cores 1-15
    client_proc = subprocess.Popen(
        ["taskset", "-c", "1-15", "python3", "scripts/load_worker.py", str(PORT), str(num_conns), str(total_duration)],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True
    )

    # Allow warmup
    time.sleep(WARMUP_S)

    # Record initial ticks
    t0 = time.perf_counter()
    cpu0_tot0, cpu0_busy0 = get_cpu0_ticks()
    client_threads0 = get_thread_ticks(client_proc.pid)

    # Optional: run mpstat in background for logging
    mpstat_proc = subprocess.Popen(
        ["mpstat", "-P", "ALL", "1", str(STEADY_WINDOW_S)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    # Wait for the steady-state window
    time.sleep(STEADY_WINDOW_S)

    # Record end ticks
    t1 = time.perf_counter()
    cpu0_tot1, cpu0_busy1 = get_cpu0_ticks()
    client_threads1 = get_thread_ticks(client_proc.pid)
    try:
        mpstat_proc.wait(timeout=2.0)
    except Exception:
        mpstat_proc.kill()

    dt = t1 - t0
    clk_tck = os.sysconf(os.sysconf_names['SC_CLK_TCK'])

    # Compute Server Core 0 utilization
    tot_delta = cpu0_tot1 - cpu0_tot0
    busy_delta = cpu0_busy1 - cpu0_busy0
    server_core_util = (busy_delta / tot_delta * 100.0) if tot_delta > 0 else 0.0

    # Compute Client busiest thread utilization
    busiest_util = 0.0
    for tid, ticks0 in client_threads0.items():
        if tid in client_threads1:
            dticks = client_threads1[tid] - ticks0
            sec_used = dticks / clk_tck
            util = (sec_used / dt) * 100.0
            if util > busiest_util:
                busiest_util = util

    # Terminate processes
    try:
        client_proc.wait(timeout=3.0)
    except subprocess.TimeoutExpired:
        client_proc.kill()
        client_proc.wait()

    server_proc.send_signal(signal.SIGINT)
    try:
        server_proc.wait(timeout=2.0)
    except subprocess.TimeoutExpired:
        server_proc.kill()
        server_proc.wait()

    return busiest_util, server_core_util

def main():
    os.makedirs("results", exist_ok=True)
    out_csv = "results/client_bottleneck_check.csv"

    print("================================================================================")
    print("TASK 1: Proving / Disproving Client Bottleneck on the OLD Python Asyncio Client")
    print("================================================================================")
    print(f"{'Server':<22} | {'Conns':<6} | {'Client Busiest TID %':<22} | {'Server Core 0 %':<16} | {'Status':<12}")
    print("-" * 84)

    rows = []

    for server in SERVERS:
        for conns in CONNS:
            client_utils = []
            server_utils = []

            for trial in range(TRIALS):
                c_util, s_util = run_single_trial(server, conns)
                if c_util is not None:
                    client_utils.append(c_util)
                    server_utils.append(s_util)
                time.sleep(0.5)

            med_client = statistics.median(client_utils) if client_utils else 0.0
            med_server = statistics.median(server_utils) if server_utils else 0.0
            flag = "SATURATED (>90%)" if med_client >= 90.0 else "NORMAL"

            print(f"{server:<22} | {conns:<6} | {med_client:>6.2f}% (max: {max(client_utils):>5.2f}%)   | {med_server:>6.2f}%          | {flag:<12}")

            rows.append({
                "server": server,
                "conns": conns,
                "client_busiest_thread_util_pct": round(med_client, 2),
                "client_busiest_thread_min_pct": round(min(client_utils), 2),
                "client_busiest_thread_max_pct": round(max(client_utils), 2),
                "server_core_util_pct": round(med_server, 2),
                "client_saturated": "YES" if med_client >= 90.0 else "NO"
            })

    with open(out_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "server", "conns", "client_busiest_thread_util_pct",
            "client_busiest_thread_min_pct", "client_busiest_thread_max_pct",
            "server_core_util_pct", "client_saturated"
        ])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n[DONE] Results saved to {out_csv}")

if __name__ == "__main__":
    main()
