# CS331 Course Project: Scalable Network I/O — From `select` to `io_uring`

## 📋 Project Information

- **Project Title**: Scalable Network I/O: From `select` to `io_uring`
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
├── AI_Used/                       # Course AI Disclosure & Transparency Documentation
│   ├── Tools.md                   # AI tools & technical environment
│   ├── Prompts.md                 # Representative prompt dialogs
│   ├── Step_By_Step.md            # Stage-by-stage human-AI collaboration pipeline
│   └── Thought_Process.md         # Engineering philosophy & design decisions
├── code/                          # Source code, Makefile & Benchmarking Harness
│   ├── include/
│   │   └── common.h               # Shared socket options, listener creation & non-blocking setters
│   ├── src/
│   │   ├── server_blocking.c      # Baseline: Multi-threaded (thread-per-client) TCP echo server
│   │   ├── server_select.c        # Level 1: select() event loop (O(N), compile-time FD_SETSIZE limit = 1024)
│   │   ├── server_poll.c          # Level 2: poll() event loop (O(N) pollfd array, bounded by RLIMIT_NOFILE)
│   │   ├── server_epoll.c         # Level 3: epoll Edge-Triggered event loop (O(K) ready-list processing)
│   │   └── server_uring.c         # Level 4: io_uring batched async completion ring server
│   ├── scripts/
│   │   ├── test_servers.py        # Functional echo correctness harness
│   │   ├── benchmark.py           # Non-blocking asyncio load tester (10 to 5000+ conns)
│   │   └── plot_results.py        # Matplotlib visualization chart generator (3 empirical charts)
│   ├── results/                   # JSON logs, CSV data summary, and generated PNG charts
│   └── Makefile                   # Compilation script (-O3 -Wall -Wextra -luring)
├── report/                        # Final Academic Benchmark Report
│   └── final_report.md            # Comprehensive project report
└── ppt/                           # Presentation Slides Content & Guides
```

---

## 🚀 Quick Start Guide

### 1. Prerequisites
Ensure `gcc`, `make`, `liburing-dev`, and `python3-matplotlib` are installed on Linux:
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
Verify that all 5 servers process incoming connections and echo payloads accurately (basic single-client echo verification):
```bash
python3 scripts/test_servers.py
```

### 4. Running Benchmarks & Generating Visualizations
Execute the non-blocking load testing harness and plot comparative performance graphs:
```bash
python3 scripts/benchmark.py
python3 scripts/plot_results.py
```

All generated PNG plots (`throughput_vs_connections.png`, `latency_p99_vs_connections.png`, `memory_scalability.png`) will be placed in `code/results/`.

---

## 📊 Summary of Empirical Benchmark Results

| Server Engine | 10 Conns | 500 Conns | 1,000 Conns | 5,000 Conns | Key Architectural Property |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`blocking`** | 19,748 req/s | 30,030 req/s | 28,255 req/s | 24,588 req/s | Multi-threaded (thread-per-client baseline); linear latency degradation under heavy load |
| **`select()`** | 57,947 req/s | **82,816 req/s** | **82,842 req/s** | *Exceeded limit* | Single-threaded event loop; capped by compile-time `FD_SETSIZE = 1024` bitmask limit |
| **`poll()`** | **69,394 req/s** | 81,269 req/s | 78,012 req/s | **59,510 req/s** | Single-threaded $O(N)$ dynamic array with $O(1)$ swap compaction; highest throughput |
| **`epoll()`** | 55,825 req/s | 58,829 req/s | 53,120 req/s | 42,873 req/s | Single-threaded Edge-Triggered event loop; lowest p99 latency (163 ms) and VmRSS (~1.6 MB) |
| **`io_uring`** | 60,183 req/s | 52,083 req/s | 48,216 req/s | 39,767 req/s | Batched completion ring buffer; native `recv`/`send` SQEs with non-blocking kernel event loops |
