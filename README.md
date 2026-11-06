# Scalable Network I/O: From `select` to `io_uring`

An empirical performance benchmarking study of Linux I/O multiplexing architectures in C, evaluating synchronous multi-threaded blocking, `select(2)`, `poll(2)`, `epoll(7)` (Level-Triggered and Edge-Triggered), and `io_uring(7)` (multishot receive with provided buffer rings). Sockets are benchmarked under active closed-loop concurrency (10 to 5,000 connections) and idle scaling (0 to 10,000 idle connections) using an in-tree multi-threaded C load generator to evaluate throughput, p99 tail latency, CPU time per request, wait batching, context switches, and kernel/user memory footprint.

---

## 📋 Project Information

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

The repository is organized into five top-level directories:

```
.
├── README.md                          # Project overview, requirements, build & execution guide
├── code/                              # All C source code, scripts, results, and technical documentation
│   ├── include/
│   │   └── common.h                   # Shared socket helpers, listener creation, non-blocking configuration
│   ├── src/                           # Server implementations in C
│   │   ├── server_blocking.c          # Baseline: Multi-threaded (thread-per-connection) TCP echo server
│   │   ├── server_select.c            # Level 1: select() event loop (O(N), bounded by FD_SETSIZE = 1024)
│   │   ├── server_poll.c              # Level 2: poll() event loop (O(N) pollfd array compaction)
│   │   ├── server_epoll.c             # Level 3: Original epoll baseline server
│   │   ├── epoll_lt_server.c          # Level 3 (Optimized): Level-Triggered epoll with 1024-event buffer
│   │   ├── epoll_et_server.c          # Level 3 (Optimized): Edge-Triggered epoll with short-read drain
│   │   ├── epoll_lt_lean_server.c     # Level 3 (Lean): Sparse pointer table for minimal RSS footprint
│   │   ├── server_uring.c             # Level 4: Original io_uring baseline server
│   │   ├── io_uring_opt_server.c      # Level 4 (Optimized): io_uring multishot recv + provided buffer ring
│   │   ├── reference_server.c         # Reference epoll server for load generator calibration
│   │   ├── epoll_server_v1.c          # Preserved baseline snapshot of epoll server
│   │   └── io_uring_server_v1.c       # Preserved baseline snapshot of io_uring server
│   ├── loadgen/
│   │   └── loadgen.c                  # High-headroom multi-threaded C load generator with core pinning
│   ├── scripts/                       # Correctness tests and automated benchmark suites
│   │   ├── test_servers.py            # Quick functional echo test for all server binaries
│   │   ├── test_new_loadgen.py        # Correctness test running bin/loadgen against all servers
│   │   ├── task1_bottleneck_check.py  # Diagnostic measuring per-thread CPU on the legacy Python client
│   │   ├── task3_calibration.py       # Client thread calibration against reference_server
│   │   ├── task4_scenario1.py         # Scenario 1: Active concurrency sweep (10 to 5,000 conns)
│   │   ├── task4_cpu_per_req.py       # Scenario 1: CPU us/req, ticks, and context switch measurement
│   │   ├── task4_events_per_wait.py   # Events per wakeup & waits per request using -DSTATS
│   │   ├── task4_idle_sweep.py        # Scenario 2: Idle connection sweep (0 to 10,000 idle)
│   │   ├── task6_memory.py            # Memory profiling (smaps_rollup VmRSS/Pss + sockstat TCP memory)
│   │   ├── run_all_remaining.sh       # Automated pipeline executing 4(c), 4(d), and 6
│   │   ├── benchmark.py               # Legacy Python asyncio benchmark harness
│   │   ├── plot_results.py            # Legacy Matplotlib chart generator
│   │   └── strace_check.sh            # Syscall profiling with strace
│   ├── results/                       # Empirical datasets (CSV, JSON) and generated comparison plots
│   │   ├── s1_new_client.csv          # Authoritative Scenario 1 active concurrency sweep
│   │   ├── cpu_per_req_new_client.csv # Authoritative CPU cost and context switch dataset
│   │   ├── events_per_wait_new_client.csv # Batching efficiency and event-to-wait ratios
│   │   ├── idle_sweep_new_client.csv  # Idle connection scaling dataset (0-10k idle)
│   │   ├── idle_sweep_new_client_throughput.png # Idle throughput plot with error bars
│   │   ├── idle_sweep_new_client_latency.png    # Idle p99 tail latency plot with error bars
│   │   ├── memory_new.csv             # Full memory accounting (User RSS/Pss + Kernel TCP socket memory)
│   │   ├── client_bottleneck_check.csv# Proof of client saturation in legacy load generator
│   │   └── calibration.csv            # C load generator thread calibration results
│   ├── docs/                          # Detailed engineering logs and research findings
│   │   ├── FINDINGS_v2.md             # Authoritative technical analysis of client bottleneck & benchmark v2
│   │   ├── FINDINGS.md                # Phase 1 follow-up experiment findings
│   │   └── CHANGES.md                 # Engineering changelog of epoll & io_uring optimizations
│   └── Makefile                       # Build system for standard and instrumented (-DSTATS) targets
├── report/                            # Academic Project Report
│   ├── FINAL_REPORT.pdf               # Deliverable project report (PDF)
│   └── final_report.md                # Report source markdown
├── ppt/                               # Presentation Slides
│   └── Final_Presentation.pptx        # Final project presentation slides
└── ai/                                # AI Disclosure, Prompts, and Session Transcripts
    ├── README.md                      # Overview of AI usage and tooling disclosure
    ├── prompts/                       # Milestone prompt logs (01 to 04)
    └── conversations/                 # Interactive session transcripts
```

---

## ⚙️ System Requirements & Environment

Measurements were conducted under the following validated environment:
- **Operating System**: Linux `6.6.87.2-microsoft-standard-WSL2` (Ubuntu 24.04 LTS x86_64)
- **Compiler**: `gcc 13.3.0` (`Ubuntu 13.3.0-6ubuntu2~24.04.1`)
- **liburing**: `liburing 2.5` (`pkg-config --modversion liburing`)
- **Required Packages**:
  ```bash
  sudo apt-get update
  sudo apt-get install -y gcc make liburing-dev python3 python3-matplotlib python3-pandas sysstat
  ```
- **Process Resource Limit**:
  ```bash
  ulimit -n 65536
  ```

---

## 🛠️ Build Guide

To build all server implementations and the native load generator, navigate to `code/`:

```bash
cd code

# Build all standard optimized server binaries and loadgen (-O3 -Wall -Wextra)
make

# Build instrumented binaries for event/wait statistics (-DSTATS)
make stats

# Clean compiled binaries
make clean
```

The compiled executables will be placed in `code/bin/`:
- `bin/server_blocking`
- `bin/server_select`
- `bin/server_poll`
- `bin/server_epoll`
- `bin/epoll_lt_server`
- `bin/epoll_et_server`
- `bin/epoll_lt_lean_server`
- `bin/server_uring`
- `bin/io_uring_opt_server`
- `bin/reference_server`
- `bin/loadgen`

---

## 🧪 Testing & Execution

### 1. Functional Echo Correctness Test
To verify that all 10 servers correctly accept TCP connections and echo exact payloads without error:
```bash
cd code
python3 scripts/test_servers.py
```

To run an end-to-end multi-connection verification using the C load generator:
```bash
cd code
python3 scripts/test_new_loadgen.py
```

### 2. Running an Individual Server
Each server executable accepts an optional port argument (default: `8080`):
```bash
# Pin the server to CPU Core 0
taskset -c 0 code/bin/epoll_lt_server 8080
```

### 3. Running the Native Load Generator
```bash
# Example: 1,000 active connections over 2 client threads pinned to Cores 1 and 2
code/bin/loadgen --host 127.0.0.1 --port 8080 --conns 1000 --active 1000 --threads 2 --duration 10.0 --cores 1,2
```

### 4. Running Benchmark Suites
All benchmark runners are located in `code/scripts/` and automate affinity pinning, warmup, multi-trial execution, and CSV generation:

- **Active Concurrency Sweep (Scenario 1)**:
  ```bash
  bash code/scripts/exp_v2_task4a.sh
  ```
  *(Generates `code/results/s1_new_client.csv`)*

- **CPU Cost & Context Switch Profiling**:
  ```bash
  bash code/scripts/exp_v2_task4b.sh
  ```
  *(Generates `code/results/cpu_per_req_new_client.csv`)*

- **Events per Wakeup & Batching Efficiency**:
  ```bash
  bash code/scripts/exp_v2_task4c.sh
  ```
  *(Generates `code/results/events_per_wait_new_client.csv`)*

- **Idle Connection Sweep (Scenario 2, 0 to 10k Idle)**:
  ```bash
  bash code/scripts/exp_v2_task4d.sh
  ```
  *(Generates `code/results/idle_sweep_new_client.csv` and error-bar PNG plots)*

- **Memory Accounting (User RSS + Kernel Sockets)**:
  ```bash
  bash code/scripts/exp_v2_task6.sh
  ```
  *(Generates `code/results/memory_new.csv`)*

---

## 📄 Key Deliverables & Documentation

- **Final Academic Report**: [`report/FINAL_REPORT.pdf`](report/FINAL_REPORT.pdf) (Source: [`report/final_report.md`](report/final_report.md))
- **Presentation Slides**: [`ppt/Final_Presentation.pptx`](ppt/Final_Presentation.pptx)
- **Comprehensive Findings Analysis**: [`code/docs/FINDINGS_v2.md`](code/docs/FINDINGS_v2.md)
- **AI Transparency & Interaction Logs**: Documented in [`ai/`](ai/) (prompts and interactive session transcripts).
