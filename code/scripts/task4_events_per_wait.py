#!/usr/bin/env python3
"""
TASK 4 (c): Events per wakeup and waits per request with the new C load generator.
Uses -DSTATS instrumented builds.
Conns: 100, 1000, 5000 active connections.
5 trials per point (median reported).
Output: results/events_per_wait_new_client.csv
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

PORT = 8085
CONNS_LIST = [100, 1000, 5000]
SERVERS = [
    "server_poll_stats",
    "epoll_lt_server_stats",
    "epoll_et_server_stats",
    "epoll_lt_lean_server_stats",
    "io_uring_opt_server_stats"
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

def run_trial(server_bin, conns, threads):
    bin_path = os.path.join("bin", server_bin)
    core_list = ",".join(str(c) for c in range(1, threads + 1))

    server_proc = subprocess.Popen(
        ["taskset", "-c", "0", bin_path, str(PORT)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    if not wait_for_server(PORT):
        server_proc.kill()
        return None, None, None

    time.sleep(0.3)

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

    p = subprocess.Popen(client_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    p.wait()

    server_proc.send_signal(signal.SIGTERM)
    try:
        stdout, stderr = server_proc.communicate(timeout=2.0)
    except subprocess.TimeoutExpired:
        server_proc.kill()
        stdout, stderr = server_proc.communicate()

    # Parse [STATS] line
    # Format: [STATS] server=... waits=X events=Y requests=Z avg_events_per_wait=A waits_per_request=B req_per_s=C
    combined = stdout + "\n" + stderr
    m_ev = re.search(r'avg_events_per_wait=([0-9.]+)', combined)
    m_wt = re.search(r'waits_per_request=([0-9.]+)', combined)
    m_rq = re.search(r'req_per_s=([0-9.]+)', combined)

    if m_ev and m_wt:
        ev = float(m_ev.group(1))
        wt = float(m_wt.group(1))
        rq = float(m_rq.group(1)) if m_rq else 0.0
        return ev, wt, rq
    return None, None, None

def main():
    os.makedirs("results", exist_ok=True)
    out_csv = "results/events_per_wait_new_client.csv"
    threads = get_calibrated_threads()

    print("================================================================================")
    print(f"TASK 4 (c): Events per Wait & Waits per Request (Client Threads={threads})")
    print("================================================================================")
    print(f"{'Server':<28} | {'Conns':<6} | {'Avg Events/Wait':<18} | {'Waits/Request':<16} | {'Req/s':<12}")
    print("-" * 88)

    rows = []

    for server in SERVERS:
        clean_name = server.replace("_stats", "")
        for conns in CONNS_LIST:
            ev_list, wt_list, rq_list = [], [], []
            for _ in range(TRIALS):
                ev, wt, rq = run_trial(server, conns, threads)
                if ev is not None:
                    ev_list.append(ev)
                    wt_list.append(wt)
                    rq_list.append(rq)
                time.sleep(0.3)

            med_ev = statistics.median(ev_list) if ev_list else 0.0
            med_wt = statistics.median(wt_list) if wt_list else 0.0
            med_rq = statistics.median(rq_list) if rq_list else 0.0

            print(f"{clean_name:<28} | {conns:<6} | {med_ev:>18.4f} | {med_wt:>16.6f} | {med_rq:>12.2f}")

            rows.append({
                "server": clean_name,
                "conns": conns,
                "avg_events_per_wait": round(med_ev, 4),
                "waits_per_request": round(med_wt, 6),
                "req_per_s": round(med_rq, 2)
            })

    with open(out_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "server", "conns", "avg_events_per_wait", "waits_per_request", "req_per_s"
        ])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n[DONE] Saved events per wait results to {out_csv}")

if __name__ == "__main__":
    main()
