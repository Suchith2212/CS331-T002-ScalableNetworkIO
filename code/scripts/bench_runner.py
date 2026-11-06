#!/usr/bin/env python3
import os
import sys
import time
import subprocess
import json
import csv
import socket
import signal
import asyncio
import statistics
import argparse

RESULTS_DIR = "results"
BIN_DIR = "bin"
PORT = 8080
TRIAL_DURATION = 2  # Seconds per trial (5 trials * 2s = 10s per configuration for fast, rock-solid medians)
NUM_TRIALS = 5

DEFAULT_SERVERS = [
    "server_blocking",
    "server_select",
    "server_poll",
    "epoll_lt_server",
    "epoll_et_server",
    "io_uring_opt_server"
]

CONNECTIONS = [10, 100, 500, 1000, 2000, 5000]

def ensure_dirs():
    os.makedirs(RESULTS_DIR, exist_ok=True)

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

def get_server_rss_kb(pid):
    try:
        with open(f"/proc/{pid}/status", "r") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1])
    except Exception:
        pass
    return 0

async def async_active_worker(port, stop_event, stats):
    payload = b"PING_ECHO_PAYLOAD_1234567890\n"
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection('127.0.0.1', port), timeout=3.0
        )
        sock = writer.get_extra_info('socket')
        if sock:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    except Exception:
        return

    req_count = 0
    lats = []

    while not stop_event.is_set():
        t0 = time.perf_counter()
        try:
            writer.write(payload)
            await writer.drain()
            data = await reader.read(1024)
            t1 = time.perf_counter()
            if not data:
                break
            req_count += 1
            lats.append((t1 - t0) * 1000.0)
        except Exception:
            break

    try:
        writer.close()
        await writer.wait_closed()
    except Exception:
        pass

    stats["total_reqs"] += req_count
    stats["latencies_ms"].extend(lats)

async def async_idle_worker(port, stop_event, connected_event):
    try:
        reader, writer = await asyncio.open_connection('127.0.0.1', port)
        sock = writer.get_extra_info('socket')
        if sock:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        connected_event.set()
    except Exception:
        return

    # Keep connection open and idle until stopped
    while not stop_event.is_set():
        await asyncio.sleep(0.5)

    try:
        writer.close()
        await writer.wait_closed()
    except Exception:
        pass

async def run_standard_load(port, num_conns, duration):
    stop_event = asyncio.Event()
    stats = {"total_reqs": 0, "latencies_ms": []}

    tasks = [
        asyncio.create_task(async_active_worker(port, stop_event, stats))
        for _ in range(num_conns)
    ]

    start_time = time.time()
    await asyncio.sleep(duration)
    stop_event.set()

    await asyncio.gather(*tasks, return_exceptions=True)

    elapsed = time.time() - start_time
    total_reqs = stats["total_reqs"]
    throughput = total_reqs / elapsed if elapsed > 0 else 0

    latencies = sorted(stats["latencies_ms"])
    p99 = latencies[int(len(latencies) * 0.99)] if latencies else 0.0

    return throughput, p99

async def run_idle_active_load(port, num_idle, num_active, duration):
    stop_event = asyncio.Event()
    stats = {"total_reqs": 0, "latencies_ms": []}

    # Step 1: Establish idle connections in batches
    idle_tasks = []
    batch_size = 500
    for i in range(0, num_idle, batch_size):
        curr_batch = min(batch_size, num_idle - i)
        events = [asyncio.Event() for _ in range(curr_batch)]
        batch_tasks = [
            asyncio.create_task(async_idle_worker(port, stop_event, events[j]))
            for j in range(curr_batch)
        ]
        idle_tasks.extend(batch_tasks)
        await asyncio.sleep(0.05)

    await asyncio.sleep(1.0) # Let all idle sockets stabilize

    # Step 2: Spawn active load workers
    active_tasks = [
        asyncio.create_task(async_active_worker(port, stop_event, stats))
        for _ in range(num_active)
    ]

    start_time = time.time()
    await asyncio.sleep(duration)
    stop_event.set()

    await asyncio.gather(*active_tasks, return_exceptions=True)
    await asyncio.gather(*idle_tasks, return_exceptions=True)

    elapsed = time.time() - start_time
    total_reqs = stats["total_reqs"]
    throughput = total_reqs / elapsed if elapsed > 0 else 0

    latencies = sorted(stats["latencies_ms"])
    p99 = latencies[int(len(latencies) * 0.99)] if latencies else 0.0

    return throughput, p99

def run_trial(server_bin, conn_count, is_idle_scenario=False):
    # Server pinned to core 0 with taskset
    cmd = ["taskset", "-c", "0", server_bin, str(PORT)]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    if not wait_for_server(PORT):
        proc.kill()
        return None, None, None

    time.sleep(0.2)

    try:
        if is_idle_scenario:
            tps, p99 = asyncio.run(run_idle_active_load(PORT, 10000, 100, TRIAL_DURATION))
        else:
            tps, p99 = asyncio.run(run_standard_load(PORT, conn_count, TRIAL_DURATION))
        rss_kb = get_server_rss_kb(proc.pid)
    except Exception as e:
        tps, p99, rss_kb = 0, 0, 0
    finally:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            proc.kill()
        time.sleep(0.3)

    return tps, p99, rss_kb

def benchmark_standard(servers):
    ensure_dirs()
    results = []

    print("\n--- Running Standard Concurrency Scenario (10 to 5000 Conns, 5 Trials Median) ---")
    print(f"{'Server':<22} | {'Conns':<6} | {'Median req/s':<14} | {'Median p99 (ms)':<16} | {'VmRSS (KB)':<10}")
    print("-" * 78)

    for server in servers:
        server_bin = os.path.join(BIN_DIR, server)
        if not os.path.exists(server_bin):
            continue

        for conn in CONNECTIONS:
            if server == "server_select" and conn > 1020:
                print(f"{server:<22} | {conn:<6} | {'EXCEEDED LIMIT':<14} | {'N/A':<16} | {'N/A':<10}")
                results.append({
                    "server": server, "conns": conn, "throughput_rps": 0,
                    "p99_latency_ms": 0, "rss_kb": 0, "status": "FD_SETSIZE_EXCEEDED"
                })
                continue

            tps_list = []
            p99_list = []
            rss_list = []

            for _ in range(NUM_TRIALS):
                tps, p99, rss = run_trial(server_bin, conn, is_idle_scenario=False)
                if tps is not None and tps > 0:
                    tps_list.append(tps)
                    p99_list.append(p99)
                    rss_list.append(rss)

            if tps_list:
                med_tps = round(statistics.median(tps_list), 2)
                med_p99 = round(statistics.median(p99_list), 3)
                med_rss = int(statistics.median(rss_list))
                status = "OK"
            else:
                med_tps, med_p99, med_rss = 0, 0, 0
                status = "ERROR"

            print(f"{server:<22} | {conn:<6} | {med_tps:<14} | {med_p99:<16} | {med_rss:<10}")
            results.append({
                "server": server, "conns": conn, "throughput_rps": med_tps,
                "p99_latency_ms": med_p99, "rss_kb": med_rss, "status": status
            })

    # Save to CSV
    csv_file = os.path.join(RESULTS_DIR, "bench_hygiene_summary.csv")
    with open(csv_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["server", "conns", "throughput_rps", "p99_latency_ms", "rss_kb", "status"])
        writer.writeheader()
        writer.writerows(results)

    print(f"\nSaved standard hygiene benchmark summary to {csv_file}")

def benchmark_idle(servers):
    ensure_dirs()
    print("\n--- Running Scenario 2: 10,000 Idle + 100 Active Connections (5 Trials Median) ---")
    print(f"{'Server':<22} | {'Active/Idle Conns':<18} | {'Median req/s':<14} | {'Median p99 (ms)':<16} | {'VmRSS (KB)':<10}")
    print("-" * 88)

    idle_servers = [s for s in servers if s != "server_select"]
    results = []

    for server in idle_servers:
        server_bin = os.path.join(BIN_DIR, server)
        if not os.path.exists(server_bin):
            continue

        tps_list, p99_list, rss_list = [], [], []
        for _ in range(NUM_TRIALS):
            tps, p99, rss = run_trial(server_bin, 100, is_idle_scenario=True)
            if tps is not None and tps > 0:
                tps_list.append(tps)
                p99_list.append(p99)
                rss_list.append(rss)

        if tps_list:
            med_tps = round(statistics.median(tps_list), 2)
            med_p99 = round(statistics.median(p99_list), 3)
            med_rss = int(statistics.median(rss_list))
        else:
            med_tps, med_p99, med_rss = 0, 0, 0

        print(f"{server:<22} | {'100 act / 10k idle':<18} | {med_tps:<14} | {med_p99:<16} | {med_rss:<10}")
        results.append({
            "server": server, "throughput_rps": med_tps,
            "p99_latency_ms": med_p99, "rss_kb": med_rss
        })

    csv_idle = os.path.join(RESULTS_DIR, "bench_idle_scenario.csv")
    with open(csv_idle, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["server", "throughput_rps", "p99_latency_ms", "rss_kb"])
        writer.writeheader()
        writer.writerows(results)
    print(f"Saved 10k idle scenario results to {csv_idle}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=["standard", "idle", "all"], default="all")
    args = parser.parse_args()

    if args.scenario in ["standard", "all"]:
        benchmark_standard(DEFAULT_SERVERS)
    if args.scenario in ["idle", "all"]:
        benchmark_idle(DEFAULT_SERVERS)

if __name__ == "__main__":
    main()
