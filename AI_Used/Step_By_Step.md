# Stage-by-Stage Breakdown of Human-AI Collaboration

## 📌 Collaborative Development Pipeline

This document details the step-by-step collaboration between **Team T002** (**Suchith**, **Rohith**, **Harshith**, **Hanook**) and our AI coding assistants across all project phases.

---

### Stage 1: Core Architecture & Shared Header (`code/include/common.h`)
- **Human Work (Suchith & Rohith)**: Designed the socket architecture, defined network parameters (`PORT 8080`, `BACKLOG 4096`, `BUF_SIZE 4096`, `MAX_EVENTS 16384`), and specified required socket options (`SO_REUSEADDR`, `SO_REUSEPORT`, `O_NONBLOCK`).
- **AI Contribution**: Synthesized boilerplate function implementations for `set_nonblocking(fd)` using `fcntl` and `make_listener(port)`.
- **Human Verification**: Added conditional `#ifdef SO_REUSEPORT` guards to ensure portability across different Linux kernel versions and verified bind error handling.

---

### Stage 2: Synchronous Multiplexing Engines (`server_select.c` & `server_poll.c`)
- **Human Work (Harshith)**: Analyzed theoretical $O(N)$ limitations of POSIX `select()` and `poll()`.
- **AI Contribution**: Generated initial event loop structures and bitmask manipulation macros.
- **Human Verification & Audit**:
  - Inserted strict `if (client_fd >= FD_SETSIZE)` guard in `server_select.c` to prevent bitmask stack corruption when scaling past 1024 descriptors.
  - Implemented dynamic `realloc()` array resizing and array compaction logic (`fds[i].fd = -1`) in `server_poll.c`.

---

### Stage 3: Scalable Edge-Triggered `epoll()` Engine (`server_epoll.c`)
- **Human Work (Rohith)**: Selected Edge-Triggered (`EPOLLET`) mode over Level-Triggered mode to minimize kernel event notifications and optimize $O(1)$ ready-list performance.
- **AI Contribution**: Assisted in writing `epoll_create1(0)`, `epoll_ctl()`, and `epoll_wait()` event loop skeleton.
- **Human Verification & Audit**: Identified Edge-Triggered buffer starvation risks and re-engineered accept and read routines into non-blocking `while(1)` loops draining socket buffers until returning `EAGAIN` or `EWOULDBLOCK`.

---

### Stage 4: Asynchronous Completion Ring Engine (`server_uring.c`)
- **Human Work (Suchith)**: Researched Linux `io_uring` architecture, Submission Queue (SQ) and Completion Queue (CQ) ring buffers, and batch event processing benefits.
- **AI Contribution**: Provided syntax templates for `liburing` queue initialization (`io_uring_queue_init`) and SQE prep helpers (`io_uring_prep_accept`, `io_uring_prep_read`, `io_uring_prep_write`).
- **Human Verification & Audit**: Designed `struct conn_info` state context objects attached to SQEs via `io_uring_sqe_set_data()`, implemented batch harvesting (`io_uring_peek_batch_cqe`), and ensured proper re-arming of connection accept events.

---

### Stage 5: Benchmarking Suite & Harness Debugging (`code/scripts/`)
- **Human Work (Hanook)**: Defined benchmarking metrics (throughput req/s, 99th percentile latency, RSS memory, system call efficiency) and load ranges (10 to 5,000 parallel connections).
- **AI Contribution**: Generated initial multi-threaded Python benchmark script and Matplotlib plotting framework.
- **Human Verification & Audit**:
  - When the initial multi-threaded Python harness crashed at 5,000 connections (`RuntimeError: can't start new thread`), Hanook diagnosed OS thread stack limits and guided AI to refactor the harness to single-threaded Python `asyncio` non-blocking streams.
  - Verified plotting outputs (`throughput_vs_connections.png`, `latency_p99_vs_connections.png`, `memory_scalability.png`).

---

### Stage 6: Documentation, Reports & Presentation (`report/` & `ppt/`)
- **Human Work (All Team Members)**: Compiled empirical findings, formatted theoretical comparisons, reviewed slide structures, and prepared Viva presentation responses.
- **AI Contribution**: Assisted in generating Markdown tables, LaTeX equations, slide deck outline formatting, and organizing documentation artifacts.
- **Human Verification**: Verified Team ID (`T002`), Project ID (`13`), Title, Roster, and empirical metrics across all repo documentation.
