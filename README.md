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

## 📊 Summary of Benchmark Results

| Server Engine | 10 Conns | 500 Conns | 1,000 Conns | 5,000 Conns | Key Architectural Property |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`blocking`** | 27,431 req/s | 37,707 req/s | 37,883 req/s | 32,373 req/s | High memory footprint (~12.4 MB RSS at 5k conns) |
| **`select()`** | **89,682 req/s** | 117,831 req/s | 87,445 req/s | *Exceeded limit* | Hard-capped at `FD_SETSIZE = 1024` descriptors |
| **`poll()`** | 78,590 req/s | **123,672 req/s** | **108,819 req/s** | **77,367 req/s** | $O(N)$ array scanning; scales past 1024 descriptors |
| **`epoll()`** | 75,667 req/s | 79,541 req/s | 71,059 req/s | 56,459 req/s | $O(1)$ ready-list event queue with minimal ~1.5 MB RSS |
| **`io_uring`** | 65,636 req/s | 70,026 req/s | 64,213 req/s | 46,399 req/s | Completion queue ring buffer; zero per-I/O syscall cost |
