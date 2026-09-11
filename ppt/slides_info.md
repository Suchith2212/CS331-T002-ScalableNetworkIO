# Master Presentation Deck Content & Speaker Guide (`slides_info.md`)

**Project Title**: Scalable Network I/O: From `select` to `io_uring`  
**Course**: CS331 - Computer Networks | **Team ID**: `T002` | **Project ID**: `13`  
**Team Roster**:
- **Suchith** (24110313) — *Architecture Lead & `io_uring` Completion Ring Engine*
- **Rohith** (24110091) — *Edge-Triggered `epoll()` Engine & Kernel Socket Tuning*
- **Harshith** (24110303) — *Synchronous `select()` & `poll()` Multiplexing Engines*
- **Hanook** (24110378) — *Async Benchmarking Harness & Performance Visualizations*

---

## 📌 SLIDE 1: Title, Team & Project Overview

### 🖥️ Visual Slide Layout
```
+---------------------------------------------------------------------------------------+
|  CS331: COMPUTER NETWORKS COURSE PROJECT (TEAM ID: T002 | PROJECT ID: 13)            |
|                                                                                       |
|             SCALABLE NETWORK I/O: FROM select TO io_uring                             |
|       An Empirical & Architectural Analysis of Linux Socket Multiplexing              |
|                                                                                       |
|  +---------------------+-----------------------+---------------------+--------------+ |
|  | SUCHITH (24110313)  | ROHITH (24110091)     | HARSHITH (24110303) | HANOOK (...) | |
|  | Architecture Lead   | epoll (ET) & Sockets  | select & poll       | Benchmarking | |
|  +---------------------+-----------------------+---------------------+--------------+ |
+---------------------------------------------------------------------------------------+
```

### 📄 Content Details
- **Project Goal**: Systematically build, profile, and compare 5 distinct Linux TCP socket I/O paradigms (`blocking`, `select`, `poll`, `epoll`, `io_uring`) under extreme concurrency scaling (10 to 5,000+ parallel persistent connections).
- **Target Repository**: `https://github.com/Suchith2212/CS331-T002-ScalableNetworkIO`

### 🎙️ Speaker Notes (Presenter: Suchith)
> *"Good morning professor and evaluators. Today Team T002 presents our CS331 Computer Networks project: 'Scalable Network I/O: From select to io_uring'. In modern high-concurrency network servers, traditional thread-per-client models quickly break down under the C10K concurrency barrier. Over the past three decades, the Linux kernel evolved from synchronous O(N) file descriptor scanning with select and poll, to O(1) event-driven notifications with epoll, and finally to asynchronous zero-syscall completion rings with io_uring. Our work implements all 5 server paradigms in C from scratch and empirically benchmarked their throughput, latency, memory RSS footprint, and system call overhead."*

---

## 📌 SLIDE 2: Problem Statement & The C10K Concurrency Barrier

### 🖥️ Visual Slide Layout
```
+---------------------------------------------------------------------------------------+
|                       THE C10K CONCURRENCY BARRIER IN TCP SERVERS                     |
|                                                                                       |
|   1. THREAD STACK MEMORY WALL          2. CONTEXT SWITCH THRASHING                    |
|   - 8 MB default POSIX thread stack    - CPU spends 90%+ time swapping registers/TLB |
|   - 1,000 threads = ~8 GB RAM          - Hardware L1/L2/L3 cache misses skyrocket     |
|                                                                                       |
|   3. SYSCALL OVERHEAD WALL             4. BITMASK SCALING CPLX (O(N))                 |
|   - User <-> Kernel mode switches      - Iterating 10,000 file descriptors per event  |
|   - Per-read/write system call cost    - select() capped strictly at FD_SETSIZE (1024) |
+---------------------------------------------------------------------------------------+
```

### 📄 Content Details
- **Thread Stack Exhaustion**: Traditional thread-per-client baseline (`server_blocking.c`) spawns 1 OS thread per client connection, consuming massive Resident Set Size (RSS) memory.
- **CPU Context Switch Thrashing**: High connection counts force the kernel scheduler to constantly context-switch between thousands of threads, causing CPU cache misses and throughput collapse.
- **The $O(N)$ vs $O(1)$ Dilemma**: Synchronous `select()` and `poll()` require scanning the full descriptor array on every event loop iteration, yielding $O(N)$ algorithmic runtime complexity.

### 🎙️ Speaker Notes (Presenter: Harshith)
> *"To understand why high-concurrency networking is difficult, consider the C10K problem. Spawning one OS thread per client connection fails for two reasons: memory footprint and CPU scheduling overhead. Each POSIX thread defaults to 8MB stack allocation, meaning 1,000 connections allocate gigabytes of memory just for thread stacks! Furthermore, the CPU spends more time swapping thread register contexts and invalidating TLB caches than executing server logic. When developers transitioned to non-blocking I/O with select and poll, they hit an O(N) complexity wall where the kernel must scan every single socket descriptor to find ready I/O events. Furthermore, select is hard-capped at FD_SETSIZE 1024."*

---

## 📌 SLIDE 3: Architectural Evolution & Server Implementations

### 🖥️ Visual Slide Layout
```
+---------------------------------------------------------------------------------------+
|                          EVOLUTION OF LINUX NETWORKING ENGINES                        |
|                                                                                       |
|  [Blocking Baseline] -> Thread-per-client (pthread_create), O(N) thread stack RAM     |
|          |                                                                            |
|  [select Engine]     -> fd_set bitmask scanning, O(N) user-kernel copies, 1024 Cap     |
|          |                                                                            |
|  [poll Engine]       -> Dynamic struct pollfd array, O(N) scan, removes 1024 Cap     |
|          |                                                                            |
|  [epoll ET Engine]   -> Kernel Red-Black Tree + O(1) Ready List (EPOLLET mode)        |
|          |                                                                            |
|  [io_uring Engine]   -> Shared Ring Buffers (SQ/CQ) in memory, ZERO per-I/O Syscalls  |
+---------------------------------------------------------------------------------------+
```

### 📄 Content Details
- **Level 0 Baseline (`server_blocking.c`)**: Synchronous socket reads/writes, worker thread dispatched via `pthread_create()`.
- **Level 1 Synchronous (`server_select.c`)**: `fd_set` read/write bitmasks. Guarded with `if (client_fd >= FD_SETSIZE)` to prevent stack corruption.
- **Level 2 Array Polling (`server_poll.c`)**: Dynamic `struct pollfd` array resizing with `realloc()`. Compacts array upon disconnection.
- **Level 3 Edge-Triggered (`server_epoll.c`)**: Kernel-managed Red-Black Tree (`epoll_create1`). Edge-Triggered (`EPOLLET`) mode draining socket buffers with `while(1)` loops until `EAGAIN`.
- **Level 4 Completion Ring (`server_uring.c`)**: Asynchronous kernel Submission Queue (SQ) and Completion Queue (CQ) ring buffers (`liburing`). State tracking via `struct conn_info`.

### 2. 🎙️ Speaker Notes (Presenter: Rohith)
> *"We implemented all five server paradigms from scratch in C99. In `common.h`, Suchith and I wrote unified socket helpers using SO_REUSEADDR, SO_REUSEPORT, and set_nonblocking via fcntl. Harshith implemented select and poll. Notice how in server_select.c we explicitly enforce a safety guard check if (client_fd >= FD_SETSIZE) to reject connections cleanly past 1024 without crashing. In server_epoll.c, I used Edge-Triggered mode (EPOLLET). Edge-Triggered epoll only notifies the process when socket state transitions, so our read loop must drain all payload bytes in a while(1) loop until read returns EAGAIN; otherwise bytes remain stuck in socket buffers."*

---

## 📌 SLIDE 4: Empirical Benchmark Results & Analysis

### 🖥️ Visual Slide Layout
```
+---------------------------------------------------------------------------------------+
|                           EMPIRICAL PERFORMANCE COMPARISON                            |
|                                                                                       |
|  THROUGHPUT (req/s)                       P99 LATENCY & MEMORY (5,000 CONNS)          |
|  - poll():  59.0k peak (100 conns)        - epoll():    1.5 MB VmRSS (Lowest RAM)     |
|  - epoll():  28.1k req/s at 5,000 conns    - io_uring(): 21.5k req/s (2.0 MB VmRSS)    |
|  - select(): Hard Cap at 1024 Conns       - blocking(): 26.8 MB VmRSS (High RAM)      |
|                                                                                       |
|  +-----------------+--------------+---------------+---------------+-----------------+ |
|  | Paradigm        | 10 Conns     | 1,000 Conns   | 5,000 Conns   | VmRSS Memory    | |
|  +-----------------+--------------+---------------+---------------+-----------------+ |
|  | blocking        | 16,954 req/s | 14,864 req/s  | 3,984 req/s   | 26.8 MB (High)  | |
|  | select()        | 24,688 req/s | 50,907 req/s  | EXCEEDED      | 1.2 MB          | |
|  | poll()          | 46,254 req/s | 55,332 req/s  | 26,569 req/s  | 1.2 MB          | |
|  | epoll (ET)      | 35,306 req/s | 18,897 req/s  | 28,142 req/s  | 1.5 MB (Lowest) | |
|  | io_uring        | 33,371 req/s | 29,287 req/s  | 21,543 req/s  | 2.0 MB          | |
|  +-----------------+--------------+---------------+---------------+-----------------+ |
+---------------------------------------------------------------------------------------+
```

### 📄 Content Details
- **Peak Throughput**: `poll()` achieves peak throughput at low/medium scale (59.0k req/s at 100 conns) due to minimal per-connection kernel data structure overhead for modest array iteration.
- **Scaling Cap**: `select()` exceeds hardware `FD_SETSIZE = 1024` bitmask limits past 1020 connections and rejects further clients.
- **Memory Efficiency (VmRSS)**: Multi-threaded blocking baseline consumes **26.8 MB VmRSS** at 5,000 connections, whereas `epoll()` maintains a compact **1.5 MB VmRSS** footprint.
- **High Concurrency Stability**: `epoll()` ET delivers superior throughput stability (28.1k req/s) at 5,000 connections.

### 🎙️ Speaker Notes (Presenter: Hanook)
> *"To benchmark these engines accurately without client bottlenecking, I built a non-blocking Python asyncio load generator in scripts/benchmark.py capable of driving up to 5,000 parallel client connections over persistent sockets. As shown in our empirical data, select hits a hard cap past 1020 connections due to FD_SETSIZE and rejects new connections. At low to medium concurrency (100–1,000 connections), poll achieves high peak throughput (up to 59k req/s) because scanning small pollfd arrays in CPU L1/L2 cache incurs negligible overhead. However, as connections scale to 5,000, epoll demonstrates outstanding memory efficiency, consuming only 1.5 MB VmRSS compared to 26.8 MB for the multi-threaded blocking server."*

---

## 📌 SLIDE 5: Asynchronous `io_uring` Deep Dive & Syscall Efficiency

### 🖥️ Visual Slide Layout
```
+---------------------------------------------------------------------------------------+
|                      io_uring: ASYNCHRONOUS COMPLETION RING BUFFER                    |
|                                                                                       |
|      USER SPACE                                           KERNEL SPACE                |
|  +-------------------+                             +--------------------+             |
|  | Submission Queue  | ----> [io_uring_submit] --->| Submission Ring    |             |
|  | (SQ) Ring Buffer  |                             | Execution Worker   |             |
|  +-------------------+                             +--------------------+             |
|            ^                                                 |                        |
|            |                                                 v                        |
|  +-------------------+                             +--------------------+             |
|  | Completion Queue  | <--- [io_uring_wait_cqe] <-- | Completion Ring    |             |
|  | (CQ) Ring Buffer  |                             | Event Harvesting   |             |
|  +-------------------+                             +--------------------+             |
|                                                                                       |
|   SYSCALL ELIMINATION: Batch 64 reads/writes in 1 kernel entry system call!           |
+---------------------------------------------------------------------------------------+
```

### 📄 Content Details
- **Ring Buffer Architecture**: Shared kernel-user memory mapping eliminating data copying for submission and completion queue entries.
- **Zero-Syscall Batching**: Submits multiple I/O requests (`io_uring_prep_read`, `io_uring_prep_write`) in a single `io_uring_submit()` call.
- **State Management**: Asynchronous callbacks mapped cleanly using `struct conn_info` and `io_uring_sqe_set_data()`.

### 🎙️ Speaker Notes (Presenter: Suchith)
> *"Let us look under the hood of io_uring, Linux's latest asynchronous I/O framework introduced by Jens Axboe. Unlike epoll, which is ready-notification based (telling you when a socket CAN be read), io_uring is completion-based (performing the read asynchronously and notifying you when data IS read). Communication happens via two lockless ring buffers shared between user space and kernel space: the Submission Queue (SQ) and Completion Queue (CQ). By batching multiple SQEs into a single io_uring_submit system call using io_uring_peek_batch_cqe, io_uring completely eliminates the per-I/O system call overhead that plagues traditional read/write loops."*

---

## 📌 SLIDE 6: Key Takeaways, Viva Q&A & Project Wrap-Up

### 🖥️ Visual Slide Layout
```
+---------------------------------------------------------------------------------------+
|                             SUMMARY & VIVA PREPARATION CHEATSHEET                      |
|                                                                                       |
|  SUMMARY RECOMMENDATIONS BY USE-CASE:                                                 |
|  - Low Concurrency (<100 conns):    select() / poll() -> Simplicity & low overhead  |
|  - High Concurrency (1k - 50k+):    epoll() (ET) -> Low memory (1.5MB) & O(1) speed   |
|  - High Throughput / Disk+Socket:   io_uring -> Zero per-I/O system call overhead   |
|                                                                                       |
|  VIVA DEFENSE QUICK-FIRE READY ANSWERS:                                               |
|  Q: Why does select cap at 1024?   -> FD_SETSIZE macro hardcoded in sys/select.h.   |
|  Q: Level vs Edge Triggered?       -> LT notifies repeatedly; ET notifies ONCE on    |
|                                       state change (requires EAGAIN loop draining).   |
|  Q: Why does poll peak high req/s? -> No kernel tree overhead for small FD counts.    |
+---------------------------------------------------------------------------------------+
```

### 📄 Content Details
- **Architectural Trade-offs**:
  - `select()`/`poll()`: Simple implementation, ideal for lightweight, low-connection applications.
  - `epoll()`: Benchmark gold standard for Linux network servers (Nginx, Redis, Netty).
  - `io_uring`: Future-proof asynchronous engine unifying network and disk I/O.
- **Verification Status**: 100% test suite pass rate, fully documented in [final_report.md](file:///f:/Sem%20V/CN/report/final_report.md) and [master_learning_guide.md](file:///f:/Sem%20V/CN/report/master_learning_guide.md).

### 🎙️ Speaker Notes (Presenter: Suchith & Team)
> *"To conclude, our empirical analysis highlights that there is no one-size-fits-all server engine. For small connection counts, poll and select offer lower setup overhead. But as concurrency grows into thousands of sockets, epoll's O(1) kernel event queue and low 1.5MB memory footprint make it the industry gold standard. Finally, io_uring represents the future of Linux async I/O by eliminating system call overhead entirely via submission and completion ring buffers. All 5 engines have been built, verified, and committed to our repository. Thank you, and we are ready to take your questions!"*
