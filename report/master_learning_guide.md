# Master Computer Networks Learning & Project Guide: From Sockets to io_uring

**Project Title**: Scalable Network I/O: From select to io_uring  
**Course**: CS331 - Computer Networks  
**Team ID**: `T002` | **Project ID**: `13`  
**Authors**: Suchith (`24110313`), Rohith (`24110303`), Harshith (`24110091`), Hanook (`24110378`)  

---

# SECTION 1: SYSTEMATIC CONCEPTUAL FOUNDATIONS

## 1.1 Sockets and File Descriptors in Linux

In Unix/Linux operating systems, **"Everything is a File"**. Sockets are represented as integer index keys called **File Descriptors (FDs)** in the kernel's process file descriptor table.

### The Socket Lifecycle for TCP:
1. **`socket(AF_INET, SOCK_STREAM, 0)`**: Creates an endpoint for communication. Returns a file descriptor `fd`.
2. **`bind(fd, struct sockaddr *, len)`**: Binds the socket to an IP address and Port (e.g., `0.0.0.0:8080`).
3. **`listen(fd, backlog)`**: Marks the socket as a passive listener accepting incoming client connections. `backlog` defines the maximum queue length of pending connections (`BACKLOG=4096`).
4. **`accept(listen_fd, ...)`**: Extracts the first connection request from the pending queue and creates a **new connected client file descriptor** (`client_fd`).
5. **`read(client_fd, buf, size)` / `write(client_fd, buf, size)`**: Data transfer over the connection.
6. **`close(fd)`**: Closes the socket and releases kernel resources.

```
       SERVER SIDE                             CLIENT SIDE
     +--------------+                        +--------------+
     |   socket()   |                        |   socket()   |
     +------ API ---+                        +------ API ---+
            |                                       |
     +------v-------+                               |
     |    bind()    |                               |
     +------ API ---+                               |
            |                                       |
     +------v-------+                               |
     |   listen()   |                               |
     +------ API ---+                               |
            |                                       |
     +------v-------+         Three-Way             |
     |   accept()   |<------- TCP Handshake ------->|   connect()  |
     +------ API ---+                               +------ API ---+
            |                                       |
     +------v-------+          Data Exchange        +------v-------+
     | read/write() |<=============================>| read/write() |
     +------ API ---+                               +------ API ---+
            |                                       |
     +------v-------+                               +------v-------+
     |   close()    |                               |   close()    |
     +--------------+                               +--------------+
```

---

## 1.2 Blocking vs. Non-Blocking Sockets

### Blocking Sockets (Default)
When a socket is in **blocking mode**, calling `read()` or `accept()` puts the executing thread/process to sleep until an event occurs (e.g., data arrives or a client connects).
- **Advantage**: Simple sequential code flow.
- **Disadvantage**: Thread cannot perform any other work while waiting.

### Non-Blocking Sockets (`O_NONBLOCK`)
By calling `fcntl(fd, F_SETFL, flags | O_NONBLOCK)`, the socket is configured as **non-blocking**.
- If no data is available during `read()` or no client is pending during `accept()`, the system call returns **immediately** with an error code:
  - `EAGAIN` or `EWOULDBLOCK`.
- The thread can continue executing without being suspended.

---

## 1.3 The C10K / C100K Concurrency Problem

The **C10K Problem** (handling 10,000 concurrent client connections) highlights the physical limits of traditional concurrency models:

### Why Thread-per-Client Fails:
1. **Memory Allocation**: Each OS thread allocates a stack frame (~2 MB to 8 MB). 10,000 threads require ~20 GB to 80 GB of RAM purely for idle thread stacks!
2. **CPU Context Switching**: The CPU scheduler must save registers, flush TLB caches, and restore thread states thousands of times per second. CPU cache thrashing reduces throughput dramatically.

---

## 1.4 Linux I/O Multiplexing & Paradigm Evolution

To solve C10K, single-threaded **I/O Multiplexing** was introduced, allowing one thread to monitor thousands of file descriptors simultaneously.

```
+-----------------------------------------------------------------------------------+
| Synchronous Readiness Notification (O(N))                                         |
|  - select(): Bitmask fd_set, hard-capped at FD_SETSIZE (1024)                      |
|  - poll(): Dynamic struct pollfd array, no cap, but O(N) array iteration          |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| Scalable Asynchronous Readiness Queue (O(1))                                      |
|  - epoll(): In-kernel Red-Black Tree + Linked Ready List (Edge-Triggered)         |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| Next-Gen Asynchronous Completion Ring (Zero Syscall Batching)                     |
|  - io_uring: Shared SQ / CQ Ring Buffers in memory                                |
+-----------------------------------------------------------------------------------+
```

---

### Level 1: `select()` (POSIX.1-2001)
- Uses fixed-size bitmasks (`fd_set`).
- **Algorithm**: Application sets bits for target sockets and calls `select(max_fd + 1, &readfds, ...)`.
- **Bottlenecks**:
  1. **`FD_SETSIZE` Hard Cap**: Limited to 1024 file descriptors by system header definition. Sockets with descriptor value $\ge 1024$ cause memory corruptions.
  2. **Memory Copying**: Bitmasks are copied from user space to kernel space and back on *every single call*.
  3. **$O(N)$ Scanning**: The kernel and user program must inspect every bit from index `0` to `max_fd`.

---

### Level 2: `poll()` (SVR4)
- Replaces fixed bitmasks with a dynamic array of `struct pollfd`:
  ```c
  struct pollfd {
      int fd;        // File descriptor
      short events;  // Requested events (POLLIN, POLLOUT)
      short revents; // Returned events
  };
  ```
- **Improvement**: Removes the 1024 FD limit.
- **Remaining Bottleneck**: Still $O(N)$ linear scanning. The kernel must iterate through all elements in the `pollfd` array to check event status.

---

### Level 3: `epoll()` (Linux 2.5.44+)
`epoll` solves $O(N)$ degradation using three distinct system calls:
1. **`epoll_create1(flags)`**: Allocates an epoll kernel instance.
2. **`epoll_ctl(epfd, op, fd, event)`**: Adds, modifies, or deletes watched FDs in an **in-kernel Red-Black Tree**. Descriptors are registered **once**, avoiding per-iteration memory copying.
3. **`epoll_wait(epfd, events, maxevents, timeout)`**: Suspends execution until activity occurs.

#### How `epoll` Achieves $O(1)$ Complexity:
When network activity occurs, NIC hardware interrupts trigger kernel driver callbacks that append ready sockets to a **ready list** (linked list). `epoll_wait()` simply reads the ready list in $O(1)$ time, returning only active sockets!

#### Level-Triggered (LT) vs. Edge-Triggered (ET / `EPOLLET`):
- **Level-Triggered (Default)**: `epoll_wait()` notifies you repeatedly as long as data remains in the read buffer.
- **Edge-Triggered (`EPOLLET`)**: `epoll_wait()` notifies you **only once** when state transitions from no-data to data-available.
  - **Requirement**: Socket MUST be non-blocking (`O_NONBLOCK`).
  - **Requirement**: You MUST loop `read()` / `accept()` until it returns `EAGAIN` or `EWOULDBLOCK`.

---

### Level 4: `io_uring` (Linux 5.1+)
`io_uring` shifts the model from **Readiness Notification** to **Asynchronous Completion**.

#### Ring Buffer Architecture:
`io_uring` creates two lockless ring buffers shared directly in memory between user space and kernel space:
1. **Submission Queue (SQ)**: Application writes Submission Queue Entries (SQEs) describing operations (`IORING_OP_ACCEPT`, `IORING_OP_READ`, `IORING_OP_WRITE`).
2. **Completion Queue (CQ)**: Kernel executes operations asynchronously and posts Completion Queue Entries (CQEs) containing completion results (`res`).

```
  +-----------------------------------------------------------------------+
  |                             USER SPACE                                |
  |                                                                       |
  |  +------------------------+              +-------------------------+  |
  |  | Submission Queue (SQ)  |              |  Completion Queue (CQ)  |  |
  |  | [SQE1] [SQE2] [SQE3]   |              |  [CQE1] [CQE2] [CQE3]   |  |
  |  +-----------+------------+              +------------^------------+  |
  +--------------|----------------------------------------|---------------+
                 | Shared Memory Ring Buffers             |
  +--------------|----------------------------------------|---------------+
  |  +-----------v------------+              +------------|------------+  |
  |  |   Kernel SQ Consumer   |              |   Kernel CQ Producer    |  |
  |  +------------------------+              +-------------------------+  |
  |                                                                       |
  |                             KERNEL SPACE                              |
  +-----------------------------------------------------------------------+
```

#### Key Advantages:
- **Zero-Syscall Batching**: Multiple I/O requests are posted to SQEs and submitted in a single `io_uring_submit()` call, avoiding system call context switching per packet.

---

# SECTION 2: SYSTEMATIC CODEBASE WALKTHROUGH

## 2.1 Shared Header Architecture (`code/include/common.h`)

The shared header defines constants, headers, and essential non-blocking socket setup helpers.

```c
#pragma once
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <fcntl.h>
#include <sys/socket.h>
#include <sys/select.h>
#include <poll.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <signal.h>

#define PORT        8080
#define BACKLOG     4096
#define BUF_SIZE    4096
#define MAX_EVENTS  16384

// Sets a file descriptor to non-blocking mode via fcntl
static inline void set_nonblocking(int fd) {
    int f = fcntl(fd, F_GETFL, 0);
    fcntl(fd, F_SETFL, f | O_NONBLOCK);
}

// Creates, configures SO_REUSEADDR/SO_REUSEPORT, binds, and listens on port
static inline int make_listener(int port) {
    int fd = socket(AF_INET, SOCK_STREAM, 0);
    int opt = 1;
    setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));
#ifdef SO_REUSEPORT
    setsockopt(fd, SOL_SOCKET, SO_REUSEPORT, &opt, sizeof(opt));
#endif

    struct sockaddr_in a;
    memset(&a, 0, sizeof(a));
    a.sin_family = AF_INET;
    a.sin_port = htons(port);
    a.sin_addr.s_addr = INADDR_ANY;

    bind(fd, (struct sockaddr *)&a, sizeof(a));
    listen(fd, BACKLOG);
    printf("[server] Listening on :%d\n", port);
    return fd;
}
```

---

## 2.2 Server 1: Baseline Thread-per-Client (`code/src/server_blocking.c`)

Each incoming connection spawns a POSIX thread:

```c
void *client_handler(void *arg) {
    int client_fd = *(int *)arg;
    free(arg);
    char buf[BUF_SIZE];

    while (1) {
        ssize_t bytes_read = read(client_fd, buf, sizeof(buf));
        if (bytes_read <= 0) break; // Error or disconnect

        ssize_t total_written = 0;
        while (total_written < bytes_read) {
            ssize_t n = write(client_fd, buf + total_written, bytes_read - total_written);
            if (n <= 0) break;
            total_written += n;
        }
        if (total_written < bytes_read) break;
    }

    close(client_fd);
    return NULL;
}

int main(int argc, char *argv[]) {
    int port = (argc > 1) ? atoi(argv[1]) : PORT;
    signal(SIGPIPE, SIG_IGN);
    int listen_fd = make_listener(port);

    while (1) {
        struct sockaddr_in client_addr;
        socklen_t client_len = sizeof(client_addr);
        int client_fd = accept(listen_fd, (struct sockaddr *)&client_addr, &client_len);
        if (client_fd < 0) continue;

        pthread_t thread_id;
        int *pfd = malloc(sizeof(int));
        *pfd = client_fd;
        pthread_create(&thread_id, NULL, client_handler, pfd);
        pthread_detach(thread_id);
    }
    return 0;
}
```

---

## 2.3 Server 2: `select()` Implementation (`code/src/server_select.c`)

Implements `select()` event loop with explicit `FD_SETSIZE` guards:

```c
int main(int argc, char *argv[]) {
    int port = (argc > 1) ? atoi(argv[1]) : PORT;
    signal(SIGPIPE, SIG_IGN);
    int listen_fd = make_listener(port);
    set_nonblocking(listen_fd);

    fd_set master_set, readfds;
    FD_ZERO(&master_set);
    FD_SET(listen_fd, &master_set);
    int max_fd = listen_fd;

    char buf[BUF_SIZE];
    while (1) {
        readfds = master_set; // Copy master set as select() mutates it
        int activity = select(max_fd + 1, &readfds, NULL, NULL, NULL);
        if (activity < 0) continue;

        for (int i = 0; i <= max_fd; ++i) {
            if (!FD_ISSET(i, &readfds)) continue;

            if (i == listen_fd) {
                // Accept incoming client
                int client_fd = accept(listen_fd, NULL, NULL);
                if (client_fd >= FD_SETSIZE) {
                    close(client_fd); // Reject FD >= 1024
                    continue;
                }
                set_nonblocking(client_fd);
                FD_SET(client_fd, &master_set);
                if (client_fd > max_fd) max_fd = client_fd;
            } else {
                // Handle client read/write
                ssize_t bytes_read = read(i, buf, sizeof(buf));
                if (bytes_read <= 0) {
                    close(i);
                    FD_CLR(i, &master_set);
                } else {
                    write(i, buf, bytes_read);
                }
            }
        }
    }
    return 0;
}
```

---

## 2.4 Server 3: `poll()` Implementation (`code/src/server_poll.c`)

Dynamic `struct pollfd` array removing the 1024 FD limit:

```c
int main(int argc, char *argv[]) {
    int port = (argc > 1) ? atoi(argv[1]) : PORT;
    signal(SIGPIPE, SIG_IGN);
    int listen_fd = make_listener(port);
    set_nonblocking(listen_fd);

    size_t poll_cap = 1024;
    struct pollfd *fds = malloc(poll_cap * sizeof(struct pollfd));
    fds[0].fd = listen_fd;
    fds[0].events = POLLIN;
    nfds_t nfds = 1;

    char buf[BUF_SIZE];
    while (1) {
        poll(fds, nfds, -1);
        nfds_t current_nfds = nfds;
        int compress = 0;

        for (nfds_t i = 0; i < current_nfds; ++i) {
            if (fds[i].revents == 0) continue;

            if (fds[i].fd == listen_fd) {
                int client_fd = accept(listen_fd, NULL, NULL);
                if (client_fd < 0) continue;
                set_nonblocking(client_fd);

                if (nfds >= poll_cap) {
                    poll_cap *= 2;
                    fds = realloc(fds, poll_cap * sizeof(struct pollfd));
                }
                fds[nfds].fd = client_fd;
                fds[nfds].events = POLLIN;
                nfds++;
            } else {
                ssize_t bytes_read = read(fds[i].fd, buf, sizeof(buf));
                if (bytes_read <= 0) {
                    close(fds[i].fd);
                    fds[i].fd = -1;
                    compress = 1;
                } else {
                    write(fds[i].fd, buf, bytes_read);
                }
            }
        }
        // Compact array if FDs were closed
        if (compress) {
            for (nfds_t i = 0; i < nfds; ++i) {
                if (fds[i].fd == -1) {
                    for (nfds_t j = i; j < nfds - 1; ++j) fds[j] = fds[j + 1];
                    i--;
                    nfds--;
                }
            }
        }
    }
    return 0;
}
```

---

## 2.5 Server 4: `epoll()` Edge-Triggered (`code/src/server_epoll.c`)

$O(1)$ Edge-Triggered (`EPOLLET`) non-blocking server:

```c
int main(int argc, char *argv[]) {
    int port = (argc > 1) ? atoi(argv[1]) : PORT;
    signal(SIGPIPE, SIG_IGN);
    int listen_fd = make_listener(port);
    set_nonblocking(listen_fd);

    int epoll_fd = epoll_create1(0);
    struct epoll_event ev, events[MAX_EVENTS];
    ev.events = EPOLLIN | EPOLLET;
    ev.data.fd = listen_fd;
    epoll_ctl(epoll_fd, EPOLL_CTL_ADD, listen_fd, &ev);

    char buf[BUF_SIZE];
    while (1) {
        int nfds = epoll_wait(epoll_fd, events, MAX_EVENTS, -1);
        for (int i = 0; i < nfds; ++i) {
            int fd = events[i].data.fd;

            if (fd == listen_fd) {
                // Edge-triggered accept loop: accept ALL pending clients
                while (1) {
                    int client_fd = accept(listen_fd, NULL, NULL);
                    if (client_fd < 0) {
                        if (errno == EAGAIN || errno == EWOULDBLOCK) break;
                        break;
                    }
                    set_nonblocking(client_fd);
                    ev.events = EPOLLIN | EPOLLET;
                    ev.data.fd = client_fd;
                    epoll_ctl(epoll_fd, EPOLL_CTL_ADD, client_fd, &ev);
                }
            } else {
                // Edge-triggered read loop: read until EAGAIN
                int disconnect = 0;
                while (1) {
                    ssize_t bytes_read = read(fd, buf, sizeof(buf));
                    if (bytes_read < 0) {
                        if (errno == EAGAIN || errno == EWOULDBLOCK) break; // Buffer drained
                        disconnect = 1; break;
                    } else if (bytes_read == 0) {
                        disconnect = 1; break;
                    }
                    write(fd, buf, bytes_read);
                }
                if (disconnect) {
                    epoll_ctl(epoll_fd, EPOLL_CTL_DEL, fd, NULL);
                    close(fd);
                }
            }
        }
    }
    return 0;
}
```

---

## 2.6 Server 5: `io_uring` Asynchronous Engine (`code/src/server_uring.c`)

Completion queue ring buffer processing using `liburing`:

```c
#include <liburing.h>

#define EVENT_ACCEPT 0
#define EVENT_READ   1
#define EVENT_WRITE  2

struct conn_info {
    int fd;
    int type;
    char buf[BUF_SIZE];
    size_t len;
};

static struct conn_info accept_conn;

static void add_accept(struct io_uring *ring, int listen_fd) {
    struct io_uring_sqe *sqe = io_uring_get_sqe(ring);
    accept_conn.fd = listen_fd;
    accept_conn.type = EVENT_ACCEPT;
    io_uring_prep_accept(sqe, listen_fd, NULL, NULL, 0);
    io_uring_sqe_set_data(sqe, &accept_conn);
}

static void add_read(struct io_uring *ring, struct conn_info *conn) {
    struct io_uring_sqe *sqe = io_uring_get_sqe(ring);
    conn->type = EVENT_READ;
    io_uring_prep_read(sqe, conn->fd, conn->buf, BUF_SIZE, 0);
    io_uring_sqe_set_data(sqe, conn);
}

static void add_write(struct io_uring *ring, struct conn_info *conn, size_t len) {
    struct io_uring_sqe *sqe = io_uring_get_sqe(ring);
    conn->type = EVENT_WRITE;
    io_uring_prep_write(sqe, conn->fd, conn->buf, len, 0);
    io_uring_sqe_set_data(sqe, conn);
}

int main(int argc, char *argv[]) {
    int port = (argc > 1) ? atoi(argv[1]) : PORT;
    signal(SIGPIPE, SIG_IGN);
    int listen_fd = make_listener(port);

    struct io_uring ring;
    io_uring_queue_init(4096, &ring, 0);

    add_accept(&ring, listen_fd);
    io_uring_submit(&ring);

    while (1) {
        struct io_uring_cqe *cqe;
        io_uring_wait_cqe(&ring, &cqe);

        struct io_uring_cqe *cqes[MAX_EVENTS];
        unsigned count = io_uring_peek_batch_cqe(&ring, cqes, MAX_EVENTS);
        if (count == 0 && cqe != NULL) { cqes[0] = cqe; count = 1; }

        for (unsigned i = 0; i < count; ++i) {
            struct io_uring_cqe *c = cqes[i];
            struct conn_info *conn = (struct conn_info *)io_uring_cqe_get_data(c);
            int res = c->res;

            if (conn->type == EVENT_ACCEPT) {
                if (res >= 0) {
                    set_nonblocking(res);
                    struct conn_info *client_conn = malloc(sizeof(struct conn_info));
                    client_conn->fd = res;
                    add_read(&ring, client_conn);
                }
                add_accept(&ring, listen_fd); // Re-arm accept request
            } else if (conn->type == EVENT_READ) {
                if (res <= 0) { close(conn->fd); free(conn); }
                else add_write(&ring, conn, res);
            } else if (conn->type == EVENT_WRITE) {
                if (res <= 0) { close(conn->fd); free(conn); }
                else add_read(&ring, conn);
            }
            io_uring_cqe_seen(&ring, c);
        }
        io_uring_submit(&ring);
    }
    return 0;
}
```

---

# SECTION 3: EMPIRICAL BENCHMARKING & RESULTS

## 3.1 Functional Correctness Verification (`code/scripts/test_servers.py`)
All five servers were tested for payload echoing correctness and clean connection tear-downs:

```
Testing bin/server_blocking ... SUCCESS! (Received exact echo payload)
Testing bin/server_select   ... SUCCESS! (Received exact echo payload)
Testing bin/server_poll     ... SUCCESS! (Received exact echo payload)
Testing bin/server_epoll    ... SUCCESS! (Received exact echo payload)
Testing bin/server_uring    ... SUCCESS! (Received exact echo payload)

Result: 5/5 servers passed correctness verification.
```

---

## 3.2 Benchmark Performance Table (`code/results/benchmark_summary.csv`)

| Server Paradigm | 10 Conns (req/s, p99 ms) | 100 Conns (req/s, p99 ms) | 500 Conns (req/s, p99 ms) | 1,000 Conns (req/s, p99 ms) | 2,000 Conns (req/s, p99 ms) | 5,000 Conns (req/s, p99 ms) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`blocking`** | 27,431 (0.66) | 45,467 (3.73) | 37,707 (17.85) | 37,883 (32.25) | 34,660 (74.85) | 32,373 (198.43) |
| **`select()`** | **89,682** (0.23) | **137,089** (1.03) | 117,831 (5.91) | 87,445 (16.93) | *EXCEEDED LIMIT* | *EXCEEDED LIMIT* |
| **`poll()`** | 78,590 (0.37) | 113,644 (1.89) | **123,672** (5.24) | **108,819** (11.52) | **99,640** (37.19) | **77,367** (96.15) |
| **`epoll()`** | 75,667 (0.28) | 94,062 (1.45) | 79,541 (7.87) | 71,059 (16.66) | 65,970 (42.62) | 56,459 (113.29) |
| **`io_uring`** | 65,636 (0.28) | 74,205 (2.17) | 70,026 (8.71) | 64,213 (21.31) | 59,351 (50.02) | 46,399 (165.23) |

---

# SECTION 4: VIVA EXAM MASTER QUESTION & ANSWER LIST

### Q1: What is the file descriptor table?
**Answer**: An in-kernel array allocated per process where integer indexes (file descriptors) map to kernel file object structures representing open files, sockets, or pipes.

### Q2: Why does `select()` fail past 1024 connections?
**Answer**: `select()` uses fixed-size bitmask structures (`fd_set`). `FD_SETSIZE` is hardcoded to 1024 in system C libraries. File descriptor values $\ge 1024$ overflow the bitmask array boundaries.

### Q3: Why does `poll()` degrade under 5,000 connections?
**Answer**: `poll()` uses a dynamic array of `struct pollfd`. Even if only 1 socket has active data, `poll()` requires the kernel and user loop to scan through all 5,000 array elements ($O(N)$ overhead).

### Q4: How does `epoll()` achieve $O(1)$ notification complexity?
**Answer**: `epoll()` registers sockets once in an in-kernel Red-Black Tree. When network hardware interrupts arrive, kernel callbacks append active descriptors to a doubly linked **ready list**. `epoll_wait()` returns only active descriptors in $O(1)$ time.

### Q5: What is Edge-Triggered mode in `epoll()` and why is non-blocking I/O required?
**Answer**: Edge-Triggered (`EPOLLET`) notifies the application **only once** when socket state changes from no-data to data-available. Sockets must be non-blocking, and the application must loop `read()` until `EAGAIN` to prevent leaving unread data stuck in the socket buffer.

### Q6: How does `io_uring` eliminate system call overhead?
**Answer**: `io_uring` uses two lockless ring buffers (Submission Queue and Completion Queue) shared in memory between user space and kernel space. Multiple I/O operations are posted to SQEs and submitted in a single batched call (`io_uring_submit()`), avoiding per-I/O system call context switching.
