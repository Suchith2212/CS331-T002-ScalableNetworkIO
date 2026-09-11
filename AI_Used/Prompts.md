# AI Prompts Archive

**Course**: CS331 - Computer Networks  
**Team ID**: `T002` | **Project ID**: `13`  
**Project Title**: Scalable Network I/O: From select to io_uring  

---

## 💬 Representative Prompts Archive

Below is an authentic catalog of key prompts issued to the AI assistants across the project lifecycle:

### Phase 1: Architecture & Shared Header Scoping
> *"We are building a C project comparing 5 TCP echo servers: blocking, select, poll, epoll ET, and io_uring. Help us write a shared common.h header with socket initialization helper `make_listener(port)` with SO_REUSEADDR and SO_REUSEPORT, plus non-blocking helper `set_nonblocking(fd)` via fcntl."*

### Phase 2: C Socket Server Engine Implementations
> *"Write a single-threaded C server for epoll using Edge-Triggered mode (EPOLLET). Make sure accept() and read() loops handle EAGAIN / EWOULDBLOCK properly so no unread payload bytes get stuck in non-blocking socket buffers."*

> *"Write a single-threaded C TCP echo server using Linux liburing. We need to initialize an io_uring queue with 4096 entries, prep accept SQEs, prep read/write SQEs, and handle completion queue events using io_uring_wait_cqe and io_uring_peek_batch_cqe."*

### Phase 3: Benchmarking & Harness Debugging
> *"Our initial benchmark script crashed at 5,000 connections with 'RuntimeError: can't start new thread' because spawning 5,000 Python OS threads exceeded stack limits. Help us refactor scripts/benchmark.py to use non-blocking asyncio streams so a single event loop can handle 5,000 parallel client sockets cleanly."*

### Phase 4: Data Visualization & Plotting
> *"Write a Python script scripts/plot_results.py using matplotlib that reads results/benchmark_data.json and produces 4 publication-quality charts: throughput vs connections, p99 latency vs connections, memory RSS vs connections, and relative system call overhead."*

### Phase 5: Documentation & Slide Generation
> *"Generate an academic benchmark report for README.md and report/final_report.md summarizing our theoretical findings: O(N) vs O(1) complexity, select's FD_SETSIZE 1024 cap, and io_uring's zero-syscall batching advantage."*
