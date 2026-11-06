# AI Interactions and Artifacts

This directory contains records of all AI-assisted engineering sessions for the Linux I/O Multiplexing Benchmark project.

## Directory Structure

```
ai/
├── README.md               # Overview of AI usage and tooling
├── prompts/                # Prompts used across development milestones
│   ├── 01_epoll_io_uring_fixes.md
│   ├── 02_followup_experiments.md
│   ├── 03_new_client_loadgen.md
│   └── 04_repo_restructure.md
└── conversations/          # Complete interactive session transcripts
    ├── session_01.md
    ├── session_02.md
    ├── session_03.md
    └── session_04.md
```

## Tools and Models
- **AI Coding Assistant**: Antigravity (Google DeepMind)
- **Primary Model**: Advanced agentic reasoning models
- **Key Contributions**:
  - Implementation of optimized level-triggered and edge-triggered epoll servers (`epoll_lt_server.c`, `epoll_et_server.c`, `epoll_lt_lean_server.c`).
  - Optimization of io_uring echo server (`io_uring_opt_server.c`) utilizing multishot receive and provided buffer rings.
  - Identification and empirical validation of Python `asyncio` load generator bottleneck.
  - Engineering of a high-headroom, multi-threaded C load generator (`code/loadgen/loadgen.c`).
  - Automation scripts for CPU utilization, context switch accounting, wait batching, idle sweeps, and smaps/sockstat memory profiling.
  - Repository restructuring into a clean academic submission format.
