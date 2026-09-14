# Authentic Interactive AI Prompts Archive

## 📋 Overview & Methodology

This document archives the authentic, real prompts used by **Team T002** (**Suchith**, **Rohith**, **Harshith**, **Hanook**) during interactive engineering, codebase exploration, and deep-dive technical analysis with the AI assistant. 

Filtering applied: Minor typos, repetitive short queries, and overly verbose prompt templates were excluded to present a curated archive of high-value technical prompts.

---

## 💬 Real Prompt Archive

### Section 1: Core Concepts & Project Overview
* **Prompt**: *"Explain all the concepts used in this project in detail, (in depth up to project level)"*
  - **Context**: Deep-dive theoretical breakdown of socket fundamentals, C10K/C100K scalability challenges, POSIX multi-threading overhead, synchronous readiness multiplexing (`select`, `poll`), scalable event queues (`epoll` ET), and completion-queue ring buffers (`io_uring`).
* **Prompt**: *"I need you to explain all the terms also — there are many keywords/variables that also explain"*
  - **Context**: Dictionary extraction covering Linux system calls, C macros (`PORT`, `BACKLOG`, `FD_SETSIZE`), socket options (`SO_REUSEADDR`, `SO_REUSEPORT`), non-blocking flags (`O_NONBLOCK`), and error symbols (`EAGAIN`, `EWOULDBLOCK`, `EINTR`).

---

### Section 2: Implementation Deep Dives

#### 1. Common Infrastructure (`common.h`)
* **Prompt**: *"Fully explain the code in common.h"*
  - **Context**: Line-by-line breakdown of socket header inclusions, `#pragma once` guard, non-blocking `fcntl` helper (`set_nonblocking`), listening socket creation (`make_listener`), and socket backlog/reuse option configuration.

#### 2. Baseline Multi-Threaded Server (`server_blocking.c`)
* **Prompt**: *"Explain server_blocking.c in detail"*
  - **Context**: Analysis of the thread-per-client architecture, stack memory allocation, and performance degradation under high connection scale.
* **Prompt**: *"I haven't understood the main function — not even why we are using them, why we are writing these conditions?"*
  - **Context**: Detailed rationale for every line and `if` statement in `main()`, including `signal(SIGPIPE, SIG_IGN)`, dynamic memory allocation (`malloc`) for thread descriptors to prevent race conditions, and `pthread_detach()` resource cleanup.
* **Prompt**: *"How many threads are we using in server_blocking?"*
  - **Context**: Thread counting formula ($\text{Total Threads} = 1 \text{ [Main Acceptor]} + N \text{ [Connected Clients]}$) and memory impact (26.8 MB VmRSS for 5,001 threads at 5k connections).

#### 3. Synchronous Readiness Servers (`server_select.c` & `server_poll.c`)
* **Prompt**: *"Now explain server_select.c"*
  - **Context**: Analysis of `fd_set` bitmask operations (`FD_ZERO`, `FD_SET`, `FD_CLR`, `FD_ISSET`), the `readfds = master_set` copy necessity, $O(N)$ descriptor scanning, and enforcing the compile-time `FD_SETSIZE = 1024` guard (`client_fd >= FD_SETSIZE`).
* **Prompt**: *"Explain server_poll.c"*
  - **Context**: Explanation of replacing bitmasks with dynamic `struct pollfd` arrays allocated via `malloc()` and grown via `realloc()`, avoiding the 1024 limit, and implementing array compaction for closed sockets (`fds[i].fd = -1`).

#### 4. Scalable Event Queue (`server_epoll.c`)
* **Prompt**: *"Explain server_epoll.c"*
  - **Context**: Breakdown of `epoll_create1`, `epoll_ctl`, `epoll_wait`, kernel Red-Black tree persistence, $O(K)$ ready list harvesting, and Edge-Triggered (`EPOLLET`) non-blocking `while(1)` drain loops.
* **Prompt**: *"When do we add a socket to the red-black tree?"*
  - **Context**: Pinpointing exact lifecycle code locations where `epoll_ctl(EPOLL_CTL_ADD)` is called: during server startup for `listen_fd` and immediately after `accept()` for each new `client_fd`.
* **Prompt**: *"How does red black tree affect the performance of epoll?"*
  - **Context**: Deep dive into the $O(\log N)$ search, insertion, and deletion complexity of the in-kernel Red-Black Tree, contrasting it against $O(N)$ linear array scanning in `select()` and `poll()`.

---

### Section 3: Linux Kernel Network Internals
* **Prompt**: *"What is this EAGAIN, EWOULDBLOCK?"*
  - **Context**: Detailed explanation of non-blocking OS error signals, historical origins (SVR4 vs. BSD), why they signify "resource temporarily unavailable" rather than a real error, and how they signal loop termination in Edge-Triggered non-blocking reads/accepts.
* **Prompt**: *"So we have one socket and from that we accept the network requests?"*
  - **Context**: Clarifying the distinction between the single passive Listening Socket (`listen_fd`) sitting at port 8080 and individual active Connected Client Sockets (`client_fd`) returned by `accept()`.
* **Prompt**: *"Do we accept the new incoming connection in all the mechanisms?"*
  - **Context**: Comparative analysis proving that calling `accept()` (or `io_uring_prep_accept`) is mandatory across all 5 paradigms to extract established TCP handshakes from the kernel Accept Queue.

---

### Section 4: Asynchronous Completion Ring (`io_uring`)
* **Prompt**: *"What will be there in submission queue — are only the read/write ones there in it like the ready to data transfer ones?"*
  - **Context**: Clarifying `io_uring` Submission Queue (SQ) mechanics, demonstrating that SQEs hold prepared intent operations (`accept`, `read`, `write`) queued *before* data arrives, rather than just ready data transfers.

---

### Section 5: Benchmarking & Testing Suite
* **Prompt**: *"Explain testservers.py"*
  - **Context**: Line-by-line explanation of the functional correctness test script, background subprocess management (`subprocess.Popen`), payload verification, and socket timeout safety.
* **Prompt**: *"Now let's come to the benchmarking we have done"*
  - **Context**: Comprehensive review of the Python `asyncio` load generator (`benchmark.py`), performance metrics (Throughput req/s, p99 Latency, Resident Set Memory VmRSS), empirical data tables, and architectural trade-offs.
