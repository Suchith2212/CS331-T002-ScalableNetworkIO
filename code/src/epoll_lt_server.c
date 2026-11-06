#include "../include/common.h"
#include <sys/epoll.h>
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

#define LOCAL_MAX_EVENTS 16384 // Ensure epoll_wait harvests at least 1024 events in one batch
#define MAX_FDS          65536 // Maximum descriptor tracking range

// State container to buffer unsent bytes on partial writes without busy-spinning
struct client_state {
    char wbuf[BUF_SIZE];
    size_t wlen;
    size_t woffset;
};

static struct client_state client_states[MAX_FDS];

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

    int epoll_fd = epoll_create1(EPOLL_CLOEXEC);
    if (epoll_fd < 0) {
        perror("epoll_create1");
        exit(EXIT_FAILURE);
    }

    // Register listener in Level-Triggered mode (default, no EPOLLET)
    struct epoll_event ev, events[LOCAL_MAX_EVENTS];
    ev.events = EPOLLIN;
    ev.data.fd = listen_fd;

    if (epoll_ctl(epoll_fd, EPOLL_CTL_ADD, listen_fd, &ev) < 0) {
        perror("epoll_ctl listen_fd");
        exit(EXIT_FAILURE);
    }

    printf("[epoll_lt] Server running on port %d (Level-Triggered O(1) epoll)\n", port);

    char buf[BUF_SIZE]; // Shared single read buffer

#ifdef STATS
    while (!g_stop) {
        g_waits++;
#else
    while (1) {
#endif
        int nfds = epoll_wait(epoll_fd, events, LOCAL_MAX_EVENTS, -1);
        if (nfds < 0) {
            if (errno == EINTR) {
#ifdef STATS
                if (g_stop) break;
#endif
                continue;
            }
            perror("epoll_wait");
            break;
        }

        for (int i = 0; i < nfds; ++i) {
            int fd = events[i].data.fd;
            uint32_t revents = events[i].events;

            if (fd == listen_fd) {
                // Drain incoming connection queue
                while (1) {
                    struct sockaddr_in client_addr;
                    socklen_t client_len = sizeof(client_addr);
                    int client_fd = accept(listen_fd, (struct sockaddr *)&client_addr, &client_len);
                    if (client_fd < 0) {
                        if (errno == EAGAIN || errno == EWOULDBLOCK) break;
                        perror("accept");
                        break;
                    }

                    set_nonblocking(client_fd);
                    set_tcp_nodelay(client_fd);

                    if (client_fd < MAX_FDS) {
                        client_states[client_fd].wlen = 0;
                        client_states[client_fd].woffset = 0;

                        // Level-Triggered registration: monitor readability without EPOLLET
                        ev.events = EPOLLIN;
                        ev.data.fd = client_fd;
                        if (epoll_ctl(epoll_fd, EPOLL_CTL_ADD, client_fd, &ev) < 0) {
                            perror("epoll_ctl add client");
                            close(client_fd);
                        }
                    } else {
                        close(client_fd);
                    }
                }
            } else {
                // Handle writable event first if a previous partial write was buffered
                if (revents & EPOLLOUT) {
                    struct client_state *cs = &client_states[fd];
                    int error = 0;
                    while (cs->woffset < cs->wlen) {
                        ssize_t n = write(fd, cs->wbuf + cs->woffset, cs->wlen - cs->woffset);
                        if (n < 0) {
                            if (errno == EAGAIN || errno == EWOULDBLOCK) {
                                break; // Kernel send buffer still full, wait for next EPOLLOUT
                            }
                            error = 1;
                            break;
                        }
                        cs->woffset += n;
                    }

                    if (error) {
                        epoll_ctl(epoll_fd, EPOLL_CTL_DEL, fd, NULL);
                        close(fd);
                        cs->wlen = 0;
                        cs->woffset = 0;
                        continue;
                    }

                    if (cs->woffset == cs->wlen) {
                        // Buffer completely drained; switch epoll back to EPOLLIN only
                        cs->wlen = 0;
                        cs->woffset = 0;
                        ev.events = EPOLLIN;
                        ev.data.fd = fd;
                        epoll_ctl(epoll_fd, EPOLL_CTL_MOD, fd, &ev);
#ifdef STATS
                        g_requests++;
#endif
                    }
                }

                // Level-Triggered read: execute EXACTLY ONE read() per readiness notification
                if (revents & EPOLLIN) {
                    ssize_t bytes_read = read(fd, buf, sizeof(buf));
                    if (bytes_read <= 0) {
                        if (bytes_read < 0 && (errno == EAGAIN || errno == EWOULDBLOCK)) {
                            continue;
                        }
                        // EOF or fatal connection error
                        epoll_ctl(epoll_fd, EPOLL_CTL_DEL, fd, NULL);
                        close(fd);
                        client_states[fd].wlen = 0;
                        client_states[fd].woffset = 0;
                    } else {
#ifdef STATS
                        g_events++; // Task 5: count request-producing ready event
#endif
                        // Attempt immediate non-blocking write
                        ssize_t n = write(fd, buf, bytes_read);
                        if (n < 0) {
                            if (errno == EAGAIN || errno == EWOULDBLOCK) {
                                n = 0;
                            } else {
                                // Fatal write error
                                epoll_ctl(epoll_fd, EPOLL_CTL_DEL, fd, NULL);
                                close(fd);
                                client_states[fd].wlen = 0;
                                client_states[fd].woffset = 0;
                                continue;
                            }
                        }

                        // If partial write occurred, buffer unsent bytes and register EPOLLOUT
                        if (n < bytes_read) {
                            struct client_state *cs = &client_states[fd];
                            size_t remaining = bytes_read - n;
                            memcpy(cs->wbuf, buf + n, remaining);
                            cs->wlen = remaining;
                            cs->woffset = 0;

                            ev.events = EPOLLIN | EPOLLOUT;
                            ev.data.fd = fd;
                            epoll_ctl(epoll_fd, EPOLL_CTL_MOD, fd, &ev);
                        } else {
#ifdef STATS
                            g_requests++;
#endif
                        }
                    }
                }
            }
        }
    }

#ifdef STATS
    struct timespec end_time;
    clock_gettime(CLOCK_MONOTONIC, &end_time);
    double elapsed = (end_time.tv_sec - g_start_time.tv_sec) + (end_time.tv_nsec - g_start_time.tv_nsec) / 1e9;
    double avg_events = g_waits ? (double)g_events / g_waits : 0.0;
    double waits_per_req = g_requests ? (double)g_waits / g_requests : 0.0;
    double req_per_s = elapsed > 0 ? (double)g_requests / elapsed : 0.0;
    printf("\n[STATS] server=epoll_lt_server waits=%llu events=%llu requests=%llu avg_events_per_wait=%.4f waits_per_request=%.6f req_per_s=%.2f\n",
           g_waits, g_events, g_requests, avg_events, waits_per_req, req_per_s);
    // Task 5: Consistency self-check between waits_per_request and 1/avg_events_per_wait
    double inv_avg = avg_events > 0.0 ? (1.0 / avg_events) : 0.0;
    double diff = fabs(waits_per_req - inv_avg);
    if (inv_avg > 0.0 && (diff / inv_avg) > 0.10) {
        fprintf(stderr, "[STATS WARNING] server=epoll_lt_server: waits_per_request (%.4f) and 1/avg_events (%.4f) disagree by >10%%!\n",
                waits_per_req, inv_avg);
    }
    fflush(stdout);
#endif

    close(epoll_fd);
    close(listen_fd);
    return 0;
}
