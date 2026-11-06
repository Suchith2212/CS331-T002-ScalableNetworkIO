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

static inline void set_tcp_nodelay(int fd) {
    int opt = 1;
    setsockopt(fd, IPPROTO_TCP, TCP_NODELAY, &opt, sizeof(opt));
}

#define LOCAL_MAX_EVENTS 16384
#define MAX_FDS          65536

// On-demand allocated structure for partial write remainder
struct pending_write {
    char *buf;
    size_t len;
    size_t offset;
};

// Pointer array: only 512 KB in BSS, zero memory allocated per connection unless partial write occurs
static struct pending_write *pending_writes[MAX_FDS];

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

    struct epoll_event ev, events[LOCAL_MAX_EVENTS];
    ev.events = EPOLLIN;
    ev.data.fd = listen_fd;

    if (epoll_ctl(epoll_fd, EPOLL_CTL_ADD, listen_fd, &ev) < 0) {
        perror("epoll_ctl listen_fd");
        exit(EXIT_FAILURE);
    }

    printf("[epoll_lt_lean] Server running on port %d (Lean Level-Triggered epoll, on-demand write buffer)\n", port);

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
                        pending_writes[client_fd] = NULL;
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
                // Handle writable event if previous write was partial
                if (revents & EPOLLOUT) {
                    struct pending_write *pw = pending_writes[fd];
                    if (pw) {
                        int error = 0;
                        while (pw->offset < pw->len) {
                            ssize_t n = write(fd, pw->buf + pw->offset, pw->len - pw->offset);
                            if (n < 0) {
                                if (errno == EAGAIN || errno == EWOULDBLOCK) break;
                                error = 1;
                                break;
                            }
                            pw->offset += n;
                        }

                        if (error) {
                            epoll_ctl(epoll_fd, EPOLL_CTL_DEL, fd, NULL);
                            close(fd);
                            free(pw->buf);
                            free(pw);
                            pending_writes[fd] = NULL;
                            continue;
                        }

                        if (pw->offset == pw->len) {
                            free(pw->buf);
                            free(pw);
                            pending_writes[fd] = NULL;
                            ev.events = EPOLLIN;
                            ev.data.fd = fd;
                            epoll_ctl(epoll_fd, EPOLL_CTL_MOD, fd, &ev);
#ifdef STATS
                            g_requests++;
#endif
                        }
                    }
                }

                // Level-Triggered read: execute EXACTLY ONE read() per event
                if (revents & EPOLLIN) {
                    ssize_t bytes_read = read(fd, buf, sizeof(buf));
                    if (bytes_read <= 0) {
                        if (bytes_read < 0 && (errno == EAGAIN || errno == EWOULDBLOCK)) {
                            continue;
                        }
                        epoll_ctl(epoll_fd, EPOLL_CTL_DEL, fd, NULL);
                        close(fd);
                        if (pending_writes[fd]) {
                            free(pending_writes[fd]->buf);
                            free(pending_writes[fd]);
                            pending_writes[fd] = NULL;
                        }
                    } else {
#ifdef STATS
                        g_events++; // Task 5: count request-producing ready event
#endif
                        ssize_t n = write(fd, buf, bytes_read);
                        if (n < 0) {
                            if (errno == EAGAIN || errno == EWOULDBLOCK) {
                                n = 0;
                            } else {
                                epoll_ctl(epoll_fd, EPOLL_CTL_DEL, fd, NULL);
                                close(fd);
                                if (pending_writes[fd]) {
                                    free(pending_writes[fd]->buf);
                                    free(pending_writes[fd]);
                                    pending_writes[fd] = NULL;
                                }
                                continue;
                            }
                        }

                        if (n < bytes_read) {
                            // Allocate on demand only when a partial write actually occurs
                            struct pending_write *pw = malloc(sizeof(struct pending_write));
                            if (pw) {
                                pw->len = bytes_read - n;
                                pw->offset = 0;
                                pw->buf = malloc(pw->len);
                                if (pw->buf) {
                                    memcpy(pw->buf, buf + n, pw->len);
                                    pending_writes[fd] = pw;
                                    ev.events = EPOLLIN | EPOLLOUT;
                                    ev.data.fd = fd;
                                    epoll_ctl(epoll_fd, EPOLL_CTL_MOD, fd, &ev);
                                } else {
                                    free(pw);
                                }
                            }
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
    printf("\n[STATS] server=epoll_lt_lean_server waits=%llu events=%llu requests=%llu avg_events_per_wait=%.4f waits_per_request=%.6f req_per_s=%.2f\n",
           g_waits, g_events, g_requests, avg_events, waits_per_req, req_per_s);
    // Task 5: Consistency self-check between waits_per_request and 1/avg_events_per_wait
    double inv_avg = avg_events > 0.0 ? (1.0 / avg_events) : 0.0;
    double diff = fabs(waits_per_req - inv_avg);
    if (inv_avg > 0.0 && (diff / inv_avg) > 0.10) {
        fprintf(stderr, "[STATS WARNING] server=epoll_lt_lean_server: waits_per_request (%.4f) and 1/avg_events (%.4f) disagree by >10%%!\n",
                waits_per_req, inv_avg);
    }
    fflush(stdout);
#endif

    close(epoll_fd);
    close(listen_fd);
    return 0;
}
