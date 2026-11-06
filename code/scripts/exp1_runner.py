#!/usr/bin/env python3
import os
import sys
import time
import subprocess
import signal
import statistics
import csv
import re
from load_worker import main as run_load_worker

PORT = 8086
SERVERS = [
    "server_poll_stats",
    "epoll_lt_server_stats",
    "epoll_et_server_stats",
    "io_uring_opt_server_stats"
]
CONNS = [100, 1000, 5000]
TRIALS = 5
DURATION = 3 # 3 seconds load per trial

def is_port_open(port):
    import socket
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

def run_single_trial(server_bin, num_conns):
    # Pin server to Core 0
    proc = subprocess.Popen(
        ["taskset", "-c", "0", server_bin, str(PORT)],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True
    )

    if not wait_for_server(PORT):
        proc.kill()
        return None, None

    time.sleep(0.2)

    # Run load generator pinned to Cores 1-15
    load_proc = subprocess.Popen(
        ["taskset", "-c", "1-15", "python3", "scripts/load_worker.py", str(PORT), str(num_conns), str(DURATION)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    load_proc.wait()

    # Send SIGTERM to server to trigger stats report
    proc.send_signal(signal.SIGTERM)
    try:
        stdout, _ = proc.communicate(timeout=2.0)
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, _ = proc.communicate()

    time.sleep(0.3)

    # Parse [STATS] line
    # Format: ... avg_events_per_wait=X waits_per_request=Y
    m_events = re.search(r'avg_events_per_wait=([0-9.]+)', stdout)
    m_waits = re.search(r'waits_per_request=([0-9.]+)', stdout)

    if m_events and m_waits:
        return float(m_events.group(1)), float(m_waits.group(1))
    return None, None

def main():
    os.makedirs("results", exist_ok=True)
    csv_file = "results/exp1_events_per_wait.csv"
    results = []

    print("\n--- Running Experiment 1: Events Per Wakeup & Waits Per Request (5 Trials Median) ---")
    print(f"{'Server':<26} | {'Conns':<6} | {'Avg Events/Wait':<18} | {'Waits/Request':<16}")
    print("-" * 72)

    for server in SERVERS:
        bin_path = os.path.join("bin", server)
        clean_name = server.replace("_stats", "")

        for conn in CONNS:
            events_list = []
            waits_list = []

            for _ in range(TRIALS):
                ev, wt = run_single_trial(bin_path, conn)
                if ev is not None:
                    events_list.append(ev)
                    waits_list.append(wt)

            if events_list:
                med_events = round(statistics.median(events_list), 4)
                med_waits = round(statistics.median(waits_list), 6)
            else:
                med_events, med_waits = 0.0, 0.0

            print(f"{clean_name:<26} | {conn:<6} | {med_events:<18} | {med_waits:<16}")
            results.append({
                "server": clean_name,
                "conns": conn,
                "avg_events_per_wait": med_events,
                "waits_per_request": med_waits
            })

    with open(csv_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["server", "conns", "avg_events_per_wait", "waits_per_request"])
        writer.writeheader()
        writer.writerows(results)

    print(f"\nSaved Experiment 1 results to {csv_file}")

if __name__ == "__main__":
    main()
