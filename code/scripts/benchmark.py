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

RESULTS_DIR = "results"
BIN_DIR = "bin"
PORT = 8080
DURATION = 5  # Benchmark duration per load level (seconds)

SERVERS = [
    "server_blocking",
    "server_select",
    "server_poll",
    "server_epoll",
    "server_uring"
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
                    parts = line.split()
                    return int(parts[1])
    except Exception:
        pass
    return 0

async def async_client_worker(port, duration, stop_event, stats):
    payload = b"PING_ECHO_PAYLOAD_1234567890\n"
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection('127.0.0.1', port), timeout=3.0
        )
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

async def run_async_load_generator(port, num_conns, duration):
    stop_event = asyncio.Event()
    stats = {"total_reqs": 0, "latencies_ms": []}

    tasks = []
    for _ in range(num_conns):
        tasks.append(asyncio.create_task(async_client_worker(port, duration, stop_event, stats)))

    start_time = time.time()
    await asyncio.sleep(duration)
    stop_event.set()

    await asyncio.gather(*tasks, return_exceptions=True)

    elapsed = time.time() - start_time
    total_reqs = stats["total_reqs"]
    throughput = total_reqs / elapsed if elapsed > 0 else 0

    latencies = sorted(stats["latencies_ms"])
    if latencies:
        p50 = latencies[int(len(latencies) * 0.50)]
        p99 = latencies[int(len(latencies) * 0.99)]
        avg_lat = sum(latencies) / len(latencies)
    else:
        p50, p99, avg_lat = 0.0, 0.0, 0.0

    return {
        "throughput_rps": round(throughput, 2),
        "latency_avg_ms": round(avg_lat, 3),
        "latency_p50_ms": round(p50, 3),
        "latency_p99_ms": round(p99, 3),
        "total_requests": total_reqs
    }

def run_load_generator(port, num_conns, duration):
    return asyncio.run(run_async_load_generator(port, num_conns, duration))

def benchmark_server(server_name, connections):
    server_bin = os.path.join(BIN_DIR, server_name)
    if not os.path.exists(server_bin):
        print(f"Skipping {server_name}: executable {server_bin} not found.")
        return {}

    server_results = {}
    print(f"\n==========================================")
    print(f" Benchmarking: {server_name}")
    print(f"==========================================")

    for conn in connections:
        if server_name == "server_select" and conn > 1020:
            print(f" Skipping {conn} connections for select() (FD_SETSIZE = 1024 limit)")
            server_results[conn] = {
                "throughput_rps": 0,
                "latency_avg_ms": 0,
                "latency_p99_ms": 0,
                "memory_rss_kb": 0,
                "status": "FD_SETSIZE_EXCEEDED"
            }
            continue

        print(f" -> Load: {conn} concurrent connections ...", end="", flush=True)

        # Launch server
        proc = subprocess.Popen([server_bin, str(PORT)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        if not wait_for_server(PORT):
            print(" FAILED to start server.")
            proc.kill()
            continue

        time.sleep(0.2)
        rss_kb = get_server_rss_kb(proc.pid)

        # Run asyncio load generator
        res = run_load_generator(PORT, conn, DURATION)

        res["memory_rss_kb"] = get_server_rss_kb(proc.pid) or rss_kb
        res["status"] = "OK"

        server_results[conn] = res

        # Kill server cleanly
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            proc.kill()

        time.sleep(0.5)

        print(f" Done. Throughput: {res['throughput_rps']} req/s, p99 Latency: {res['latency_p99_ms']} ms, RSS: {res['memory_rss_kb']} KB")

    return server_results

def main():
    ensure_dirs()
    all_results = {}

    for server in SERVERS:
        res = benchmark_server(server, CONNECTIONS)
        if res:
            all_results[server] = res

    # Write JSON output
    json_path = os.path.join(RESULTS_DIR, "benchmark_data.json")
    with open(json_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nSaved JSON results to {json_path}")

    # Write CSV summary
    csv_path = os.path.join(RESULTS_DIR, "benchmark_summary.csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Server", "Connections", "Throughput (req/s)", "p99 Latency (ms)", "Memory RSS (KB)", "Status"])
        for server, data in all_results.items():
            for conn, stats in data.items():
                writer.writerow([
                    server,
                    conn,
                    stats.get("throughput_rps", 0),
                    stats.get("latency_p99_ms", 0),
                    stats.get("memory_rss_kb", 0),
                    stats.get("status", "OK")
                ])
    print(f"Saved CSV summary to {csv_path}")

if __name__ == "__main__":
    main()
