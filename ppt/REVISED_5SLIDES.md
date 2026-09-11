# Revised 5-Slide Presentation Structure (Strict Course Format)

**Project Title**: Scalable Network I/O: From select to io_uring  
**Course**: CS331 - Computer Networks  
**Team ID**: `T002` | **Project ID**: `13`  
**Team Members**: Suchith (`24110313`), Rohith (`24110303`), Harshith (`24110091`), Hanook (`24110378`)  

---

## SLIDE 1: Problem Statement & Objectives

### Team & Project Info
- **Course**: CS331 | **Team ID**: T002 | **Project ID**: 13
- **Title**: Scalable Network I/O: From select to io_uring
- **Team**: Suchith (24110313), Rohith (24110303), Harshith (24110091), Hanook (24110378)

### Problem Statement
- Traditional network servers spawn a dedicated OS thread per client (thread-per-client model).
- At high connection concurrency (**C10K problem**), thread stack allocation (~8MB per thread) exhausts RAM and CPU context-switching thrashing collapses system throughput.

### Objectives
1. Build 5 standalone C TCP Echo Servers comparing: Blocking Baseline, `select()`, `poll()`, `epoll()` (Edge-Triggered), and `io_uring`.
2. Transition from $O(N)$ synchronous readiness notification to $O(1)$ kernel event queues and zero-syscall completion rings.
3. Benchmark and profile throughput (req/s), p99 latency, RAM RSS memory, and system call overhead across 10 to 5,000+ concurrent connections.

---

## SLIDE 2: Architecture & Mechanism — Design & How It Works

```
[1] Blocking (Thread-per-Client)  --> Thread stack overhead & context-switching bottleneck
[2] select()                      --> Synchronous bitmasks, O(N) scan, hard-capped at FD_SETSIZE (1024)
[3] poll()                        --> Dynamic struct pollfd array, removes 1024 cap, O(N) array scan
[4] epoll() (Edge-Triggered)      --> In-kernel Red-Black Tree + O(1) Ready List queue (EPOLLET)
[5] io_uring                      --> Shared lockless SQ / CQ Ring Buffers, Zero-Syscall Async I/O
```

### Core System Design (`/code`)
- **Shared Utilities (`include/common.h`)**: Socket listener creation (`make_listener`), `SO_REUSEADDR`/`SO_REUSEPORT`, and non-blocking setters (`set_nonblocking`).
- **Engine Implementations (`src/`)**: Clean C servers (`server_blocking.c`, `server_select.c`, `server_poll.c`, `server_epoll.c`, `server_uring.c`).
- **Build Pipeline (`Makefile`)**: GCC compilation with `-O3 -Wall -Wextra -luring`.

---

## SLIDE 3: Extension / Issues Fixed / Evaluation & Results

### Extensions & Custom Tooling Built
- **Automated Verification Harness (`scripts/test_servers.py`)**: Python test suite verifying TCP payload echo integrity & clean socket teardown (**100% Pass Rate across 5/5 servers**).
- **High-Concurrency Benchmarking Engine (`scripts/benchmark.py`)**: Custom non-blocking `asyncio` client harness testing parallel connection scaling from 10 to 5,000+ sockets.

### Bugs & Critical Issues Resolved
1. **Thread Exhaustion Fix**: Fixed `benchmark.py` crash on 5,000 threads by refactoring load generator from OS threads to Python `asyncio` non-blocking socket loops.
2. **`select()` Safety Guard**: Added descriptor bounds check (`if (client_fd >= FD_SETSIZE) close(client_fd);`) to prevent bitmask overflow memory corruption past 1024 sockets.
3. **Edge-Triggered Buffer Drain**: Implemented strict non-blocking loops in `server_epoll.c` reading/accepting until `EAGAIN` to prevent socket data starvation.

### Empirical Results Summary Table

| Server Engine | 10 Conns | 500 Conns | 1,000 Conns | 5,000 Conns | Key Evaluation Result |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`blocking`** | 27,431 req/s | 37,707 req/s | 37,883 req/s | 32,373 req/s | High memory footprint (~12.4 MB RSS) |
| **`select()`** | **89,682 req/s** | 117,831 req/s | 87,445 req/s | *Exceeded limit* | Hard-capped at `FD_SETSIZE = 1024` FDs |
| **`poll()`** | 78,590 req/s | **123,672 req/s** | **108,819 req/s** | **77,367 req/s** | $O(N)$ array scanning CPU penalty |
| **`epoll()`** | 75,667 req/s | 79,541 req/s | 71,059 req/s | 56,459 req/s | Stable $O(1)$ event queue (~1.5 MB RSS) |
| **`io_uring`** | 65,636 req/s | 70,026 req/s | 64,213 req/s | 46,399 req/s | Zero per-I/O system call overhead |

---

## SLIDE 4: Non-Functional Testing Parameters

1. **Performance (Throughput & Latency)**:
   - Peak throughput achieved by `poll()` and `select()` at medium connection scale (~123k req/s).
   - Lowest latency variance maintained by `epoll()` Edge-Triggered mode.
2. **Scalability (Concurrency Capacity)**:
   - Evaluated connection scaling from 10 to 5,000 active persistent connections.
   - `select()` fails strictly past 1024 descriptors, whereas `poll()`, `epoll()`, and `io_uring` scale past 5,000 connections smoothly.
3. **Reliability & Data Integrity**:
   - 100% functional test pass rate (`test_servers.py`) ensuring zero payload corruption, zero memory leaks, and clean TCP FIN socket closures.
4. **Memory Footprint Efficiency (RSS)**:
   - Thread-per-client baseline consumed **~12.4 MB RSS** at high load.
   - `epoll()` maintained a sleek **~1.5 MB RSS** footprint due to kernel Red-Black tree efficiency.

---

## SLIDE 5: Challenges Faced & Key Lessons

1. **System Descriptor Limits (`ulimit -n`)**:
   - *Challenge*: OS default open file descriptor limit (1024) blocked load generation.
   - *Solution*: Tuned kernel resource limits via `ulimit -n 65535`.
2. **Edge-Triggered Notification Misses in `epoll()`**:
   - *Challenge*: `EPOLLET` mode stopped notifying when unread bytes remained in socket buffers.
   - *Solution*: Re-architected read and accept loops to execute non-blocking operations continuously until `EAGAIN` / `EWOULDBLOCK`.
3. **Completion Ring Lifecycle Management in `io_uring`**:
   - *Challenge*: Managing asynchronous SQE preparation and CQE cleanup without dropping events.
   - *Solution*: Implemented batch CQE harvesting (`io_uring_peek_batch_cqe`) and explicit SQE re-arming for incoming connections.
4. **Benchmarking Harness Thread Overhead**:
   - *Challenge*: Python threading load generator hit OS `can't start new thread` limits at 5,000 connections.
   - *Solution*: Upgraded benchmarking harness to non-blocking `asyncio` event loops.
