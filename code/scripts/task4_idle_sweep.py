#!/usr/bin/env python3
"""
TASK 4 (d): Idle connection sweep with the new C load generator.
Fixed 100 active connections; idle connections: 0, 500, 1000, 2000, 3000, 4000, 5000, 7500, 10000.
Servers: server_poll, epoll_lt_server, epoll_et_server, io_uring_opt_server.
5 trials per point (median, min, max for req_s and p99).
Generates: results/idle_sweep_new_client.csv,
           results/idle_sweep_new_client_throughput.png,
           results/idle_sweep_new_client_latency.png
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
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

PORT = 8084
ACTIVE_CONNS = 100
IDLE_COUNTS = [0, 500, 1000, 2000, 3000, 4000, 5000, 7500, 10000]
SERVERS = [
    "server_poll",
    "epoll_lt_server",
    "epoll_et_server",
    "io_uring_opt_server"
]
TRIALS = 5
WARMUP_S = 0.5
DURATION_S = 2.0

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

def run_trial(server_name, idle_conns, threads):
    bin_path = os.path.join("bin", server_name)
    total_conns = ACTIVE_CONNS + idle_conns
    core_list = ",".join(str(c) for c in range(1, threads + 1))

    server_proc = subprocess.Popen(
        ["taskset", "-c", "0", bin_path, str(PORT)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    if not wait_for_server(PORT):
        server_proc.kill()
        return None, None

    time.sleep(0.3)

    client_cmd = [
        "bin/loadgen",
        "--host", "127.0.0.1",
        "--port", str(PORT),
        "--conns", str(total_conns),
        "--active", str(ACTIVE_CONNS),
        "--threads", str(threads),
        "--duration", str(DURATION_S),
        "--warmup", str(WARMUP_S),
        "--cores", core_list
    ]

    p = subprocess.Popen(client_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    stdout, _ = p.communicate()

    server_proc.send_signal(signal.SIGINT)
    try:
        server_proc.wait(timeout=2.0)
    except subprocess.TimeoutExpired:
        server_proc.kill()
        server_proc.wait()

    m_req = re.search(r'req_s=([0-9.]+)', stdout)
    m_p99 = re.search(r'p99_us=([0-9.]+)', stdout)

    req_s = float(m_req.group(1)) if m_req else 0.0
    p99_us = float(m_p99.group(1)) if m_p99 else 0.0

    return req_s, p99_us

def generate_plots(csv_file):
    data = {}
    with open(csv_file, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            s = row["server"]
            if s not in data:
                data[s] = {"idle": [], "med_req": [], "min_req": [], "max_req": [],
                           "med_p99": [], "min_p99": [], "max_p99": []}
            data[s]["idle"].append(int(row["idle_conns"]))
            data[s]["med_req"].append(float(row["throughput_req_s_median"]))
            data[s]["min_req"].append(float(row["throughput_min"]))
            data[s]["max_req"].append(float(row["throughput_max"]))
            data[s]["med_p99"].append(float(row["p99_us_median"]) / 1000.0) # convert to ms
            data[s]["min_p99"].append(float(row["p99_min"]) / 1000.0)
            data[s]["max_p99"].append(float(row["p99_max"]) / 1000.0)

    colors = {
        "server_poll": "#d62728",        # red
        "epoll_lt_server": "#1f77b4",    # blue
        "epoll_et_server": "#2ca02c",    # green
        "io_uring_opt_server": "#ff7f0e" # orange
    }
    labels = {
        "server_poll": "poll() (O(N) linear scan)",
        "epoll_lt_server": "epoll (Level-Triggered)",
        "epoll_et_server": "epoll (Edge-Triggered)",
        "io_uring_opt_server": "io_uring (DEFER_TASKRUN)"
    }

    # Plot 1: Throughput vs Idle Connections
    plt.figure(figsize=(10, 6), dpi=150)
    for s, d in data.items():
        yerr_lower = [m - n for m, n in zip(d["med_req"], d["min_req"])]
        yerr_upper = [x - m for m, x in zip(d["med_req"], d["max_req"])]
        plt.errorbar(d["idle"], d["med_req"], yerr=[yerr_lower, yerr_upper],
                     fmt='-o', color=colors.get(s, '#333'), label=labels.get(s, s),
                     capsize=4, elinewidth=1.2, linewidth=2, markersize=5)

    plt.title("Throughput vs Idle Connections (100 Active Sockets, High-Headroom Client)", fontsize=13, fontweight='bold', pad=12)
    plt.xlabel("Idle Connections (Connected & Silent)", fontsize=11)
    plt.ylabel("Throughput (Completed Requests / sec)", fontsize=11)
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend(frameon=True, facecolor="white", edgecolor="#ccc", fontsize=10)
    plt.tight_layout()
    plt.savefig("results/idle_sweep_new_client_throughput.png")
    plt.close()

    # Plot 2: Tail Latency (p99) vs Idle Connections
    plt.figure(figsize=(10, 6), dpi=150)
    for s, d in data.items():
        yerr_lower = [m - n for m, n in zip(d["med_p99"], d["min_p99"])]
        yerr_upper = [x - m for m, x in zip(d["med_p99"], d["max_p99"])]
        plt.errorbar(d["idle"], d["med_p99"], yerr=[yerr_lower, yerr_upper],
                     fmt='-s', color=colors.get(s, '#333'), label=labels.get(s, s),
                     capsize=4, elinewidth=1.2, linewidth=2, markersize=5)

    plt.title("Tail Latency (p99) vs Idle Connections (100 Active Sockets)", fontsize=13, fontweight='bold', pad=12)
    plt.xlabel("Idle Connections (Connected & Silent)", fontsize=11)
    plt.ylabel("p99 Latency (milliseconds)", fontsize=11)
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend(frameon=True, facecolor="white", edgecolor="#ccc", fontsize=10)
    plt.tight_layout()
    plt.savefig("results/idle_sweep_new_client_latency.png")
    plt.close()

def main():
    os.makedirs("results", exist_ok=True)
    out_csv = "results/idle_sweep_new_client.csv"
    threads = get_calibrated_threads()

    print("================================================================================")
    print(f"TASK 4(d): Idle Sweep Benchmark (100 Active, 0-10,000 Idle, Client Threads={threads})")
    print("================================================================================")
    print(f"{'Server':<22} | {'Idle':<6} | {'Req/s (Med)':<14} | {'Min':<10} | {'Max':<10} | {'p99 (us)':<10}")
    print("-" * 88)

    rows = []

    for server in SERVERS:
        for idle in IDLE_COUNTS:
            reqs, p99s = [], []
            for _ in range(TRIALS):
                r, p = run_trial(server, idle, threads)
                if r is not None and r > 0:
                    reqs.append(r)
                    p99s.append(p)
                time.sleep(0.3)

            med_req = statistics.median(reqs) if reqs else 0.0
            min_req = min(reqs) if reqs else 0.0
            max_req = max(reqs) if reqs else 0.0
            med_p99 = statistics.median(p99s) if p99s else 0.0
            min_p99 = min(p99s) if p99s else 0.0
            max_p99 = max(p99s) if p99s else 0.0

            print(f"{server:<22} | {idle:<6} | {med_req:>14.2f} | {min_req:>10.2f} | {max_req:>10.2f} | {med_p99:>10.2f}")

            rows.append({
                "server": server,
                "idle_conns": idle,
                "throughput_req_s_median": round(med_req, 2),
                "throughput_min": round(min_req, 2),
                "throughput_max": round(max_req, 2),
                "p99_us_median": round(med_p99, 2),
                "p99_min": round(min_p99, 2),
                "p99_max": round(max_p99, 2)
            })

    with open(out_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "server", "idle_conns", "throughput_req_s_median", "throughput_min", "throughput_max",
            "p99_us_median", "p99_min", "p99_max"
        ])
        writer.writeheader()
        writer.writerows(rows)

    generate_plots(out_csv)
    print(f"\n[DONE] Saved idle sweep results to {out_csv} and generated PNG plots.")

if __name__ == "__main__":
    main()
