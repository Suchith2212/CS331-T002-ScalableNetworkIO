# Step-by-Step AI Contribution Details

**Course**: CS331 - Computer Networks  
**Team ID**: `T002` | **Project ID**: `13`  
**Project Title**: Scalable Network I/O: From select to io_uring  

---

## 📌 Stage-by-Stage Breakdown of AI Contributions

### Stage 1: Environment & Shared Header (`code/include/common.h`)
- **Contribution**: AI generated the clean skeleton for `common.h`, defining constants (`PORT 8080`, `BACKLOG 4096`, `BUF_SIZE 4096`, `MAX_EVENTS 16384`) and non-blocking helper `set_nonblocking()`.
- **Human Audit**: Added `SO_REUSEPORT` conditional checks and verified socket bind error handling.

---

### Stage 2: Synchronous Multiplexing Engines (`server_select.c` & `server_poll.c`)
- **Contribution**: AI generated initial event loop structures for `select()` and `poll()`.
- **Human Audit**: Added strict `if (client_fd >= FD_SETSIZE)` guard in `server_select.c` to prevent bitmask overflow past 1024 descriptors. Implemented dynamic array compaction (`fds[i].fd = -1`) in `server_poll.c`.

---

### Stage 3: Scalable Edge-Triggered `epoll()` Engine (`server_epoll.c`)
- **Contribution**: AI assisted in constructing the Edge-Triggered (`EPOLLET`) event loop.
- **Human Audit**: Ensured accept and read routines executed continuous `while(1)` loops draining socket buffers until returning `EAGAIN` or `EWOULDBLOCK` to prevent socket data starvation.

---

### Stage 4: Completion-Ring `io_uring` Engine (`server_uring.c`)
- **Contribution**: AI provided correct `liburing` queue preparation syntax (`io_uring_prep_accept`, `io_uring_prep_read`, `io_uring_prep_write`).
- **Human Audit**: Designed `struct conn_info` state context objects attached to SQEs via `io_uring_sqe_set_data()`, implemented batch harvesting (`io_uring_peek_batch_cqe`), and ensured proper re-arming of connection accept events.

---

### Stage 5: Benchmarking & Profiling Harness (`scripts/`)
- **Contribution**: AI generated the Python load harness (`scripts/benchmark.py`) and Matplotlib chart generator (`scripts/plot_results.py`).
- **Human Audit**: When the initial multi-threaded Python harness crashed at 5,000 parallel client threads, we directed AI to refactor the harness to use non-blocking `asyncio` streams, enabling clean 5,000+ socket benchmarking.

---

### Stage 6: Report, Presentation & Submission Documentation
- **Contribution**: AI formatted empirical data into clean Markdown tables, generated slide deck templates, and assisted in assembling final project submission artifacts.
- **Human Audit**: Verified all Team ID (`T002`), Project ID (`13`), Title, and Team Member details (`Suchith`, `Rohith`, `Harshith`, `Hanook`) across all repository files.
