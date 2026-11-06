#!/usr/bin/env python3
import os
import sys
import time
import subprocess
import signal
import statistics
import csv
import asyncio
import socket
import matplotlib.pyplot as plt

PORT = 8089
SERVERS = [
    "server_poll",
    "epoll_lt_server",
    "epoll_et_server",
    "io_uring_opt_server"
]
IDLE_LEVELS = [0, 500, 1000, 2000, 5000, 10000]
ACTIVE_CONNS = 100
TRIALS = 5
TRIAL_DURATION = 2 # 2 seconds per trial for snappy, stable medians

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

async def active_worker(port, stop_event, stats):
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

    stats["total"] += req_count
    stats["lats"].extend(lats)

async def idle_worker(port, stop_event, ready_event):
    try:
        reader, writer = await asyncio.open_connection('127.0.0.1', port)
        sock = writer.get_extra_info('socket')
        if sock:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        ready_event.set()
    except Exception:
        return

    while not stop_event.is_set():
        await asyncio.sleep(0.5)

    try:
        writer.close()
        await writer.wait_closed()
    except Exception:
        pass

async def run_idle_active_test(port, num_idle, num_active, duration):
    stop_event = asyncio.Event()
    stats = {"total": 0, "lats": []}

    # Step 1: establish idle connections in batches
    idle_tasks = []
    if num_idle > 0:
        batch_size = 500
        for i in range(0, num_idle, batch_size):
            curr_batch = min(batch_size, num_idle - i)
            events = [asyncio.Event() for _ in range(curr_batch)]
            batch_tasks = [
                asyncio.create_task(idle_worker(port, stop_event, events[j]))
                for j in range(curr_batch)
            ]
            idle_tasks.extend(batch_tasks)
            await asyncio.sleep(0.04)
        await asyncio.sleep(0.8)

    # Step 2: spawn active load workers
    active_tasks = [
        asyncio.create_task(active_worker(port, stop_event, stats))
        for _ in range(num_active)
    ]

    t0 = time.time()
    await asyncio.sleep(duration)
    stop_event.set()

    await asyncio.gather(*active_tasks, return_exceptions=True)
    if idle_tasks:
        await asyncio.gather(*idle_tasks, return_exceptions=True)
    t1 = time.time()

    elapsed = t1 - t0
    tps = stats["total"] / elapsed if elapsed > 0 else 0
    lats = sorted(stats["lats"])
    p99 = lats[int(len(lats) * 0.99)] if lats else 0.0

    return tps, p99

def run_single_idle_trial(server_bin, num_idle):
    proc = subprocess.Popen(["taskset", "-c", "0", server_bin, str(PORT)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not wait_for_server(PORT):
        proc.kill()
        return None, None

    time.sleep(0.3)
    try:
        tps, p99 = asyncio.run(run_idle_active_test(PORT, num_idle, ACTIVE_CONNS, TRIAL_DURATION))
    except Exception:
        tps, p99 = 0, 0
    finally:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            proc.kill()
        time.sleep(0.3)

    return tps, p99

def plot_crossover(results):
    # Separate data per server
    data_tps = {}
    data_p99 = {}
    for r in results:
        s = r["server"]
        if s not in data_tps:
            data_tps[s] = {"x": [], "y": []}
            data_p99[s] = {"x": [], "y": []}
        data_tps[s]["x"].append(r["idle_conns"])
        data_tps[s]["y"].append(r["median_req_s"])
        data_p99[s]["x"].append(r["idle_conns"])
        data_p99[s]["y"].append(r["median_p99_ms"])

    colors = {
        "server_poll": "#f1c40f",
        "epoll_lt_server": "#3498db",
        "epoll_et_server": "#9b59b6",
        "io_uring_opt_server": "#2ecc71"
    }
    labels = {
        "server_poll": "poll() O(N)",
        "epoll_lt_server": "epoll (LT)",
        "epoll_et_server": "epoll (ET)",
        "io_uring_opt_server": "io_uring (Opt)"
    }
    markers = {
        "server_poll": "o",
        "epoll_lt_server": "s",
        "epoll_et_server": "^",
        "io_uring_opt_server": "D"
    }

    # Plot 1: Throughput Crossover
    plt.figure(figsize=(10, 6))
    for s, d in data_tps.items():
        plt.plot(d["x"], d["y"], label=labels.get(s, s), color=colors.get(s, "#333"),
                 marker=markers.get(s, "o"), linewidth=2.5, markersize=8)

    # Detect crossover between server_poll and epoll_et_server
    crossover_x = None
    if "server_poll" in data_tps and "epoll_et_server" in data_tps:
        p_y = data_tps["server_poll"]["y"]
        e_y = data_tps["epoll_et_server"]["y"]
        x_vals = data_tps["server_poll"]["x"]
        for idx in range(len(x_vals) - 1):
            if (p_y[idx] >= e_y[idx] and p_y[idx+1] <= e_y[idx+1]) or (p_y[idx] <= e_y[idx] and p_y[idx+1] >= e_y[idx+1]):
                # Approximate linear interpolation for crossover
                x0, x1 = x_vals[idx], x_vals[idx+1]
                y_p0, y_p1 = p_y[idx], p_y[idx+1]
                y_e0, y_e1 = e_y[idx], e_y[idx+1]
                denom = (y_p1 - y_p0) - (y_e1 - y_e0)
                if denom != 0:
                    crossover_x = x0 + (x1 - x0) * ((y_e0 - y_p0) / (denom))
                    break

    if crossover_x and crossover_x > 0:
        plt.axvline(x=crossover_x, color="red", linestyle=":", linewidth=2, label=f"Crossover (~{int(crossover_x)} idle conns)")
        plt.annotate(f"Crossover: ~{int(crossover_x)} Idle Conns\n(epoll overtakes poll)",
                     xy=(crossover_x, (data_tps["epoll_et_server"]["y"][1] + data_tps["server_poll"]["y"][1])/2),
                     xytext=(crossover_x + 600, 80000),
                     arrowprops=dict(facecolor='red', shrink=0.05, width=1.5, headwidth=8),
                     fontsize=10, fontweight="bold", bbox=dict(boxstyle="round,pad=0.3", fc="yellow", alpha=0.3))

    plt.title("Idle Connection Sweep: Throughput (100 Active Sockets)", fontsize=14, fontweight="bold", pad=15)
    plt.xlabel("Number of Idle Connections", fontsize=12)
    plt.ylabel("Active Throughput (Requests / sec)", fontsize=12)
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.legend(fontsize=11)
    plt.tight_layout()
    tps_png = "results/exp4_idle_throughput.png"
    plt.savefig(tps_png, dpi=300)
    plt.close()
    print(f"Generated: {tps_png}")

    # Plot 2: Latency Crossover
    plt.figure(figsize=(10, 6))
    for s, d in data_p99.items():
        plt.plot(d["x"], d["y"], label=labels.get(s, s), color=colors.get(s, "#333"),
                 marker=markers.get(s, "o"), linewidth=2.5, markersize=8)

    if crossover_x and crossover_x > 0:
        plt.axvline(x=crossover_x, color="red", linestyle=":", linewidth=2, label=f"Crossover (~{int(crossover_x)} idle conns)")

    plt.title("Idle Connection Sweep: p99 Tail Latency (100 Active Sockets)", fontsize=14, fontweight="bold", pad=15)
    plt.xlabel("Number of Idle Connections", fontsize=12)
    plt.ylabel("Active p99 Latency (ms)", fontsize=12)
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.legend(fontsize=11)
    plt.tight_layout()
    lat_png = "results/exp4_idle_latency.png"
    plt.savefig(lat_png, dpi=300)
    plt.close()
    print(f"Generated: {lat_png}")

def main():
    os.makedirs("results", exist_ok=True)
    csv_file = "results/exp4_idle_sweep.csv"
    results = []

    print("\n--- Running Experiment 4: Idle Connection Sweep (100 Active, 0 to 10k Idle) ---")
    print(f"{'Server':<22} | {'Idle Conns':<12} | {'Median req/s':<14} | {'Median p99 (ms)':<16}")
    print("-" * 72)

    for server in SERVERS:
        bin_path = os.path.join("bin", server)
        for idle in IDLE_LEVELS:
            tps_list = []
            p99_list = []

            for _ in range(TRIALS):
                tps, p99 = run_single_idle_trial(bin_path, idle)
                if tps is not None and tps > 0:
                    tps_list.append(tps)
                    p99_list.append(p99)

            if tps_list:
                med_tps = round(statistics.median(tps_list), 2)
                med_p99 = round(statistics.median(p99_list), 3)
            else:
                med_tps, med_p99 = 0.0, 0.0

            print(f"{server:<22} | {idle:<12} | {med_tps:<14} | {med_p99:<16}")
            results.append({
                "server": server,
                "idle_conns": idle,
                "median_req_s": med_tps,
                "median_p99_ms": med_p99
            })

    with open(csv_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["server", "idle_conns", "median_req_s", "median_p99_ms"])
        writer.writeheader()
        writer.writerows(results)

    print(f"\nSaved Experiment 4 results to {csv_file}")
    plot_crossover(results)

if __name__ == "__main__":
    main()
