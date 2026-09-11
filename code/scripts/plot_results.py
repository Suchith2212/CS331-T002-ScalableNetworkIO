#!/usr/bin/env python3
import os
import json
import matplotlib.pyplot as plt

RESULTS_DIR = "results"
JSON_PATH = os.path.join(RESULTS_DIR, "benchmark_data.json")

SERVER_LABELS = {
    "server_blocking": "Blocking (Thread/Conn)",
    "server_select": "select() O(N)",
    "server_poll": "poll() O(N)",
    "server_epoll": "epoll() O(1)",
    "server_uring": "io_uring Async Ring"
}

COLORS = {
    "server_blocking": "#e74c3c", # Red
    "server_select": "#e67e22",   # Orange
    "server_poll": "#f1c40f",     # Yellow
    "server_epoll": "#3498db",    # Blue
    "server_uring": "#2ecc71"     # Green
}

MARKERS = {
    "server_blocking": "o",
    "server_select": "s",
    "server_poll": "^",
    "server_epoll": "D",
    "server_uring": "P"
}

def load_data():
    if not os.path.exists(JSON_PATH):
        print(f"Error: {JSON_PATH} not found. Run benchmark.py first!")
        return None
    with open(JSON_PATH, "r") as f:
        return json.load(f)

def plot_throughput(data):
    plt.figure(figsize=(10, 6))
    for server, stats in data.items():
        conns = []
        tps = []
        for c_str, stat in stats.items():
            if stat.get("status") == "OK":
                conns.append(int(c_str))
                tps.append(stat.get("throughput_rps", 0))
        label = SERVER_LABELS.get(server, server)
        plt.plot(conns, tps, label=label, color=COLORS.get(server, "#333"),
                 marker=MARKERS.get(server, "o"), linewidth=2.5, markersize=8)

    plt.title("TCP Echo Server Throughput vs Concurrent Connections", fontsize=14, fontweight="bold", pad=15)
    plt.xlabel("Concurrent Connections", fontsize=12)
    plt.ylabel("Throughput (Requests / sec)", fontsize=12)
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.legend(fontsize=11)
    plt.tight_layout()
    out_file = os.path.join(RESULTS_DIR, "throughput_vs_connections.png")
    plt.savefig(out_file, dpi=300)
    plt.close()
    print(f"Generated chart: {out_file}")

def plot_latency(data):
    plt.figure(figsize=(10, 6))
    for server, stats in data.items():
        conns = []
        lats = []
        for c_str, stat in stats.items():
            if stat.get("status") == "OK":
                conns.append(int(c_str))
                lats.append(stat.get("latency_p99_ms", 0))
        label = SERVER_LABELS.get(server, server)
        plt.plot(conns, lats, label=label, color=COLORS.get(server, "#333"),
                 marker=MARKERS.get(server, "o"), linewidth=2.5, markersize=8)

    plt.title("99th Percentile Latency vs Concurrent Connections", fontsize=14, fontweight="bold", pad=15)
    plt.xlabel("Concurrent Connections", fontsize=12)
    plt.ylabel("p99 Latency (ms)", fontsize=12)
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.legend(fontsize=11)
    plt.tight_layout()
    out_file = os.path.join(RESULTS_DIR, "latency_p99_vs_connections.png")
    plt.savefig(out_file, dpi=300)
    plt.close()
    print(f"Generated chart: {out_file}")

def plot_memory(data):
    plt.figure(figsize=(10, 6))
    for server, stats in data.items():
        conns = []
        mem_mb = []
        for c_str, stat in stats.items():
            if stat.get("status") == "OK":
                conns.append(int(c_str))
                mem_mb.append(stat.get("memory_rss_kb", 0) / 1024.0)
        label = SERVER_LABELS.get(server, server)
        plt.plot(conns, mem_mb, label=label, color=COLORS.get(server, "#333"),
                 marker=MARKERS.get(server, "o"), linewidth=2.5, markersize=8)

    plt.title("Memory Footprint (RSS MB) vs Concurrent Connections", fontsize=14, fontweight="bold", pad=15)
    plt.xlabel("Concurrent Connections", fontsize=12)
    plt.ylabel("Memory RSS (MB)", fontsize=12)
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.legend(fontsize=11)
    plt.tight_layout()
    out_file = os.path.join(RESULTS_DIR, "memory_scalability.png")
    plt.savefig(out_file, dpi=300)
    plt.close()
    print(f"Generated chart: {out_file}")

def plot_syscall_complexity():
    plt.figure(figsize=(9, 5))
    servers = ["Blocking", "select()", "poll()", "epoll()", "io_uring"]
    complexity_scores = [100, 85, 70, 25, 5]  # Conceptual relative syscall overhead per 10k ops
    colors = ["#e74c3c", "#e67e22", "#f1c40f", "#3498db", "#2ecc71"]

    bars = plt.bar(servers, complexity_scores, color=colors, width=0.55, edgecolor="black")
    plt.title("Theoretical Architectural Syscall Complexity per 10k IO Ops", fontsize=13, fontweight="bold", pad=15)
    plt.ylabel("Normalized Syscall Complexity (%)", fontsize=11)
    plt.grid(axis="y", linestyle="--", alpha=0.6)

    for bar in bars:
        yval = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2.0, yval + 1.5, f"{yval}%", ha='center', va='bottom', fontweight='bold')

    plt.ylim(0, 115)
    plt.tight_layout()
    out_file = os.path.join(RESULTS_DIR, "syscall_efficiency_comparison.png")
    plt.savefig(out_file, dpi=300)
    plt.close()
    print(f"Generated chart: {out_file}")

def main():
    data = load_data()
    if not data:
        return
    plot_throughput(data)
    plot_latency(data)
    plot_memory(data)
    plot_syscall_complexity()
    print("\nAll 4 benchmark plots successfully generated!")

if __name__ == "__main__":
    main()
