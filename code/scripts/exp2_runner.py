#!/usr/bin/env python3
import os
import sys
import time
import subprocess
import signal
import csv

PORT = 8087
SERVERS = [
    "server_blocking",
    "server_select",
    "server_poll",
    "epoll_lt_server",
    "epoll_et_server",
    "io_uring_opt_server"
]
CONNS = [100, 1000, 5000]
WINDOW_SECONDS = 10

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

def get_clk_tck():
    try:
        return os.sysconf(os.sysconf_names['SC_CLK_TCK'])
    except Exception:
        return 100.0

def read_proc_stat_cpu():
    # Returns dict of {cpu_name: (busy_ticks, total_ticks)}
    cpus = {}
    try:
        with open("/proc/stat", "r") as f:
            for line in f:
                if line.startswith("cpu"):
                    parts = line.split()
                    name = parts[0]
                    vals = [float(x) for x in parts[1:]]
                    idle = vals[3] + (vals[4] if len(vals) > 4 else 0)
                    total = sum(vals)
                    busy = total - idle
                    cpus[name] = (busy, total)
    except Exception:
        pass
    return cpus

def read_pid_stat(pid):
    # Returns utime + stime in ticks
    try:
        with open(f"/proc/{pid}/stat", "r") as f:
            line = f.read()
            # Handle process names with spaces enclosed in parentheses
            rparen = line.rfind(")")
            parts = line[rparen + 2:].split()
            utime = int(parts[11]) # index 13 in 1-based /proc/pid/stat
            stime = int(parts[12]) # index 14
            return utime + stime
    except Exception:
        return 0

def read_pid_status_cs(pid):
    # Returns (vol_cs, invol_cs)
    vol = 0
    invol = 0
    try:
        with open(f"/proc/{pid}/status", "r") as f:
            for line in f:
                if line.startswith("voluntary_ctxt_switches:"):
                    vol = int(line.split()[1])
                elif line.startswith("nonvoluntary_ctxt_switches:"):
                    invol = int(line.split()[1])
    except Exception:
        pass
    return vol, invol

def run_exp2_trial(server_bin, num_conns):
    # Pin server to Core 0
    server_proc = subprocess.Popen(
        ["taskset", "-c", "0", server_bin, str(PORT)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    if not wait_for_server(PORT):
        server_proc.kill()
        return None

    time.sleep(0.5)
    pid = server_proc.pid
    clk_tck = get_clk_tck()

    # Launch client load generator pinned to Cores 1-15 in background
    load_proc = subprocess.Popen(
        ["taskset", "-c", "1-15", "python3", "scripts/load_worker.py", str(PORT), str(num_conns), str(WINDOW_SECONDS)],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True
    )

    # Let warm up for 0.5s into steady-state
    time.sleep(0.5)

    # Sample START
    stat_start = read_pid_stat(pid)
    vol_start, invol_start = read_pid_status_cs(pid)
    cpu_start = read_proc_stat_cpu()
    t0 = time.time()

    # Wait for load generator to finish
    stdout, _ = load_proc.communicate()
    t1 = time.time()

    # Sample END
    stat_end = read_pid_stat(pid)
    vol_end, invol_end = read_pid_status_cs(pid)
    cpu_end = read_proc_stat_cpu()

    # Cleanly terminate server
    server_proc.send_signal(signal.SIGTERM)
    try:
        server_proc.wait(timeout=1.0)
    except subprocess.TimeoutExpired:
        server_proc.kill()
    time.sleep(0.3)

    # Parse total requests from load generator
    try:
        total_reqs = int(stdout.strip())
    except Exception:
        total_reqs = 0

    elapsed = t1 - t0
    delta_ticks = stat_end - stat_start
    cpu_time_s = delta_ticks / clk_tck
    cpu_us_per_req = (cpu_time_s * 1e6 / total_reqs) if total_reqs > 0 else 0.0

    delta_vol = vol_end - vol_start
    delta_invol = invol_end - invol_start

    # Core 0 util
    if "cpu0" in cpu_start and "cpu0" in cpu_end:
        b0 = cpu_end["cpu0"][0] - cpu_start["cpu0"][0]
        tot0 = cpu_end["cpu0"][1] - cpu_start["cpu0"][1]
        server_core_util = (b0 / tot0 * 100.0) if tot0 > 0 else 0.0
    else:
        server_core_util = 0.0

    # Cores 1-15 util
    client_utils = []
    for c_id in range(1, 16):
        c_name = f"cpu{c_id}"
        if c_name in cpu_start and c_name in cpu_end:
            bc = cpu_end[c_name][0] - cpu_start[c_name][0]
            tc = cpu_end[c_name][1] - cpu_start[c_name][1]
            if tc > 0:
                client_utils.append(bc / tc * 100.0)
    client_core_util = (sum(client_utils) / len(client_utils)) if client_utils else 0.0

    return {
        "cpu_us_per_req": round(cpu_us_per_req, 2),
        "server_core_util": round(server_core_util, 1),
        "client_core_util": round(client_core_util, 1),
        "vol_cs": delta_vol,
        "invol_cs": delta_invol,
        "total_reqs": total_reqs,
        "client_bottleneck": client_core_util > 90.0
    }

def main():
    os.makedirs("results", exist_ok=True)
    csv_file = "results/exp2_cpu_per_req.csv"
    results = []

    print("\n--- Running Experiment 2: CPU Cost Per Request & Client Bottleneck Detection ---")
    print(f"{'Server':<22} | {'Conns':<6} | {'CPU (us/req)':<12} | {'Srv Util%':<10} | {'Cli Util%':<10} | {'Vol CS':<8} | {'Invol CS':<9} | {'Bottleneck'}")
    print("-" * 100)

    for server in SERVERS:
        bin_path = os.path.join("bin", server)
        for conn in CONNS:
            if server == "server_select" and conn > 1020:
                print(f"{server:<22} | {conn:<6} | {'EXCEEDED':<12} | {'N/A':<10} | {'N/A':<10} | {'N/A':<8} | {'N/A':<9} | N/A")
                continue

            data = run_exp2_trial(bin_path, conn)
            if data:
                b_flag = "CLIENT >90%!" if data["client_bottleneck"] else "NORMAL"
                print(f"{server:<22} | {conn:<6} | {data['cpu_us_per_req']:<12} | {data['server_core_util']:<10} | {data['client_core_util']:<10} | {data['vol_cs']:<8} | {data['invol_cs']:<9} | {b_flag}")
                results.append({
                    "server": server,
                    "conns": conn,
                    "cpu_us_per_req": data["cpu_us_per_req"],
                    "server_core_util": data["server_core_util"],
                    "client_core_util": data["client_core_util"],
                    "vol_cs": data["vol_cs"],
                    "invol_cs": data["invol_cs"]
                })

    with open(csv_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["server", "conns", "cpu_us_per_req", "server_core_util", "client_core_util", "vol_cs", "invol_cs"])
        writer.writeheader()
        writer.writerows(results)

    print(f"\nSaved Experiment 2 results to {csv_file}")

if __name__ == "__main__":
    main()
