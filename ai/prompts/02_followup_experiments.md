# Prompt 02: Follow-up Experiments

```markdown
CONTEXT
I'm benchmarking Linux I/O multiplexing echo servers in C (server_blocking, server_select, 
server_poll, epoll_lt_server, epoll_et_server, io_uring_opt_server). Existing scripts are in 
code/scripts/ (run_bench.sh, strace_check.sh). Results so far:
 - Scenario 1 (all connections active): poll beats epoll and io_uring at 100-5000 conns.
 - Scenario 2 (100 active + 10,000 idle): epoll and io_uring are ~3.2x faster than poll.
 - strace shows ~1.96 syscalls/request for epoll and 0.083 for io_uring.
 - epoll VmRSS at 5k conns rose from 1.6 MB to 21.6 MB, and io_uring is 36.1 MB. I want to know why.
 - epoll and io_uring throughput are nearly identical, so I suspect the load generator is 
   the bottleneck.
I need four follow-up experiments to explain these results. 

RULES
 - Do NOT change the echo protocol, the existing server behavior, or common.h.
 - Instrumentation must be compile-time optional (e.g. -DSTATS) so the normal benchmark 
   binaries are unaffected. Build separate *_stats binaries.
 - Reuse my existing load generator. Do not invent a new protocol.
 - Pin the server and load generator to separate cores with taskset, run `ulimit -n 65536`, 
   and use 5 trials with the MEDIAN reported, as in run_bench.sh.
 - Comment every change with a short "why".

EXPERIMENT 1: events per wakeup (tests why poll wins when all conns are active)
 - Add -DSTATS instrumentation to server_poll, epoll_lt_server, epoll_et_server and 
   io_uring_opt_server. Count (a) wait calls (poll / epoll_wait / io_uring_submit_and_wait), 
   (b) total ready events or CQEs handled, (c) total requests echoed.
 - Print on SIGINT/SIGTERM: avg events per wait call, wait calls per request, and 
   requests/s over the run. Don't print in the hot path.
 - Run at 100, 1000 and 5000 active conns. Output a CSV: server,conns,avg_events_per_wait,
   waits_per_request.

EXPERIMENT 2: CPU cost per request (tests whether io_uring is really cheaper)
 - Under load, for each server and each conn count (100, 1000, 5000), read utime+stime 
   from /proc/<pid>/stat before and after a 10-second steady-state window (use clock ticks 
   via getconf CLK_TCK). Also report voluntary and involuntary context switches from 
   /proc/<pid>/status.
 - Compute server CPU microseconds per request (using request counts from the load 
   generator, NOT from strace) and CPU utilization of the server core.
 - If `perf` is available, also run `perf stat -e task-clock,context-switches,cycles,instructions -p <pid>` 
   for the window. If not, skip it and say so.
 - Also record the load generator's CPU utilization, and flag any run where the load 
   generator core is >90% busy. That means the client is the bottleneck.
 - Output a CSV: server,conns,cpu_us_per_req,server_core_util,client_core_util,vol_cs,invol_cs.

EXPERIMENT 3: explain the VmRSS increase
 - For epoll_lt_server, epoll_et_server and io_uring_opt_server, read the source and tell me 
   exactly what allocates the extra memory. Look for per-connection buffers, pending-write 
   state, large static arrays (e.g. MAX_CONNS * BUF_SIZE), and the io_uring ring and 
   provided-buffer ring sizes.
 - Measure VmRSS and VmData from /proc/<pid>/status at 0, 1000 and 5000 connections.
 - Report a table: server, baseline RSS, RSS at 5000, bytes per connection, and the cause. 
   Say which part is a design choice and which is inherent to the mechanism.
 - If the epoll memory comes from avoidable per-connection state, add an epoll variant 
   epoll_lt_lean_server.c that keeps the old one-shared-buffer design. Handle partial 
   writes using a small, allocate-on-demand pending buffer, not one for every connection. 
   Benchmark it against the others.

EXPERIMENT 4: idle-connection sweep (find the poll/epoll crossover)
 - Keep 100 active connections fixed. Vary idle connections: 0, 500, 1000, 2000, 5000, 10000. 
   Run server_poll, epoll_lt_server, epoll_et_server and io_uring_opt_server (skip blocking 
   and select, which can't handle these counts). 5 trials, median.
 - Output a CSV: server,idle_conns,median_req_s,median_p99_ms.
 - Make a plot (matplotlib, PNG): x = idle connections, y = req/s, one line per server, 
   plus a second plot for p99 latency. Mark where poll and epoll cross if they do.

DELIVERABLES
 1. New/updated source files, scripts (e.g. code/scripts/exp1_events_per_wait.sh, 
    exp2_cpu_per_req.sh, exp3_memory.sh, exp4_idle_sweep.sh) and a Makefile target 
    that builds the *_stats binaries.
 2. All CSVs and PNGs in a results/ folder.
 3. A FINDINGS.md that answers, with numbers:
    a) Does poll get more events per wakeup than epoll when all conns are active?
    b) Is io_uring cheaper in CPU per request than epoll? Is the client the bottleneck?
    c) What causes the memory increase and how much of it is avoidable?
    d) At how many idle connections does epoll overtake poll?
    Mark each conclusion as "measured" or "inferred", and don't claim anything the data doesn't show.
 4. Verify every server still compiles with -Wall -Wextra and passes the quick echo test 
    (send "hello", receive "hello") before reporting done.
 5. State your assumptions: kernel version (uname -r), liburing version, and CPU model/core count.
```
