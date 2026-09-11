# CS331 Course Project: Scalable Network I/O: From select to io_uring

## 📋 Project Information

- **Project Title**: Scalable Network I/O: From select to io_uring
- **Course**: CS331 - Computer Networks
- **Team ID**: `T002`
- **Project ID**: `13`
- **Team Members**:
  - `Suchith` (Roll No: `24110313`)
  - `Rohith` (Roll No: `24110303`)
  - `Harshith` (Roll No: `24110091`)
  - `Hanook` (Roll No: `24110378`)

---

## 📁 Repository Structure

```
.
├── README.md                      # Root README (Team info, Project details & Navigation)
├── code/                          # Source code, Makefile & Benchmarking Harness
│   ├── include/
│   │   └── common.h               # Shared socket options, listener creation & non-blocking setters
│   ├── src/
│   │   ├── server_blocking.c      # Baseline: Thread-per-client TCP echo server
│   │   ├── server_select.c        # Level 1: select() event loop (O(N), FD_SETSIZE limit = 1024)
│   │   ├── server_poll.c          # Level 2: poll() event loop (O(N), dynamic pollfd array)
│   │   ├── server_epoll.c         # Level 3: epoll Edge-Triggered event loop (O(1))
│   │   └── server_uring.c         # Level 4: io_uring async completion ring server
│   ├── scripts/
│   │   ├── test_servers.py        # Functional echo correctness harness (100% pass)
│   │   ├── benchmark.py           # High-concurrency asyncio load tester (10 to 5000+ conns)
│   │   └── plot_results.py        # Matplotlib visualization chart generator
│   ├── results/                   # JSON logs, CSV data summary, and generated PNG charts
│   └── Makefile                   # Compilation script (-O3 -Wall -Wextra -luring)
├── report/                        # Final Academic Benchmark Report
│   └── final_report.md            # Comprehensive project report
└── ppt/                           # Presentation Slides
    └── presentation_slides.md     # 10-slide presentation deck
```

---

## 🚀 Quick Start Guide

### 1. Prerequisites
Ensure `gcc`, `make`, `liburing-dev`, and `python3-matplotlib` are installed:
```bash
sudo apt-get update
sudo apt-get install -y gcc make liburing-dev python3-matplotlib python3-pandas
```

### 2. Building the Code
Navigate to the `code/` directory and compile all five server executables:
```bash
cd code
make
```

### 3. Functional Correctness Test
Verify that all 5 servers process incoming connections and echo payloads accurately:
```bash
python3 scripts/test_servers.py
```

### 4. Running Benchmarks & Generating Visualizations
Execute the load testing harness and plot comparative performance graphs:
```bash
python3 scripts/benchmark.py
python3 scripts/plot_results.py
```

All generated PNG plots (`throughput_vs_connections.png`, `latency_p99_vs_connections.png`, `memory_scalability.png`, `syscall_efficiency_comparison.png`) will be placed in `code/results/`.

---

## 📊 Summary of Empirical Benchmark Results

| Server Engine | 10 Conns | 500 Conns | 1,000 Conns | 5,000 Conns | Key Architectural Property |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`blocking`** | 16,954 req/s | 21,498 req/s | 14,864 req/s | 3,984 req/s | Multi-threaded (thread-per-client); high VmRSS RAM (~26.8 MB at 5k conns) |
| **`select()`** | 24,688 req/s | 35,620 req/s | **50,907 req/s** | *Exceeded limit* | Hard-capped at compile-time `FD_SETSIZE = 1024` bitmask limit |
| **`poll()`** | **46,254 req/s** | **43,246 req/s** | 55,332 req/s | 26,569 req/s | Single-threaded $O(N)$ array scanning; minimal overhead for small FD counts |
| **`epoll()`** | 35,306 req/s | 25,304 req/s | 18,897 req/s | **28,142 req/s** | Single-threaded $O(K)$ ready-list queue; lowest VmRSS footprint (~1.5 MB) |
| **`io_uring`** | 33,371 req/s | 31,332 req/s | 29,287 req/s | 21,543 req/s | Single-threaded batched completion ring buffer; reduces syscall frequency via batching |
