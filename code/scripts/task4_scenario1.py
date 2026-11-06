#!/usr/bin/env python3
"""
TASK 4 (a): Scenario 1 benchmark with the new C load generator.
Conns: 10, 100, 500, 1000, 2000, 5000 active connections.
Servers: server_blocking, server_select (up to 1000), server_poll,
         epoll_lt_server, epoll_et_server, epoll_lt_lean_server, io_uring_opt_server.
5 trials per point (median, min, max, p99 median, server core util, busiest client thread util).
Output: results/s1_new_client.csv
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

PORT = 8082
CONNS_LIST = [10, 100, 500, 1000, 2000, 5000]
SERVERS = [
    "server_blocking",
    "server_select",
    "server_poll",
    "epoll_lt_server",
    "epoll_et_server",
    "epoll_lt_lean_server",
    "io_uring_opt_server"
]
TRIALS = 5
WARMUP_S = 0.5
DURATION_S = 2.5

def get_calibrated_threads():
    calib_csv = "results/calibration.csv"
    if os.path.exists(calib_csv):
        try:
            with open(calib_csv, "r") as f:
                reader = csv.DictReader(f)
                best_t = 4
                max_s = 0.0
                for row in reader:
                    s_util = float(row["server_core_util_pct"])
                    c_util = float(row["max_client_thread_util_pct"])
                    t = int(row["client_threads"])
                    if s_util >= 90.0 and c_util <= 85.0:
                        return t
                    if s_util > max_s:
                        max_s = s_util
                        best_t = t
                return best_t
        except Exception:
            pass
    return 4

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

def run_trial(server_name, conns, threads):
    bin_path = os.path.join("bin", server_name)
    core_list = ",".join(str(c) for c in range(1, threads + 1))

    server_proc = subprocess.Popen(
        ["taskset", "-c", "0", bin_path, str(PORT)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    if not wait_for_server(PORT):
        server_proc.kill()
        return None, None, None, None

    time.sleep(0.3)
    tot0, busy0 = get_cpu0_ticks()

    client_cmd = [
        "bin/loadgen",
        "--host", "127.0.0.1",
        "--port", str(PORT),
        "--conns", str(conns),
        "--active", str(conns),
        "--threads", str(threads),
        "--duration", str(DURATION_S),
        "--warmup", str(WARMUP_S),
        "--cores", core_list
    ]

    p = subprocess.Popen(client_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    stdout, _ = p.communicate()

    tot1, busy1 = get_cpu0_ticks()

    server_proc.send_signal(signal.SIGINT)
    try:
        server_proc.wait(timeout=2.0)
    except subprocess.TimeoutExpired:
        server_proc.kill()
        server_proc.wait()

    m_req = re.search(r'req_s=([0-9.]+)', stdout)
    m_p99 = re.search(r'p99_us=([0-9.]+)', stdout)
    m_cpu = re.search(r'max_thread_cpu_pct=([0-9.]+)', stdout)

    req_s = float(m_req.group(1)) if m_req else 0.0
    p99_us = float(m_p99.group(1)) if m_p99 else 0.0
    client_cpu = float(m_cpu.group(1)) if m_cpu else 0.0

    dtot = tot1 - tot0
    dbusy = busy1 - busy0
    server_util = (dbusy / dtot * 100.0) if dtot > 0 else 0.0

    return req_s, p99_us, server_util, client_cpu

def main():
    os.makedirs("results", exist_ok=True)
    out_csv = "results/s1_new_client.csv"
    threads = get_calibrated_threads()

    print("================================================================================")
    print(f"TASK 4(a): Scenario 1 Benchmark with New C Load Generator (Client Threads={threads})")
    print("================================================================================")
    print(f"{'Server':<22} | {'Conns':<6} | {'Req/s (Med)':<14} | {'Min':<10} | {'Max':<10} | {'p99 (us)':<10} | {'Server Core 0%':<14} | {'Client Max%':<12}")
    print("-" * 115)

    rows = []

    for server in SERVERS:
        for conns in CONNS_LIST:
            if server == "server_select" and conns > 1000:
                continue

            reqs, p99s, s_utils, c_utils = [], [], [], []
            for _ in range(TRIALS):
                r, p, s, c = run_trial(server, conns, threads)
                if r is not None and r > 0:
                    reqs.append(r)
                    p99s.append(p)
                    s_utils.append(s)
                    c_utils.append(c)
                time.sleep(0.3)

            med_req = statistics.median(reqs) if reqs else 0.0
            min_req = min(reqs) if reqs else 0.0
            max_req = max(reqs) if reqs else 0.0
            med_p99 = statistics.median(p99s) if p99s else 0.0
            med_s = statistics.median(s_utils) if s_utils else 0.0
            med_c = statistics.median(c_utils) if c_utils else 0.0

            print(f"{server:<22} | {conns:<6} | {med_req:>14.2f} | {min_req:>10.2f} | {max_req:>10.2f} | {med_p99:>10.2f} | {med_s:>13.2f}% | {med_c:>11.2f}%")

            rows.append({
                "server": server,
                "conns": conns,
                "req_s_median": round(med_req, 2),
                "req_s_min": round(min_req, 2),
                "req_s_max": round(max_req, 2),
                "p99_us_median": round(med_p99, 2),
                "server_core_util": round(med_s, 2),
                "busiest_client_thread_util": round(med_c, 2)
            })

    with open(out_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "server", "conns", "req_s_median", "req_s_min", "req_s_max",
            "p99_us_median", "server_core_util", "busiest_client_thread_util"
        ])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n[DONE] Saved Scenario 1 results to {out_csv}")

if __name__ == "__main__":
    main()
