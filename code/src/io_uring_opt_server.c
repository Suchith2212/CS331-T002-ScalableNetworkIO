#include "../include/common.h"
#include <liburing.h>
#include <netinet/tcp.h>

#ifdef STATS
#include <time.h>
#include <math.h>
// Compile-time optional instrumentation for wait call & event frequency (Exp 1 & Task 5)
static volatile sig_atomic_t g_stop = 0;
static unsigned long long g_waits = 0;
static unsigned long long g_events = 0;
static unsigned long long g_requests = 0;
static struct timespec g_start_time;

static void stats_sig_handler(int sig) {
    (void)sig;
    g_stop = 1;
}
#endif

// Helper to disable Nagle's algorithm for low-latency request-response packets
static inline void set_tcp_nodelay(int fd) {
    int opt = 1;
    setsockopt(fd, IPPROTO_TCP, TCP_NODELAY, &opt, sizeof(opt));
}

#define ENTRIES          16384 // Ring capacity sized for massive concurrent workloads
#define MAX_FDS          65536 // Descriptor tracking capacity
#define BUF_RING_ENTRIES 8192  // Number of pre-allocated buffers in the provided buffer ring
#define BGID             1     // Buffer Group ID

#define EVENT_ACCEPT     0
#define EVENT_RECV       1
#define EVENT_SEND       2

// Tag encoder/decoder to pass operation metadata through 64-bit user_data with zero heap allocations
#define MAKE_TAG(type, fd, bid) (((uint64_t)(type) << 48) | ((uint64_t)(bid) << 32) | ((uint64_t)(uint32_t)(fd)))
#define TAG_TYPE(tag)           ((int)((tag) >> 48))
#define TAG_BID(tag)            ((int)(((tag) >> 32) & 0xFFFF))
#define TAG_FD(tag)             ((int)((tag) & 0xFFFFFFFF))

// Compact per-connection state
struct conn_state {
    int fd;
    int active;
};

static struct conn_state conns[MAX_FDS];
static char buf_storage[BUF_RING_ENTRIES][BUF_SIZE];
static struct io_uring_buf_ring *br = NULL;

// Recycle a buffer back to the kernel provided buffer ring
static inline void return_buffer(int bid) {
    int mask = io_uring_buf_ring_mask(BUF_RING_ENTRIES);
    io_uring_buf_ring_add(br, buf_storage[bid], BUF_SIZE, bid, mask, 0);
    io_uring_buf_ring_advance(br, 1);
}

// Flushes the submission queue if full to guarantee no SQEs are ever dropped
static inline struct io_uring_sqe *get_sqe_safe(struct io_uring *ring) {
    struct io_uring_sqe *sqe = io_uring_get_sqe(ring);
    if (!sqe) {
        io_uring_submit(ring);
        sqe = io_uring_get_sqe(ring);
    }
    return sqe;
}

static void add_multishot_accept(struct io_uring *ring, int listen_fd) {
    struct io_uring_sqe *sqe = get_sqe_safe(ring);
    if (!sqe) return;
    io_uring_prep_multishot_accept(sqe, listen_fd, NULL, NULL, 0);
    io_uring_sqe_set_data64(sqe, MAKE_TAG(EVENT_ACCEPT, listen_fd, 0));
}

static void add_multishot_recv(struct io_uring *ring, int fd) {
    struct io_uring_sqe *sqe = get_sqe_safe(ring);
    if (!sqe) return;
    // Multishot recv using IOSQE_BUFFER_SELECT from provided buffer ring
    io_uring_prep_recv_multishot(sqe, fd, NULL, 0, 0);
    sqe->flags |= IOSQE_BUFFER_SELECT;
    sqe->buf_group = BGID;
    io_uring_sqe_set_data64(sqe, MAKE_TAG(EVENT_RECV, fd, 0));
}

static void add_send(struct io_uring *ring, int fd, int bid, size_t len) {
    struct io_uring_sqe *sqe = get_sqe_safe(ring);
    if (!sqe) {
        return_buffer(bid);
        return;
    }
    io_uring_prep_send(sqe, fd, buf_storage[bid], len, 0);
    io_uring_sqe_set_data64(sqe, MAKE_TAG(EVENT_SEND, fd, bid));
}

int main(int argc, char *argv[]) {
    int port = PORT;
    if (argc > 1) {
        port = atoi(argv[1]);
    }

    signal(SIGPIPE, SIG_IGN);
#ifdef STATS
    signal(SIGINT, stats_sig_handler);
    signal(SIGTERM, stats_sig_handler);
    clock_gettime(CLOCK_MONOTONIC, &g_start_time);
#endif

    int listen_fd = make_listener(port);
    set_nonblocking(listen_fd);

    struct io_uring ring;
    struct io_uring_params params;
    const char *mode_str = "DEFER_TASKRUN";

    // Attempt 1: IORING_SETUP_SINGLE_ISSUER | IORING_SETUP_DEFER_TASKRUN (Linux 6.1+)
    memset(&params, 0, sizeof(params));
    params.flags = IORING_SETUP_SINGLE_ISSUER | IORING_SETUP_DEFER_TASKRUN;
    if (io_uring_queue_init_params(ENTRIES, &ring, &params) < 0) {
        // Attempt 2: Fallback to COOP_TASKRUN | SINGLE_ISSUER (Linux 5.19+)
        memset(&params, 0, sizeof(params));
        params.flags = IORING_SETUP_COOP_TASKRUN | IORING_SETUP_SINGLE_ISSUER;
        mode_str = "COOP_TASKRUN";
        if (io_uring_queue_init_params(ENTRIES, &ring, &params) < 0) {
            // Attempt 3: Standard default mode
            mode_str = "DEFAULT";
            if (io_uring_queue_init(ENTRIES, &ring, 0) < 0) {
                perror("io_uring_queue_init");
                exit(EXIT_FAILURE);
            }
        }
    }

    printf("[io_uring_opt] Server running on port %d (Mode: %s, Multishot + Buffer Ring)\n", port, mode_str);

    // Setup Provided Buffer Ring (IORING_OP_PROVIDE_BUFFERS via ring buffer)
    int ret = 0;
    br = io_uring_setup_buf_ring(&ring, BUF_RING_ENTRIES, BGID, 0, &ret);
    if (!br) {
        fprintf(stderr, "Failed to setup buffer ring: %d\n", ret);
        exit(EXIT_FAILURE);
    }
    io_uring_buf_ring_init(br);
    int mask = io_uring_buf_ring_mask(BUF_RING_ENTRIES);
    for (int i = 0; i < BUF_RING_ENTRIES; ++i) {
        io_uring_buf_ring_add(br, buf_storage[i], BUF_SIZE, i, mask, i);
    }
    io_uring_buf_ring_advance(br, BUF_RING_ENTRIES);

    // Arm initial multishot accept
    add_multishot_accept(&ring, listen_fd);

#ifdef STATS
    while (!g_stop) {
        g_waits++;
#else
    while (1) {
#endif
        // Single unified syscall: submits queued SQEs and waits for at least 1 CQE
        int s_ret = io_uring_submit_and_wait(&ring, 1);
        if (s_ret < 0) {
            if (s_ret == -EINTR) {
#ifdef STATS
                if (g_stop) break;
#endif
                continue;
            }
            if (s_ret == -EAGAIN) continue;
            fprintf(stderr, "io_uring_submit_and_wait error: %s\n", strerror(-s_ret));
            break;
        }

        unsigned head;
        struct io_uring_cqe *cqe;
        unsigned count = 0;

        io_uring_for_each_cqe(&ring, head, cqe) {
            count++;
            uint64_t tag = cqe->user_data;
            int type = TAG_TYPE(tag);
            int fd = TAG_FD(tag);
            int res = cqe->res;
            unsigned flags = cqe->flags;

            if (type == EVENT_ACCEPT) {
                if (res >= 0) {
                    int client_fd = res;
                    // Do not call set_nonblocking on client fds for io_uring, but keep TCP_NODELAY
                    set_tcp_nodelay(client_fd);

                    if (client_fd < MAX_FDS) {
                        conns[client_fd].fd = client_fd;
                        conns[client_fd].active = 1;
                        add_multishot_recv(&ring, client_fd);
                    } else {
                        close(client_fd);
                    }
                }

                // Re-arm multishot accept only if kernel terminated multishot stream
                if (!(flags & IORING_CQE_F_MORE)) {
                    add_multishot_accept(&ring, fd);
                }
            } else if (type == EVENT_RECV) {
                if (res > 0) {
#ifdef STATS
                    g_events++; // Task 5: count request-producing ready data event
#endif
                    // Extract allocated buffer ID from CQE flags
                    int bid = flags >> IORING_CQE_BUFFER_SHIFT;
                    add_send(&ring, fd, bid, res);
                } else if (res == -ENOBUFS) {
                    // Buffer ring temporarily exhausted; re-arm recv
                    add_multishot_recv(&ring, fd);
                } else if (res == -EAGAIN || res == -EINTR) {
                    // Transient error; re-arm if multishot stopped
                    if (conns[fd].active && !(flags & IORING_CQE_F_MORE)) {
                        add_multishot_recv(&ring, fd);
                    }
                } else {
                    // EOF (res == 0) or fatal socket error (res < 0)
                    conns[fd].active = 0;
                    close(fd);
                    continue;
                }

                // Re-arm multishot recv if kernel stopped multishot mode
                if (conns[fd].active && !(flags & IORING_CQE_F_MORE)) {
                    add_multishot_recv(&ring, fd);
                }
            } else if (type == EVENT_SEND) {
                int bid = TAG_BID(tag);
                // Return buffer to provided buffer ring now that payload has been sent
                return_buffer(bid);

                if (res < 0 && res != -EAGAIN && res != -EINTR) {
                    // Fatal send error
                    conns[fd].active = 0;
                    close(fd);
                } else if (res > 0) {
#ifdef STATS
                    g_requests++; // Task 5: one completed read-then-full-echo
#endif
                }
            }
        }

        // Advance all processed CQEs in a single atomic batch operation
        io_uring_cq_advance(&ring, count);
    }

#ifdef STATS
    struct timespec end_time;
    clock_gettime(CLOCK_MONOTONIC, &end_time);
    double elapsed = (end_time.tv_sec - g_start_time.tv_sec) + (end_time.tv_nsec - g_start_time.tv_nsec) / 1e9;
    double avg_events = g_waits ? (double)g_events / g_waits : 0.0;
    double waits_per_req = g_requests ? (double)g_waits / g_requests : 0.0;
    double req_per_s = elapsed > 0 ? (double)g_requests / elapsed : 0.0;
    printf("\n[STATS] server=io_uring_opt_server waits=%llu events=%llu requests=%llu avg_events_per_wait=%.4f waits_per_request=%.6f req_per_s=%.2f\n",
           g_waits, g_events, g_requests, avg_events, waits_per_req, req_per_s);
    // Task 5: Consistency self-check between waits_per_request and 1/avg_events_per_wait
    double inv_avg = avg_events > 0.0 ? (1.0 / avg_events) : 0.0;
    double diff = fabs(waits_per_req - inv_avg);
    if (inv_avg > 0.0 && (diff / inv_avg) > 0.10) {
        fprintf(stderr, "[STATS WARNING] server=io_uring_opt_server: waits_per_request (%.4f) and 1/avg_events (%.4f) disagree by >10%%!\n",
                waits_per_req, inv_avg);
    }
    fflush(stdout);
#endif

    if (br) {
        io_uring_free_buf_ring(&ring, br, BUF_RING_ENTRIES, BGID);
    }
    io_uring_queue_exit(&ring);
    close(listen_fd);
    return 0;
}
