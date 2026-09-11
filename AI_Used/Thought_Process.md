# Human-AI Collaborative Thought Process

**Course**: CS331 - Computer Networks  
**Team ID**: `T002` | **Project ID**: `13`  
**Project Title**: Scalable Network I/O: From select to io_uring  

---

## 🧠 Integration Workflow & Design Philosophy

Our team adopted a **Human-Driven, AI-Accelerated Engineering Workflow**. We maintained strict human oversight over system design, kernel system call requirements, performance metrics, and empirical validation, while using AI as a force multiplier for rapid prototyping and debugging.

```
+-------------------------------------------------------------------------------+
| HUMAN DEVELOPER RESPONSIBILITIES                                              |
|  - Architectural design & choice of server paradigms                          |
|  - System call research (select vs poll vs epoll ET vs io_uring)              |
|  - Defining benchmark parameters (10 to 5,000 conns, p99 latency, RSS memory) |
|  - Code review, error analysis, and physical execution in Linux WSL2          |
+-------------------------------------------------------------------------------+
                                       |
                                       v
+-------------------------------------------------------------------------------+
| AI PAIR-PROGRAMMER ASSISTANCE                                                 |
|  - Boilerplate code synthesis (POSIX socket APIs, fcntl setters)              |
|  - Liburing function signature verification (io_uring_prep_read, SQE/CQE)     |
|  - Debugging concurrency crashes (refactoring load harness to asyncio)        |
|  - Matplotlib visualization generation & Markdown report structuring           |
+-------------------------------------------------------------------------------+
```

---

## 💡 Key Principles of Our AI Workflow

1. **Empirical Verification First**: Every code block or script generated with AI assistance was compiled with `-O3 -Wall -Wextra` and verified using an automated functional test suite (`scripts/test_servers.py`) before accepting into main branch.
2. **No Blind Trust**: When initial multi-threaded Python benchmark scripts failed at 5,000 connections due to OS thread stack limits, our team identified the root cause (`can't start new thread`) and guided the AI to refactor the harness to a single-threaded non-blocking `asyncio` event loop.
3. **Data Authenticity**: All throughput, p99 latency, and RAM RSS metrics in our benchmark tables and charts reflect **actual empirical measurements** collected from running binaries on Linux kernel 6.6, never AI-hallucinated dummy numbers.
