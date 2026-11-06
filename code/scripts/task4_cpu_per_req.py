#!/usr/bin/env python3
"""
TASK 4 (b): Server CPU cost per request and context switches with the new C load generator.
Window: 10 seconds steady state.
Measures: utime + stime from /proc/<pid>/stat, voluntary and involuntary CS from /proc/<pid>/status.
Counts requests using loadgen completed requests.
Output: results/cpu_per_req_new_client.csv
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

PORT = 8083
CONNS_LIST = [100, 1000, 5000]
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
WARMUP_S = 1.0
DURATION_S = 10.0

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

def get_proc_ticks_and_cs(pid):
    utime = 0
    stime = 0
    vol_cs = 0
    invol_cs = 0

    try:
        with open(f"/proc/{pid}/stat", "r") as f:
            content = f.read()
            idx = content.rfind(')')
            if idx != -1:
                parts = content[idx+2:].split()
                utime = int(parts[11])
                stime = int(parts[12])
    except Exception:
        pass

    try:
        with open(f"/proc/{pid}/status", "r") as f:
            for line in f:
                if line.startswith("voluntary_ctxt_switches:"):
                    vol_cs = int(line.split()[1])
                elif line.startswith("nonvoluntary_ctxt_switches:"):
                    invol_cs = int(line.split()[1])
    except Exception:
        pass

    return utime + stime, vol_cs, invol_cs

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
        return None, None, None, None, None, None

    time.sleep(0.3)

    # Launch client
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

    # Pre-steady state ticks
    tot0, busy0 = get_cpu0_ticks()
    ticks0, vol0, invol0 = get_proc_ticks_and_cs(server_proc.pid)

    p = subprocess.Popen(client_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    stdout, _ = p.communicate()

    tot1, busy1 = get_cpu0_ticks()
    ticks1, vol1, invol1 = get_proc_ticks_and_cs(server_proc.pid)

    server_proc.send_signal(signal.SIGINT)
    try:
        server_proc.wait(timeout=2.0)
    except subprocess.TimeoutExpired:
        server_proc.kill()
        server_proc.wait()

    m_req = re.search(r'req_s=([0-9.]+)', stdout)
    m_cpu = re.search(r'max_thread_cpu_pct=([0-9.]+)', stdout)

    req_s = float(m_req.group(1)) if m_req else 0.0
    client_cpu = float(m_cpu.group(1)) if m_cpu else 0.0
    total_reqs = req_s * DURATION_S

    dticks = ticks1 - ticks0
    dvol = vol1 - vol0
    dinvol = invol1 - invol0

    clk_tck = os.sysconf(os.sysconf_names['SC_CLK_TCK'])
    server_cpu_sec = dticks / clk_tck
    cpu_us_per_req = (server_cpu_sec * 1e6 / total_reqs) if total_reqs > 0 else 0.0

    dtot = tot1 - tot0
    dbusy = busy1 - busy0
    server_util = (dbusy / dtot * 100.0) if dtot > 0 else 0.0

    return cpu_us_per_req, server_util, client_cpu, dvol, dinvol, req_s

def main():
    os.makedirs("results", exist_ok=True)
    out_csv = "results/cpu_per_req_new_client.csv"
    threads = get_calibrated_threads()

    print("================================================================================")
    print(f"TASK 4(b): Server CPU Cost per Request (10s Steady Window, Client Threads={threads})")
    print("================================================================================")
    print(f"{'Server':<22} | {'Conns':<6} | {'CPU (us/req)':<14} | {'Server Core 0%':<14} | {'Client Max%':<12} | {'Vol CS':<10} | {'Invol CS':<10}")
    print("-" * 105)

    rows = []

    for server in SERVERS:
        for conns in CONNS_LIST:
            if server == "server_select" and conns > 1000:
                continue

            cpus, s_utils, c_utils, vols, invols = [], [], [], [], []
            for _ in range(TRIALS):
                c_req, s_util, c_util, v_cs, i_cs, r_s = run_trial(server, conns, threads)
                if c_req is not None and c_req > 0:
                    cpus.append(c_req)
                    s_utils.append(s_util)
                    c_utils.append(c_util)
                    vols.append(v_cs)
                    invols.append(i_cs)
                time.sleep(0.3)

            med_cpu = statistics.median(cpus) if cpus else 0.0
            med_s = statistics.median(s_utils) if s_utils else 0.0
            med_c = statistics.median(c_utils) if c_utils else 0.0
            med_v = int(statistics.median(vols)) if vols else 0
            med_inv = int(statistics.median(invols)) if invols else 0

            print(f"{server:<22} | {conns:<6} | {med_cpu:>14.2f} | {med_s:>13.2f}% | {med_c:>11.2f}% | {med_v:>10} | {med_inv:>10}")

            rows.append({
                "server": server,
                "conns": conns,
                "cpu_us_per_req": round(med_cpu, 2),
                "cpu_us_min": round(min(cpus), 2) if cpus else 0.0,
                "cpu_us_max": round(max(cpus), 2) if cpus else 0.0,
                "server_core_util": round(med_s, 2),
                "busiest_client_thread_util": round(med_c, 2),
                "voluntary_cs": med_v,
                "involuntary_cs": med_inv
            })

    with open(out_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "server", "conns", "cpu_us_per_req", "cpu_us_min", "cpu_us_max",
            "server_core_util", "busiest_client_thread_util",
            "voluntary_cs", "involuntary_cs"
        ])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n[DONE] Saved CPU cost per request results to {out_csv}")

if __name__ == "__main__":
    main()
