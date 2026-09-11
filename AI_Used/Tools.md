# AI Tools Utilized & Division of Work

## 📋 Overview

Our team (**Team T002**) integrated AI assistants into a **Human-Driven, AI-Accelerated Engineering Workflow** for **CS331 Project #13: Scalable Network I/O**. We maintained full ownership of system architecture, Linux kernel socket semantics, empirical benchmarking methodology, and code validation, leveraging AI as an interactive pair-programmer for syntax verification, boilerplate generation, and visualization formatting.

---

## 🛠️ AI Tools Catalog

### 1. Primary AI Coding Agent: Google DeepMind Antigravity / Gemini 3.6 Flash
- **Usage Scope**: Active C pair-programming, POSIX socket API verification, `liburing` queue helper function lookup, `asyncio` benchmarking harness refactoring, and Matplotlib plotting scripts.
- **Human Interface**: Interactive chat prompt sessions in VS Code / Antigravity IDE.

### 2. Conceptual & Research Assistant: OpenAI ChatGPT / Claude 3.5 Sonnet
- **Usage Scope**: Cross-verifying theoretical complexity models ($O(N)$ vs $O(1)$), inspecting kernel Edge-Triggered (`EPOLLET`) readiness conditions, and analyzing `io_uring` kernel memory-mapped ring buffer mechanics (`IORING_SETUP_SQPOLL`).

---

## ⚙️ Student Technical Environment & Toolchain

The human engineering team configured, tested, and executed the entire codebase on the following environment:

| Component | Specification / Version | Responsible Team Member(s) |
| :--- | :--- | :--- |
| **OS Kernel Environment** | WSL2 / Ubuntu 24.04 LTS (Linux 6.6.36 Kernel) | **Suchith** & **Rohith** |
| **Compiler & Flags** | GCC 13.3.0 (`-O3 -Wall -Wextra -luring`) | **Rohith** |
| **Async Harness Runtime** | Python 3.12 (`asyncio`, `socket`, `time`, `json`) | **Hanook** |
| **Data Visualization** | Python `matplotlib`, `pandas`, `numpy` | **Hanook** |
| **Kernel Profiling Tools** | `strace`, `valgrind`, `htop`, `ulimit`, `ss` | **Harshith** & **Rohith** |
| **C Libraries Used** | POSIX Sockets, `<sys/select.h>`, `<poll.h>`, `<sys/epoll.h>`, `<liburing.h>` | **All Members** |
