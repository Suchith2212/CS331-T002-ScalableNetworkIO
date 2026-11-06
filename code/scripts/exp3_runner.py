#!/usr/bin/env python3
import os
import sys
import time
import subprocess
import signal
import socket
import asyncio
import csv

PORT = 8088
SERVERS = [
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

def read_mem_status(pid):
    rss_kb = 0
    data_kb = 0
    try:
        with open(f"/proc/{pid}/status", "r") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    rss_kb = int(line.split()[1])
                elif line.startswith("VmData:"):
                    data_kb = int(line.split()[1])
    except Exception:
        pass
    return rss_kb, data_kb

async def idle_worker(port, stop_event, ready_event):
    try:
        reader, writer = await asyncio.open_connection('127.0.0.1', port)
        ready_event.set()
        while not stop_event.is_set():
            await asyncio.sleep(0.5)
        writer.close()
        await writer.wait_closed()
    except Exception:
        pass

async def establish_conns(port, count):
    stop_event = asyncio.Event()
    batch_size = 500
    tasks = []
    for i in range(0, count, batch_size):
        c = min(batch_size, count - i)
        events = [asyncio.Event() for _ in range(c)]
        tasks.extend([asyncio.create_task(idle_worker(port, stop_event, events[j])) for j in range(c)])
        await asyncio.sleep(0.05)
    await asyncio.sleep(1.0)
    return stop_event, tasks

def measure_memory_progression(server_bin):
    proc = subprocess.Popen(["taskset", "-c", "0", server_bin, str(PORT)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not wait_for_server(PORT):
        proc.kill()
        return None

    time.sleep(0.3)
    pid = proc.pid

    # 0 connections baseline
    rss_0, data_0 = read_mem_status(pid)

    # 1000 connections
    stop_1k, tasks_1k = asyncio.run(establish_conns(PORT, 1000))
    rss_1k, data_1k = read_mem_status(pid)
    stop_1k.set()
    time.sleep(0.5)

    # Clean kill & restart to test 5000 from fresh baseline
    proc.send_signal(signal.SIGTERM)
    proc.wait()

    proc = subprocess.Popen(["taskset", "-c", "0", server_bin, str(PORT)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    wait_for_server(PORT)
    time.sleep(0.3)
    pid = proc.pid

    # 5000 connections
    stop_5k, tasks_5k = asyncio.run(establish_conns(PORT, 5000))
    rss_5k, data_5k = read_mem_status(pid)
    stop_5k.set()

    proc.send_signal(signal.SIGTERM)
    proc.wait()

    bytes_per_conn = round(((rss_5k - rss_0) * 1024.0) / 5000.0, 1)

    return {
        "rss_0_kb": rss_0, "data_0_kb": data_0,
        "rss_1k_kb": rss_1k, "data_1k_kb": data_1k,
        "rss_5k_kb": rss_5k, "data_5k_kb": data_5k,
        "bytes_per_conn": bytes_per_conn
    }

def main():
    os.makedirs("results", exist_ok=True)
    csv_file = "results/exp3_memory_breakdown.csv"
    results = []

    print("\n--- Running Experiment 3: VmRSS & VmData Memory Allocation Breakdown ---")
    print(f"{'Server':<22} | {'0 Conns RSS':<12} | {'1k Conns RSS':<12} | {'5k Conns RSS':<12} | {'Bytes/Conn':<12} | {'Cause'}")
    print("-" * 100)

    causes = {
        "server_poll": "Dynamic struct pollfd array (8B/conn) + 4KB stack buffer",
        "epoll_lt_server": "Static client_states[65536] wbuf (4112B/conn touched in BSS)",
        "epoll_et_server": "Static client_states[65536] wbuf (4112B/conn touched in BSS)",
        "epoll_lt_lean_server": "Pointer table (8B/conn); zero heap unless partial write occurs",
        "io_uring_opt_server": "Provided buffer ring (8192 * 4KB = 32MB) + ring buffers"
    }

    for server in SERVERS:
        bin_path = os.path.join("bin", server)
        m = measure_memory_progression(bin_path)
        if m:
            c = causes.get(server, "N/A")
            print(f"{server:<22} | {m['rss_0_kb']:<12} | {m['rss_1k_kb']:<12} | {m['rss_5k_kb']:<12} | {m['bytes_per_conn']:<12} | {c[:35]}")
            results.append({
                "server": server,
                "rss_0_kb": m["rss_0_kb"],
                "data_0_kb": m["data_0_kb"],
                "rss_1k_kb": m["rss_1k_kb"],
                "data_1k_kb": m["data_1k_kb"],
                "rss_5k_kb": m["rss_5k_kb"],
                "data_5k_kb": m["data_5k_kb"],
                "bytes_per_conn": m["bytes_per_conn"],
                "cause": c
            })

    with open(csv_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["server", "rss_0_kb", "data_0_kb", "rss_1k_kb", "data_1k_kb", "rss_5k_kb", "data_5k_kb", "bytes_per_conn", "cause"])
        writer.writeheader()
        writer.writerows(results)

    print(f"\nSaved Experiment 3 memory breakdown to {csv_file}")

if __name__ == "__main__":
    main()
