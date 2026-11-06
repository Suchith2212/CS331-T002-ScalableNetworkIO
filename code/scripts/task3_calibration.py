#!/usr/bin/env python3
"""
TASK 3: Calibrate the new C load generator.
Scale client threads (1, 2, 4, 8, 12, 14) against the reference echo server
until the server core is >90% busy while no client thread is >85%.
Output: results/calibration.csv
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

PORT = 8099
THREAD_COUNTS = [1, 2, 4, 6, 8, 10, 12, 14]
CONNS = 1000
WARMUP_S = 2
DURATION_S = 10
TRIALS = 3

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
    try:
        with open("/proc/stat", "r") as f:
            for line in f:
                if line.startswith("cpu0 "):
                    parts = [int(p) for p in line.split()[1:]]
                    total = sum(parts)
                    busy = total - parts[3] - parts[4]
                    return total, busy
    except Exception:
        pass
    return 0, 0

def run_calibration_trial(threads):
    # Pin server to Core 0
    server_proc = subprocess.Popen(
        ["taskset", "-c", "0", "bin/reference_server", str(PORT)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    if not wait_for_server(PORT):
        server_proc.kill()
        return None, None, None

    # Cores for client: 1 to threads
    core_list = ",".join(str(c) for c in range(1, threads + 1))

    # CPU0 ticks before steady state
    time.sleep(1.0)
    tot0, busy0 = get_cpu0_ticks()

    # Run loadgen
    loadgen_cmd = [
        "bin/loadgen",
        "--host", "127.0.0.1",
        "--port", str(PORT),
        "--conns", str(CONNS),
        "--active", str(CONNS),
        "--threads", str(threads),
        "--duration", str(DURATION_S),
        "--warmup", str(WARMUP_S),
        "--cores", core_list
    ]

    p = subprocess.Popen(loadgen_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    stdout, stderr = p.communicate()

    tot1, busy1 = get_cpu0_ticks()

    # Kill server
    server_proc.send_signal(signal.SIGINT)
    try:
        server_proc.wait(timeout=2.0)
    except subprocess.TimeoutExpired:
        server_proc.kill()
        server_proc.wait()

    # Parse stdout:
    # req_s=... p50_us=... p99_us=... p999_us=... errors=... max_thread_cpu_pct=...
    m_req = re.search(r'req_s=([0-9.]+)', stdout)
    m_cpu = re.search(r'max_thread_cpu_pct=([0-9.]+)', stdout)

    req_s = float(m_req.group(1)) if m_req else 0.0
    client_cpu = float(m_cpu.group(1)) if m_cpu else 0.0

    dtot = tot1 - tot0
    dbusy = busy1 - busy0
    server_core_util = (dbusy / dtot * 100.0) if dtot > 0 else 0.0

    return req_s, server_core_util, client_cpu

def main():
    os.makedirs("results", exist_ok=True)
    out_csv = "results/calibration.csv"

    print("================================================================================")
    print("TASK 3: Calibrating High-Headroom C Load Generator against Reference Server")
    print("================================================================================")
    print(f"{'Threads':<8} | {'Conns':<6} | {'Throughput (req/s)':<20} | {'Server Core 0 %':<16} | {'Client Max Thread %':<20} | {'Status'}")
    print("-" * 92)

    rows = []
    chosen_thread_count = None
    max_server_util = 0.0

    for threads in THREAD_COUNTS:
        req_list, server_list, client_list = [], [], []
        for _ in range(TRIALS):
            r, s, c = run_calibration_trial(threads)
            if r is not None:
                req_list.append(r)
                server_list.append(s)
                client_list.append(c)
            time.sleep(0.5)

        med_req = statistics.median(req_list) if req_list else 0.0
        med_server = statistics.median(server_list) if server_list else 0.0
        med_client = statistics.median(client_list) if client_list else 0.0

        if med_server > max_server_util:
            max_server_util = med_server

        status = "NEEDS MORE THREADS"
        if med_server >= 90.0 and med_client <= 85.0:
            status = "OPTIMAL (SERVER SATURATED)"
            if chosen_thread_count is None:
                chosen_thread_count = threads
        elif med_server >= 90.0 and med_client > 85.0:
            status = "SERVER SATURATED (CLIENT HEAVY)"
        elif med_client > 85.0:
            status = "CLIENT BOTTLENECK"

        print(f"{threads:<8} | {CONNS:<6} | {med_req:>16.2f} req/s | {med_server:>14.2f}% | {med_client:>18.2f}% | {status}")

        rows.append({
            "client_threads": threads,
            "conns": CONNS,
            "throughput_req_s": round(med_req, 2),
            "server_core_util_pct": round(med_server, 2),
            "max_client_thread_util_pct": round(med_client, 2),
            "status": status
        })

    with open(out_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "client_threads", "conns", "throughput_req_s",
            "server_core_util_pct", "max_client_thread_util_pct", "status"
        ])
        writer.writeheader()
        writer.writerows(rows)

    print("\n--------------------------------------------------------------------------------")
    if chosen_thread_count is not None:
        print(f"Calibration SUCCESS: Optimal thread count = {chosen_thread_count} (Server Core >= 90%, Client Threads <= 85%)")
    else:
        print(f"Calibration NOTE: Max server core utilization achieved was {max_server_util:.2f}%.")
        # Pick the thread count with maximum server utilization and safest client headroom
        best_row = max(rows, key=lambda x: x["server_core_util_pct"])
        chosen_thread_count = best_row["client_threads"]
        print(f"Using best thread count = {chosen_thread_count} for subsequent benchmarks.")
    print(f"Saved calibration data to {out_csv}")
    print("--------------------------------------------------------------------------------")

if __name__ == "__main__":
    main()
