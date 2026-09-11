# AI Tools Documentation

**Course**: CS331 - Computer Networks  
**Team ID**: `T002` | **Project ID**: `13`  
**Project Title**: Scalable Network I/O: From select to io_uring  
**Team Members**: Suchith (`24110313`), Rohith (`24110303`), Harshith (`24110091`), Hanook (`24110378`)  

---

## 🛠️ AI Tools Utilized

Our engineering team integrated AI tools into a collaborative **Pair-Programming & Research Workflow** during the development, debugging, benchmarking, and reporting phases of this project.

### 1. Primary AI Coding Agent
- **Tool**: Google DeepMind Antigravity / Gemini 3.6 Flash (Agentic Pair-Programmer)
- **Role**: Active pair programming, C socket API syntax verification, `liburing` SQ/CQ queue initialization guidance, automated testing harness generation (`asyncio`), and Matplotlib benchmark visualization scripting.

### 2. Secondary AI Research & Conceptual Assistants
- **Tool**: OpenAI ChatGPT / Claude 3.5 Sonnet
- **Role**: Theoretical conceptual sanity checks regarding $O(N)$ vs. $O(1)$ scaling mechanisms, Edge-Triggered `EPOLLET` socket semantics, and `io_uring` ring buffer memory mapping details.

---

## 💻 Technical Environment & Libraries Used
- **OS Environment**: WSL2 / Ubuntu 24.04 LTS (Linux Kernel 6.6+)
- **Languages**: C (C99 standard), Python 3.12 (Benchmarking & Plotting)
- **C Libraries**: Standard POSIX Sockets, `<sys/select.h>`, `<poll.h>`, `<sys/epoll.h>`, `<liburing.h>`
- **Python Libraries**: `asyncio`, `socket`, `matplotlib`, `pandas`, `pptx`
- **Compiler**: GCC 13.3.0 (`-O3 -Wall -Wextra`)
