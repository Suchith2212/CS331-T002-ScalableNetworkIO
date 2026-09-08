# Slide Deck: Scalable Network I/O: From select to io_uring

**Course**: CS331 - Computer Networks  
**Team ID**: `T002`  
**Project ID**: `13`  
**Project Title**: Scalable Network I/O: From select to io_uring  
**Team Members**:  
- Suchith (`24110313`)  
- Rohith (`24110303`)  
- Harshith (`24110091`)  
- Hanook (`24110378`)  

---

## Slide 1: Title & Executive Summary
- **Project**: Building and Benchmarking Single-Threaded TCP Echo Servers.
- **Core Question**: How do Linux I/O multiplexing primitives scale from 10 to 5,000+ concurrent TCP connections?
- **Mechanisms Tested**:
  1. Baseline Multi-Threaded (`pthread`)
  2. `select()` — $O(N)$ Synchronous Bitmask
  3. `poll()` — $O(N)$ Synchronous Array
  4. `epoll()` — $O(1)$ Edge-Triggered Event Queue
  5. `io_uring` — Shared Ring-Buffer Completion Engine

---

## Slide 2: The Concurrency Problem (C10K Challenge)
- **Traditional Model**: One thread per client connection.
  - **Problem**: Thread stack allocation (~MBs) exhausts memory.
  - **Problem**: Kernel context switching eats CPU cycles.
- **Solution**: Single-threaded Event Loops & Asynchronous I/O multiplexing.

---

## Slide 3: Level 1 & 2 — `select()` vs `poll()` ($O(N)$ Scaling)
- **`select()`**:
  - Uses `fd_set` bitmasks.
  - **Hard Limit**: `FD_SETSIZE` caps sockets at 1024.
  - **Overhead**: Bitmasks copied to/from kernel on *every* call.
- **`poll()`**:
  - Uses dynamic `struct pollfd` array.
  - **Advantage**: Removes 1024 hard cap.
  - **Drawback**: $O(N)$ linear scanning across all array elements.

---

## Slide 4: Level 3 — `epoll()` ($O(1)$ Edge-Triggered)
- **Architecture**:
  - **Red-Black Tree**: Sockets registered in kernel memory once via `epoll_ctl()`.
  - **Ready List**: Interrupts append active sockets to a linked list.
  - **Notification**: `epoll_wait()` returns ready list in $O(1)$ time.
- **Edge-Triggered (`EPOLLET`)**:
  - Notifies only on state changes.
  - Requires non-blocking sockets and full read loops until `EAGAIN`.

---

## Slide 5: Level 4 — `io_uring` (Completion Ring Buffer)
- **Readiness vs Completion**:
  - `epoll` tells you a socket *can* be read (requires `read()` system call).
  - `io_uring` *executes* the read asynchronously and posts a completion event.
- **Shared Memory Ring Buffers**:
  - **Submission Queue (SQ)**: Application submits I/O requests.
  - **Completion Queue (CQ)**: Kernel delivers finished I/O results.
- **Benefit**: Eliminates per-I/O system call context switching.

---

## Slide 6: Code Base & Repository Architecture
```
/code
├── include/common.h          # Listener creation & non-blocking setup
├── src/
│   ├── server_blocking.c     # Thread-per-client baseline
│   ├── server_select.c       # select() O(N) event loop
│   ├── server_poll.c         # poll() O(N) dynamic array
│   ├── server_epoll.c        # epoll() O(1) Edge-Triggered loop
│   └── server_uring.c        # io_uring SQ/CQ completion engine
├── scripts/
│   ├── test_servers.py       # Automated correctness verifier (5/5 passed)
│   ├── benchmark.py          # High-concurrency load tester
│   └── plot_results.py       # Chart visualization engine
└── Makefile                  # GCC compilation (-O3 -Wall -Wextra -luring)
```

---

## Slide 7: Functional Verification & Test Harness
- **Verification Harness**: `python3 scripts/test_servers.py`
- **Results**:
  - `bin/server_blocking`  --> **SUCCESS**
  - `bin/server_select`    --> **SUCCESS**
  - `bin/server_poll`      --> **SUCCESS**
  - `bin/server_epoll`     --> **SUCCESS**
  - `bin/server_uring`     --> **SUCCESS**
- **Test Output**: `5/5 servers passed correctness verification.`

---

## Slide 8: Empirical Benchmark Results

| Server | 10 Conns | 500 Conns | 1,000 Conns | 5,000 Conns | Key takeaway |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`blocking`** | 27,431 req/s | 37,707 req/s | 37,883 req/s | 32,373 req/s | High RAM/thread overhead |
| **`select()`** | **89,682 req/s** | 117,831 req/s | 87,445 req/s | *Exceeded limit* | Rejects >1024 connections |
| **`poll()`** | 78,590 req/s | **123,672 req/s** | **108,819 req/s** | **77,367 req/s** | $O(N)$ linear scanning |
| **`epoll()`** | 75,667 req/s | 79,541 req/s | 71,059 req/s | 56,459 req/s | Stable $O(1)$ event queue |
| **`io_uring`** | 65,636 req/s | 70,026 req/s | 64,213 req/s | 46,399 req/s | Zero per-I/O syscall cost |

---

## Slide 9: Key Insights & Trade-offs
1. **`select()`**: Fast for low connection counts, but unusable for C10K due to `FD_SETSIZE = 1024`.
2. **`poll()`**: Scales connection count, but CPU usage increases linearly with idle sockets.
3. **`epoll()`**: The standard choice for Linux high-concurrency event loops (Nginx, Node.js).
4. **`io_uring`**: The future of Linux I/O—minimizes kernel context switching via shared ring buffers.

---

## Slide 10: Conclusion & Q&A
- **Summary**:
  - Implemented 5 working C TCP echo servers.
  - Verified 100% functional correctness.
  - Benchmarked throughput, p99 latency, RSS memory, and syscall trade-offs across 10 to 5,000+ connections.
- **Repository Structure**: `/code`, `/report`, `/ppt`, `/README.md`
- **Thank You! Questions?**
