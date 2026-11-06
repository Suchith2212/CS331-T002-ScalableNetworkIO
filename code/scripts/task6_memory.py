#!/usr/bin/env python3
"""
TASK 6: Memory profiling including user-space (VmRSS, VmData, Pss from smaps_rollup)
and kernel socket memory (system MemAvailable delta, TCP memory pages from sockstat).
Output: results/memory_new.csv
"""
import os
import sys
import time
import socket
import subprocess
import signal
import csv
import re

PORT = 8092
CONNS_LIST = [0, 1000, 5000]
SERVERS = [
    "server_blocking",
    "server_select",
    "server_poll",
    "epoll_lt_server",
    "epoll_et_server",
    "epoll_lt_lean_server",
    "io_uring_opt_server"
]

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

def get_system_mem_stats():
    mem_avail_kb = 0
    tcp_pages = 0
    try:
        with open("/proc/meminfo", "r") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    mem_avail_kb = int(line.split()[1])
                    break
    except Exception:
        pass

    try:
        with open("/proc/net/sockstat", "r") as f:
            for line in f:
                if line.startswith("TCP:"):
                    m = re.search(r'mem\s+(\d+)', line)
                    if m:
                        tcp_pages = int(m.group(1))
                    break
    except Exception:
        pass

    return mem_avail_kb, tcp_pages

def get_process_mem_stats(pid):
    vm_rss_kb = 0
    vm_data_kb = 0
    pss_kb = 0

    try:
        with open(f"/proc/{pid}/status", "r") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    vm_rss_kb = int(line.split()[1])
                elif line.startswith("VmData:"):
                    vm_data_kb = int(line.split()[1])
    except Exception:
        pass

    try:
        with open(f"/proc/{pid}/smaps_rollup", "r") as f:
            for line in f:
                if line.startswith("Rss:"):
                    vm_rss_kb = int(line.split()[1])
                elif line.startswith("Pss:"):
                    pss_kb = int(line.split()[1])
    except Exception:
        pass

    return vm_rss_kb, vm_data_kb, pss_kb

def main():
    os.makedirs("results", exist_ok=True)
    out_csv = "results/memory_new.csv"

    print("================================================================================")
    print("TASK 6: Memory Profiling (User-Space RSS/VmData/Pss + Kernel TCP Socket Memory)")
    print("================================================================================")
    print(f"{'Server':<22} | {'Conns':<6} | {'VmRSS (KB)':<10} | {'Pss (KB)':<10} | {'VmData (KB)':<12} | {'Kernel TCP (KB)':<16} | {'Total Est (KB)':<14}")
    print("-" * 105)

    rows = []

    for server in SERVERS:
        bin_path = os.path.join("bin", server)
        for conns in CONNS_LIST:
            if server == "server_select" and conns > 1000:
                continue

            base_avail_kb, base_tcp_pages = get_system_mem_stats()

            # Start server
            server_proc = subprocess.Popen(
                ["taskset", "-c", "0", bin_path, str(PORT)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            if not wait_for_server(PORT):
                server_proc.kill()
                continue

            time.sleep(0.3)

            client_proc = None
            if conns > 0:
                # Use loadgen with 4 threads to hold conns
                client_cmd = [
                    "bin/loadgen",
                    "--host", "127.0.0.1",
                    "--port", str(PORT),
                    "--conns", str(conns),
                    "--active", str(conns),
                    "--threads", "4",
                    "--duration", "5",
                    "--warmup", "1",
                    "--cores", "1,2,3,4"
                ]
                client_proc = subprocess.Popen(client_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                time.sleep(2.5) # allow connections to establish and steady state to run

            # Sample memory
            rss_kb, data_kb, pss_kb = get_process_mem_stats(server_proc.pid)
            curr_avail_kb, curr_tcp_pages = get_system_mem_stats()

            delta_tcp_pages = max(0, curr_tcp_pages - base_tcp_pages)
            kernel_tcp_mem_kb = delta_tcp_pages * 4 # 4KB per page
            total_est_kb = rss_kb + kernel_tcp_mem_kb

            arch_desc = ""
            if "epoll_lt_lean" in server:
                arch_desc = "On-demand pointer table (0B heap until write stalls)"
            elif "epoll_lt" in server or "epoll_et" in server:
                arch_desc = "Static client_states[65536] (4KB wbuf touched per fd)"
            elif "io_uring_opt" in server:
                arch_desc = "Shared buffer pool (no per-connection buffer, 8192x4KB pool)"
            elif "server_poll" in server:
                arch_desc = "Dynamic struct pollfd array (8B/conn) + 4KB stack buffer"
            elif "server_select" in server:
                arch_desc = "Static fd_set bitmasks (FD_SETSIZE 1024)"
            elif "server_blocking" in server:
                arch_desc = "One thread per connection (stack + pthread state)"
            else:
                arch_desc = "Baseline server implementation"

            print(f"{server:<22} | {conns:<6} | {rss_kb:>10} | {pss_kb:>10} | {data_kb:>12} | {kernel_tcp_mem_kb:>16} | {total_est_kb:>14}")

            rows.append({
                "server": server,
                "conns": conns,
                "user_vm_rss_kb": rss_kb,
                "user_pss_kb": pss_kb,
                "user_vm_data_kb": data_kb,
                "kernel_tcp_mem_kb": kernel_tcp_mem_kb,
                "total_estimated_kb": total_est_kb,
                "memory_architecture_description": arch_desc
            })

            if client_proc:
                try:
                    client_proc.wait(timeout=4.0)
                except subprocess.TimeoutExpired:
                    client_proc.kill()
                    client_proc.wait()

            server_proc.send_signal(signal.SIGINT)
            try:
                server_proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                server_proc.kill()
                server_proc.wait()

            time.sleep(0.5)

    with open(out_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "server", "conns", "user_vm_rss_kb", "user_pss_kb",
            "user_vm_data_kb", "kernel_tcp_mem_kb", "total_estimated_kb",
            "memory_architecture_description"
        ])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n[DONE] Saved memory breakdown results to {out_csv}")

if __name__ == "__main__":
    main()
