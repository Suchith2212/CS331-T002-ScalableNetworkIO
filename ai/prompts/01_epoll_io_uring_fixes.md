# Prompt 01: epoll and io_uring Server Fixes

```markdown
CONTEXT
I'm benchmarking Linux I/O multiplexing servers (blocking, select, poll, epoll, io_uring) 
written in C. All of them implement the same echo server using helpers from 
../include/common.h (make_listener, set_nonblocking, set_tcp_nodelay, PORT, BUF_SIZE, 
MAX_EVENTS). Benchmark showed epoll and io_uring slower than poll, which contradicts 
expectations. I found the cause is in my epoll and io_uring implementations, not the 
kernel mechanisms. Please fix them as described below.

RULES
- Do NOT change blocking, select, or poll servers, common.h, or the echo protocol.
- Keep the same CLI (optional port argument) and the same startup printf style.
- Every server must keep identical observable behavior: read data, echo it back, close on EOF.
- Keep code compiling with -Wall -Wextra. Check my Makefile/build script and update it if needed 
  (liburing must be linked with -luring).
- Keep a copy of the originals as epoll_server_v1.c and io_uring_server_v1.c before editing.
- Comment each change with a short "why".

TASK 1: epoll server
Problems:
 a) With EPOLLET I drain with read() until EAGAIN, which costs a wasted 3rd syscall per request 
    (read, write, read->EAGAIN). 
 b) The write loop does `continue` on EAGAIN, which busy-spins.
Fix:
 - Create TWO variants so I can benchmark both:
   1. epoll_lt_server.c: level-triggered (no EPOLLET), exactly one read() per event, 
      then write the echo.
   2. epoll_et_server.c: edge-triggered, but stop draining as soon as a read returns 
      fewer bytes than the buffer size (short read on a stream socket means drained). 
      Only continue the loop when the read filled the whole buffer.
 - In both, handle partial writes without busy-spinning: on EAGAIN during write, 
   either poll() that fd for POLLOUT briefly, or (preferred) keep the unsent remainder 
   and register EPOLLOUT for that fd. Keep it simple and correct.
 - Make sure MAX_EVENTS passed to epoll_wait is at least 1024 (use a local constant if 
   common.h's value is smaller, without editing common.h).
 - Accept loop for the listener can stay as is.
 - Use one shared read buffer (as now).

TASK 2: io_uring server (rewrite for performance)
Problems in current code:
 a) io_uring_submit() at loop bottom plus io_uring_wait_cqe() at loop top = 2 io_uring_enter 
    syscalls per iteration.
 b) io_uring_cqe_seen() called per CQE.
 c) `res <= 0` closes the connection, which wrongly includes -EAGAIN/-EINTR.
 d) set_nonblocking() on client fds is unnecessary for io_uring.
 e) A char buf[BUF_SIZE] per connection (about 20 MB at 5000 conns) inflates memory.
Fix, write as io_uring_opt_server.c (keep the original as the baseline):
 - Setup flags: IORING_SETUP_SINGLE_ISSUER | IORING_SETUP_DEFER_TASKRUN. 
   If init fails (older kernel), retry with COOP_TASKRUN|SINGLE_ISSUER, then with 0, 
   and print which mode was used.
 - Main loop: a single io_uring_submit_and_wait(&ring, 1), then process CQEs with 
   io_uring_for_each_cqe(), then ONE io_uring_cq_advance(&ring, count) per batch.
 - Use multishot accept (io_uring_prep_multishot_accept). Re-arm only if the CQE lacks 
   IORING_CQE_F_MORE.
 - Use multishot recv (io_uring_prep_recv_multishot) with a provided buffer ring 
   (io_uring_setup_buf_ring / io_uring_buf_ring_add / io_uring_buf_ring_advance) 
   using IOSQE_BUFFER_SELECT. Remove the per-connection data buffer. 
   Return buffers to the ring after the send completes. Re-arm recv if F_MORE is absent.
 - Handle -ENOBUFS (re-arm recv), -EAGAIN/-EINTR (retry), and close only on 0 or fatal errors.
 - Don't call set_nonblocking on accepted client fds, but keep set_tcp_nodelay.
 - Optionally register the ring's files with a sparse fixed-file table 
   (io_uring_register_files_sparse + direct accept) if you can do it cleanly; 
   if it adds too much complexity, skip it and mention that.
 - Per-connection state should be small (fd, state, buffer id in flight). 
   Static table of MAX_CONNS is fine.
 - Batch SQE preparation and use get_sqe_safe-style flushing when the SQ is full.

TASK 3: benchmark hygiene
 - Add a script run_bench.sh that, for each server and each connection count 
   (10, 100, 500, 1000, 2000, 5000):
   * pins the server to one core with taskset and the load generator to different cores,
   * runs 5 trials and reports the MEDIAN req/s and p99,
   * records server VmRSS from /proc/<pid>/status,
   * runs `ulimit -n 65536` first.
   Reuse my existing load generator if there is one in the repo; do not invent a new protocol.
 - Add a second scenario: 10,000 idle connections plus 100 active ones, 
   which is where epoll should beat poll/select.
 - Add a small script strace_check.sh that runs `strace -c -f -p <pid>` for 10 seconds 
   under load for each server and prints syscalls per request.

DELIVERABLES
 1. The new/updated source files and build changes.
 2. A short CHANGES.md explaining each fix and the expected effect.
 3. Verify that each server compiles and passes a quick functional test 
    (connect, send "hello", receive "hello") before reporting done.
 4. Tell me any assumption you made (kernel version needed, liburing version needed). 
    Check with `uname -r` and `pkg-config --modversion liburing`.
```
