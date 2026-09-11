# Human-Driven, AI-Accelerated Design & Thought Process

## 💡 Engineering Philosophy & Rationale

Our team (**Team T002**) established a strict **Human-Driven, AI-Accelerated Engineering Workflow**. We maintained direct control over system design, POSIX kernel socket mechanics, performance criteria, and empirical validation, while using AI tools as pair-programming assistants to accelerate prototyping and visual reporting.

```
+---------------------------------------------------------------------------------------+
| HUMAN STUDENT RESPONSIBILITIES (Suchith, Rohith, Harshith, Hanook)                    |
|  - Architectural design & breakdown into 5 comparative I/O paradigms                  |
|  - Kernel socket system call mechanics (select, poll, epoll ET, io_uring)             |
|  - System limit tuning (ulimit -n 65535, WSL2 kernel 6.6 configuration)               |
|  - Identifying runtime bugs (thread stack limit at 5k conns, EPOLLET buffer starvation) |
|  - Running empirical benchmarks & validating 100% test suite pass rate                 |
+---------------------------------------------------------------------------------------+
                                           |
                                           v
+---------------------------------------------------------------------------------------+
| AI PAIR-PROGRAMMER ASSISTANCE (Antigravity / Gemini 3.6 Flash / Claude 3.5)            |
|  - Boilerplate code generation (fcntl flags, sockaddr structures, header includes)     |
|  - Syntax verification for liburing SQE/CQE queue manipulation helper APIs            |
|  - Refactoring Python benchmarking harness to non-blocking asyncio streams            |
|  - Generating Matplotlib visualization scripts and formatting slide content           |
+---------------------------------------------------------------------------------------+
```

---

## 🎯 Key Design & Engineering Decisions Made by Students

1. **FD_SETSIZE Safety Guard**: **Harshith** recognized that standard POSIX `select()` uses fixed `fd_set` bitmasks (1024 bits). Passing a file descriptor $\ge 1024$ corrupts stack memory. The team instructed AI to insert an explicit guard (`if (client_fd >= FD_SETSIZE) close(client_fd);`) in `server_select.c`.
2. **Edge-Triggered (`EPOLLET`) Buffer Starvation Handling**: **Rohith** identified that Edge-Triggered mode only triggers when socket state changes from non-readable to readable. If unread bytes remain in the kernel buffer, `epoll_wait()` will block indefinitely. The team designed continuous `while(1)` accept and read loops draining buffers until returning `EAGAIN` / `EWOULDBLOCK`.
3. **`io_uring` Asynchronous State Management**: **Suchith** structured the completion ring model around a custom `struct conn_info` state container attached to SQEs via `io_uring_sqe_set_data()`. This allowed CQE event handlers to track socket descriptors, active buffers, and operation types (`EVENT_ACCEPT`, `EVENT_READ`, `EVENT_WRITE`) cleanly.
4. **Benchmarking Harness Refactoring**: **Hanook** discovered that standard OS multi-threading crashed at 5,000 parallel connections due to stack allocations exceeding OS memory limits. Hanook directed the AI to refactor `scripts/benchmark.py` to leverage Python `asyncio` single-threaded event loops, successfully scaling to 5,000+ persistent TCP streams.

---

## 🔬 Empirical Integrity & Data Authenticity

- **No Synthetic / Hallucinated Data**: All benchmark throughput (req/s), latency (p99 ms), and memory RSS values reported in `code/results/benchmark_summary.csv` and `report/final_report.md` are **empirical measurements** captured directly on Linux kernel 6.6.
- **Verification Rule**: Every file modification was built using `make` with `-O3 -Wall -Wextra` and verified against `scripts/test_servers.py` before committing to the repository.
