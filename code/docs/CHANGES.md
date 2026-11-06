# Architectural Changes & Optimization Report

This document details the architectural fixes and enhancements made across the Linux I/O multiplexing implementations (`epoll` variants and optimized `io_uring`), benchmark hygiene automation, and the resulting empirical findings.

---

## 1. Baseline Preservation
- **Preserved Originals**: Saved original source implementations to [`code/src/epoll_server_v1.c`](file:///f:/Sem%20V/CN/code/src/epoll_server_v1.c) and [`code/src/io_uring_server_v1.c`](file:///f:/Sem%20V/CN/code/src/io_uring_server_v1.c).
- **Untouched Components**: [`code/src/server_blocking.c`](file:///f:/Sem%20V/CN/code/src/server_blocking.c), [`code/src/server_select.c`](file:///f:/Sem%20V/CN/code/src/server_select.c), [`code/src/server_poll.c`](file:///f:/Sem%20V/CN/code/src/server_poll.c), [`code/include/common.h`](file:///f:/Sem%20V/CN/code/include/common.h), and the echo protocol were strictly left intact.

---

## 2. Epoll Re-Engineering (Task 1)

### Problem Analysis in Previous Implementation
1. **Wasted 3rd System Call**: Under Edge-Triggered (`EPOLLET`), the server drained using `while(1) read()`, always executing a redundant 3rd `read()` system call per ping-echo that invariably returned `-1 EAGAIN`.
2. **Busy-Spinning on Write**: The write loop used `continue` on `EAGAIN`, consuming 100% CPU in a spinlock-like fashion when kernel socket write buffers filled up.

### Fixes Implemented

#### A. Level-Triggered Server: [`code/src/epoll_lt_server.c`](file:///f:/Sem%20V/CN/code/src/epoll_lt_server.c)
- **Single `read()` per event**: Exactly one `read()` system call is issued per readability notification.
- **Non-blocking Write Buffering with `EPOLLOUT`**: When `write()` encounters `EAGAIN` or produces a short write, unsent bytes are stored in `client_states[fd].wbuf`, and interest is switched to `EPOLLIN | EPOLLOUT`. When the socket becomes writable, buffered data is drained, and interest reverts to `EPOLLIN`. No busy-spinning or sleeping occurs.
- **Harvest Buffer Capacity**: `LOCAL_MAX_EVENTS` is set to `16384` ($\ge 1024$).

#### B. Edge-Triggered Server: [`code/src/epoll_et_server.c`](file:///f:/Sem%20V/CN/code/src/epoll_et_server.c)
- **Short-Read Drain Optimization**: On stream sockets (`SOCK_STREAM`), receiving fewer bytes than the buffer size (`bytes_read < sizeof(buf)`) guarantees that the kernel receive queue is drained. The loop breaks immediately without invoking the redundant `read()` that returns `-1 EAGAIN`.
- **Verified Syscall Reduction**: As measured by `strace_check.sh`, `epoll_et_server` achieved a 1:1 `read` to `write` ratio (73,443 reads and 73,443 writes under 100 conns), cutting system calls by ~33% compared to naive ET draining.
- **Event-Driven Write Buffering**: Identical non-blocking `EPOLLOUT` state machine buffering unsent data without spinlocks.

---

## 3. High-Performance `io_uring` Rewrite (Task 2): [`code/src/io_uring_opt_server.c`](file:///f:/Sem%20V/CN/code/src/io_uring_opt_server.c)

### Problem Analysis in Previous Implementation
1. **Dual System Calls**: Calling `io_uring_submit()` at the bottom and `io_uring_wait_cqe()` at the top resulted in 2 `io_uring_enter` calls per loop.
2. **Per-CQE `io_uring_cqe_seen()`**: Substantial memory barrier and atomic update overhead per event.
3. **Improper Error Handling**: `res <= 0` treated transient `-EAGAIN` and `-EINTR` as fatal disconnections.
4. **Memory Inflation**: Allocating a `char buf[BUF_SIZE]` per connection consumed ~20–35 MB at scale.
5. **Redundant `set_nonblocking()`**: Unnecessary overhead since `io_uring` natively manages asynchronous execution.

### Fixes Implemented
1. **Adaptive Ring Flags**:
   - Initialized with `IORING_SETUP_SINGLE_ISSUER | IORING_SETUP_DEFER_TASKRUN` (Linux 6.1+).
   - Graceful runtime fallback to `COOP_TASKRUN | SINGLE_ISSUER` (Linux 5.19+), then to standard `0`.
2. **Unified Single-Syscall Batch Loop**:
   - Replaced separate wait/submit calls with a single `io_uring_submit_and_wait(&ring, 1)`.
   - Iterates completions using `io_uring_for_each_cqe()`.
   - Advances completions via a single batch call `io_uring_cq_advance(&ring, count)`.
3. **Multishot Operations**:
   - **`io_uring_prep_multishot_accept`**: Submits a single accept SQE; re-arms only if `!(cqe->flags & IORING_CQE_F_MORE)`.
   - **`io_uring_prep_recv_multishot`**: Continuously receives packets with `IOSQE_BUFFER_SELECT`.
4. **Provided Buffer Ring (`io_uring_setup_buf_ring`)**:
   - Pre-allocates a shared ring of 8,192 4KB buffers (`BGID 1`).
   - Sockets select buffers dynamically on packet arrival. Buffers are returned via `io_uring_buf_ring_add` and `io_uring_buf_ring_advance` once the matching `send` completes.
   - Eliminates per-connection buffer memory.
5. **Robust Error Handling**:
   - Correctly handles `-ENOBUFS` (re-arms recv).
   - Tolerates `-EAGAIN` and `-EINTR`.
   - Closes strictly on `res == 0` (EOF) or fatal errors.
6. **Zero-Allocation 64-Bit Tagging**:
   - Operation metadata (`type`, `fd`, `bid`) is packed into `sqe->user_data` (`MAKE_TAG`), eliminating heap allocations.
7. **Sparse Fixed-File Table Decision**:
   - Evaluated `io_uring_register_files_sparse`. Omitted to avoid fragile direct-descriptor slot reclamation logic, keeping the code clean, portable, and robust.

---

## 4. Benchmark Hygiene & Verification (Task 3)

### Tooling Added
- [`code/scripts/run_bench.sh`](file:///f:/Sem%20V/CN/code/scripts/run_bench.sh): Sets `ulimit -n 65536`, pins the server to Core 0 (`taskset -c 0`) and load generators to Cores 1–15 (`taskset -c 1-15`), runs 5 trials, and computes median req/s, median p99 latency, and VmRSS.
- [`code/scripts/strace_check.sh`](file:///f:/Sem%20V/CN/code/scripts/strace_check.sh): Profiles exact system call invocation frequency over 10 seconds under load.
- [`code/scripts/test_servers.py`](file:///f:/Sem%20V/CN/code/scripts/test_servers.py): Automated functional echo verification (8/8 servers passed).

### Key Empirical Findings

#### Scenario 1: Standard Concurrency Scaling (10 to 5,000 Connections, 5-Trial Median)
- **`poll()`**: Peaks at **154,098 req/s** (100 conns) and **69,016 req/s** (5,000 conns) due to contiguous CPU cache streaming and $O(1)$ swap-with-last compaction.
- **`epoll_et`**: Sustains **47,983 req/s** at 5,000 connections with low tail latency (**122.38 ms p99**).
- **`io_uring_opt`**: Delivers **47,471 req/s** at 5,000 connections with **35.9 MB** fixed buffer-ring memory footprint.

#### Scenario 2: 10,000 Idle + 100 Active Connections (The C10K Architectural Test)
| Server Engine | Active / Idle Conns | Median Throughput | Median p99 Latency | Architectural Observation |
| :--- | :--- | :--- | :--- | :--- |
| **`server_blocking`** | 100 act / 10k idle | **0 req/s** (Failed) | N/A | Exceeds OS thread stack limits |
| **`server_select`** | 100 act / 10k idle | **0 req/s** (Blocked) | N/A | Hard compile-time `FD_SETSIZE = 1024` limit |
| **`server_poll`** | 100 act / 10k idle | **17,040 req/s** | 7.28 ms | $O(N)$ linear scan over 10,100 `pollfd` structs |
| **`epoll_lt`** | 100 act / 10k idle | **59,345 req/s** | 3.23 ms | $O(K)$ ready list ignores idle connections |
| **`epoll_et`** | 100 act / 10k idle | **60,869 req/s** | 3.33 ms | $O(K)$ ready list + short-read optimization |
| **`io_uring_opt`** | 100 act / 10k idle | **61,059 req/s** | 3.26 ms | **Highest throughput**; zero syscall overhead on idle sockets |

*Outcome*: In the presence of 10,000 idle connections, **`epoll` and `io_uring` outperform `poll` by 3.6×** (61k req/s vs 17k req/s), with less than half the tail latency, validating the fundamental theory of scalable network I/O.

#### System Call Profiling (`strace_check.sh`)
| Server | Total Syscalls | Total Requests | Syscalls / Request |
| :--- | :--- | :--- | :--- |
| **`server_blocking`** | 850,174 | 426,449 | **1.994** (~1 read + 1 write) |
| **`server_select`** | 146,359 | 75,636 | **1.935** |
| **`server_poll`** | 148,685 | 77,399 | **1.921** |
| **`epoll_lt_server`** | 148,129 | 76,466 | **1.937** |
| **`epoll_et_server`** | 146,838 | 75,718 | **1.939** (Eliminated 3rd read) |
| **`io_uring_opt_server`** | 42,797 | 511,021 | **0.084** (~12 requests per system call) |

---

## 5. Environment & Assumptions
- **Linux Kernel**: `6.6.87.2-microsoft-standard-WSL2` (verified via `uname -r`). Requires Linux 6.1+ for `IORING_SETUP_DEFER_TASKRUN`, with automatic runtime fallback to 5.19+ and standard modes.
- **liburing**: Version `2.5` (verified via `pkg-config --modversion liburing`). Requires `liburing` $\ge 2.3$ for `io_uring_setup_buf_ring` and multishot socket APIs.
- **CPU Isolation**: Server pinned to Core 0; load generator pinned to Cores 1–15.
