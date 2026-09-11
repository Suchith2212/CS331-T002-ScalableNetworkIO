# Representative AI Prompts Archive

## 📋 Context & Methodology

The prompts below document the authentic, iterative dialog between **Team T002** (**Suchith**, **Rohith**, **Harshith**, **Hanook**) and our AI coding assistants. Prompts were drafted by team members to solve specific technical challenges, debug runtime edge cases, and automate visualization.

---

## 💬 Stage-by-Stage Prompts Archive

### Phase 1: Shared Network Infrastructure & Socket Setup
- **Prompted by**: **Suchith** & **Rohith**
> *"We are building a C project comparing 5 TCP echo servers: blocking baseline, select, poll, epoll ET, and io_uring. Help us write a clean shared header header file `code/include/common.h` containing non-blocking socket setter `set_nonblocking(fd)` via `fcntl` and listener helper `make_listener(port)` configured with `SO_REUSEADDR`, `SO_REUSEPORT`, and a listen backlog of 4096."*

---

### Phase 2: Synchronous Multiplexing Engines (`select` & `poll`)
- **Prompted by**: **Harshith**
> *"In `server_select.c`, `select()` fails if a socket descriptor exceeds 1024 because of `FD_SETSIZE`. How can we explicitly guard against buffer overflow when accepting new connections in `select()`? Show us how to enforce `if (client_fd >= FD_SETSIZE)` and reject gracefully."*
>
> **Follow-up Prompt**: *"For `server_poll.c`, write a dynamic array structure using `struct pollfd` that starts with capacity 1024 and doubles using `realloc()`. Make sure closed sockets get marked with `fd = -1` and array compaction is performed so `nfds` stays tight."*

---

### Phase 3: Edge-Triggered `epoll()` Buffer Starvation Fix
- **Prompted by**: **Rohith**
> *"Our Edge-Triggered (`EPOLLET`) epoll server drops incoming request data when multiple packets arrive simultaneously because `epoll_wait` only fires once. Write continuous non-blocking `while(1)` accept and read loops that drain all ready bytes until returning `EAGAIN` or `EWOULDBLOCK`."*

---

### Phase 4: `io_uring` Ring Buffer & Asynchronous State Mapping
- **Prompted by**: **Suchith**
> *"We are writing `server_uring.c` using Linux `liburing`. How do we attach connection context data to Submission Queue Entries (SQEs) so that when a Completion Queue Entry (CQE) arrives, we know which client socket and buffer state it belongs to? Draft a `struct conn_info` setup using `io_uring_sqe_set_data` and batch harvesting with `io_uring_peek_batch_cqe`."*

---

### Phase 5: Harness Debugging — Resolving Python Thread Exhaustion
- **Prompted by**: **Hanook**
> *"Our initial multi-threaded Python benchmark script crashed at 5,000 connections with `RuntimeError: can't start new thread` because spawning 5,000 OS threads exceeded stack limits on Linux WSL2. Help us refactor `scripts/benchmark.py` to use Python `asyncio` non-blocking stream readers/writers so a single event loop can generate up to 5,000+ simultaneous TCP client streams."*

---

### Phase 6: Publication-Quality Matplotlib Visualizations
- **Prompted by**: **Hanook** & **Suchith**
> *"Write `scripts/plot_results.py` using `matplotlib` to parse `code/results/benchmark_data.json` and generate 4 PNG charts: Throughput vs Connections, P99 Latency vs Connections, Memory Footprint (RSS) vs Connections, and Syscall Efficiency. Make sure chart labels use grid lines, distinct line markers, and clean legend placements suitable for an academic presentation."*
