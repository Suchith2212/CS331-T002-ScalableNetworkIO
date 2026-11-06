# Prompt 03: High-Headroom C Load Generator & Re-benchmarking

```markdown
CONTEXT
I'm benchmarking Linux I/O multiplexing echo servers in C (server_blocking, server_select,
server_poll, epoll_lt_server, epoll_et_server, epoll_lt_lean_server, io_uring_opt_server).
Earlier results came from a single-threaded Python asyncio load generator. The experiments so
far suggest the CLIENT is the bottleneck:
 - The server core was only ~19% busy, and epoll and io_uring throughput were nearly identical.
 - "Client cores 1-15 at ~6.8%" was an average over 15 cores. 6.8% x 15 is about 100% of ONE
   core, so the single-threaded Python client was probably saturated.
 - poll won Scenario 1 despite using MORE CPU per request (6.96 us vs 4.56 us for epoll).
   Likely cause: poll returns big batches (~117 events/call vs ~1.4 for epoll), which are
   cheaper for the client to process. That measures client/server batching interaction, not
   server efficiency.
Goal: replace the load generator with one that has headroom, then re-run the experiments and
see which earlier conclusions survive.

RULES
 - Do NOT change the echo protocol, server behavior, or common.h. Servers stay as they are,
   except for the stats fix in TASK 5.
 - Keep the old Python load generator untouched so I can compare old vs new results.
 - Pin the server to one core (taskset). Client threads go on other cores, one thread per core.
   Run `ulimit -n 65536`. 5 trials per point, report MEDIAN plus min/max (or stddev).
 - Comment every change with a short "why".
 - Never report a conclusion as "measured" unless a CSV in results/ supports it.

TASK 1: prove or disprove the client bottleneck (on the OLD client)
 - Re-run server_poll, epoll_lt_server and io_uring_opt_server at 100, 1000 and 5000 conns
   with the old Python client.
 - Measure CPU per PROCESS/THREAD, not averaged over cores: use `pidstat -t -p <pid> 1` or read
   /proc/<pid>/task/*/stat before and after a 10 s steady window. Also record `mpstat -P ALL 1`.
 - Report: client busiest-thread utilization, server-core utilization. Flag any run where the
   busiest client thread is above 90%.
 - Output results/client_bottleneck_check.csv and say plainly whether the old client was saturated.

TASK 2: build a high-headroom load generator in C (code/loadgen/loadgen.c)
 - Same protocol as the existing client: each connection sends one message of the same size,
   waits for the full echo, then sends again (closed loop). Check the old client's message size
   and match it exactly.
 - Multi-threaded: N worker threads (CLI flag), each pinned to its own core with
   pthread_setaffinity_np, each running its own epoll loop over its share of the connections,
   non-blocking sockets, TCP_NODELAY, no shared state in the hot path.
 - CLI: --host --port --conns N --active M (the rest of the connections stay idle: connected but
   silent) --threads T --duration S --warmup S --cores LIST
 - Latency: per-thread histogram in microsecond buckets (up to ~1 s, with an overflow bucket),
   merged at the end for p50/p99/p99.9. No malloc in the hot path.
 - Ignore the first WARMUP seconds. Count only completed request/response pairs in the
   steady-state window. Print a single machine-readable line:
   req_s=... p50_us=... p99_us=... p999_us=... errors=... max_thread_cpu_pct=...
 - Report each worker thread's CPU utilization at the end (getrusage RUSAGE_THREAD or
   /proc/self/task) and print a WARNING if any thread is above 85%.
 - Handle partial reads/writes correctly and verify the echoed bytes match the sent bytes
   (count mismatches as errors).

TASK 3: calibrate the new client (do this BEFORE trusting any server result)
 - Write a trivial reference echo server (single thread, epoll LT, shared buffer).
 - Scale client threads (1, 2, 4, 8...) until the server core is above 90% busy while no client
   thread is above 85%. Record the thread count that achieves this and save
   results/calibration.csv.
 - If the server core cannot be saturated, say so explicitly and report how close it got.
   Every later result then has to carry the caveat "client-limited".
 - Use that thread count for all later runs.

TASK 4: re-run the experiments with the new client
 a) Scenario 1: 10, 100, 500, 1000, 2000, 5000 active conns for server_blocking, server_select
    (up to 1000 only), server_poll, epoll_lt, epoll_et, epoll_lt_lean, io_uring_opt.
    Output results/s1_new_client.csv with req/s median, min, max, p99 median, server core
    utilization, busiest client thread utilization.
 b) CPU per request (server utime+stime delta over the 10 s window / requests counted by the
    load generator) at 100, 1000, 5000 conns, plus voluntary and involuntary context switches.
    Results go in results/cpu_per_req_new_client.csv. If `perf` is available also run
    `perf stat -e task-clock,context-switches,cycles,instructions -p <pid>`.
 c) Events per wakeup, using the -DSTATS builds, at 100, 1000, 5000 conns:
    results/events_per_wait_new_client.csv.
 d) Idle sweep with 100 active conns and idle = 0, 500, 1000, 2000, 3000, 4000, 5000, 7500,
    10000 for poll, epoll_lt, epoll_et, io_uring_opt. Output results/idle_sweep_new_client.csv
    and PNGs (req/s and p99 vs idle conns, one line per server, with min/max error bars).
    Report the crossover as the BRACKET between the two idle counts where the ordering flips.
    Also give the linearly interpolated value, labelled as an estimate.

TASK 5: fix the stats counting
 - In the -DSTATS builds, waits_per_request should roughly equal 1 / avg_events_per_wait when
   each event produces one request. Earlier numbers (1.37-1.40 events/wait but 0.801
   waits/request, where 1/1.38 is about 0.72) don't match. Find out why (ET draining? requests
   counted differently?), fix the counting so all servers count "request" identically (one
   completed read-then-full-echo), and add a self-check that prints a warning when the two
   quantities disagree by more than 10%.

TASK 6: memory, including kernel memory
 - VmRSS excludes kernel socket buffers, so it understates real cost. For each server at 0,
   1000 and 5000 connections also record:
   * VmRSS, VmData, and Pss from /proc/<pid>/smaps_rollup
   * system-wide deltas of "MemAvailable" (/proc/meminfo) and TCP memory pages
     (/proc/net/sockstat) relative to the idle baseline
 - Output results/memory_new.csv with a column that separates user-space memory from
   kernel/socket memory. Describe io_uring's provided buffer ring as a "shared buffer pool
   (no per-connection buffer)", not as zero-copy.

TASK 7: FINDINGS_v2.md
 Answer with numbers, marking each statement [MEASURED] (cite the CSV) or [INFERRED]:
 a) Was the old client saturated? Evidence from TASK 1.
 b) Does poll still beat epoll/io_uring in Scenario 1 with the new client? If poll's lead
    shrinks or reverses, state by how much. Compare old vs new in a table.
 c) Is the server core now busy (>90%) in Scenario 1? If not, say the run is still client-limited.
 d) io_uring vs epoll_et CPU per request: report the difference with its spread across trials.
    If it's within trial-to-trial noise, call them equivalent. Don't claim "lowest" for a
    difference smaller than the noise.
 e) Events per wakeup with the new client: does poll still batch ~100 events per call?
 f) The poll/epoll crossover as a bracket, from the finer idle sweep.
 g) Which of my earlier conclusions changed after switching clients, and which held up.
 Do not offer explanations (cache effects, etc.) unless a measurement supports them. Label
 anything else as a hypothesis.

DELIVERABLES
 1. loadgen.c, the Makefile targets, calibration and experiment scripts
    (code/scripts/exp_v2_*.sh), reference server.
 2. All CSVs and PNGs in results/.
 3. FINDINGS_v2.md.
 4. Verify everything compiles with -Wall -Wextra and passes the functional echo test
    ("hello" -> "hello") through the NEW load generator against every server.
 5. State assumptions: kernel version, liburing version, CPU model, core count, and which cores
    were assigned to server and client threads.
```
