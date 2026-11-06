#include "../include/common.h"

#ifdef STATS
#include <time.h>
#include <math.h>
// Compile-time optional instrumentation for wait call & event frequency (Exp 1 & Task 5)
// Tracks waits, request-producing events, and completed echoes with 10% consistency self-check.
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

#define INITIAL_POLL_CAP 1024

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

    size_t poll_cap = INITIAL_POLL_CAP;
    struct pollfd *fds = malloc(poll_cap * sizeof(struct pollfd));
    if (!fds) {
        perror("malloc");
        exit(EXIT_FAILURE);
    }

    fds[0].fd = listen_fd;
    fds[0].events = POLLIN;
    fds[0].revents = 0;
    nfds_t nfds = 1;

    printf("[poll] Server running on port %d (dynamic pollfd array, O(N))\n", port);

    char buf[BUF_SIZE];

#ifdef STATS
    while (!g_stop) {
        g_waits++;
#else
    while (1) {
#endif
        int activity = poll(fds, nfds, -1);
        if (activity < 0) {
            if (errno == EINTR) {
#ifdef STATS
                if (g_stop) break;
#endif
                continue;
            }
            perror("poll");
            break;
        }

        nfds_t current_nfds = nfds;
        int compress_array = 0;

        for (nfds_t i = 0; i < current_nfds; ++i) {
            if (fds[i].revents == 0) continue;

            if (fds[i].fd == listen_fd) {
                // Accept incoming connection(s)
                while (1) {
                    struct sockaddr_in client_addr;
                    socklen_t client_len = sizeof(client_addr);
                    int client_fd = accept(listen_fd, (struct sockaddr *)&client_addr, &client_len);
                    if (client_fd < 0) {
                        if (errno == EAGAIN || errno == EWOULDBLOCK) {
                            break;
                        }
                        perror("accept");
                        break;
                    }

                    set_nonblocking(client_fd);

                    if (nfds >= poll_cap) {
                        poll_cap *= 2;
                        struct pollfd *new_fds = realloc(fds, poll_cap * sizeof(struct pollfd));
                        if (!new_fds) {
                            perror("realloc");
                            close(client_fd);
                            break;
                        }
                        fds = new_fds;
                    }

                    fds[nfds].fd = client_fd;
                    fds[nfds].events = POLLIN;
                    fds[nfds].revents = 0;
                    nfds++;
                }
            } else {
                // Handle client read/write
                if (fds[i].revents & (POLLIN | POLLERR | POLLHUP)) {
                    ssize_t bytes_read = read(fds[i].fd, buf, sizeof(buf));
                    if (bytes_read <= 0) {
                        if (bytes_read < 0 && (errno == EAGAIN || errno == EWOULDBLOCK)) {
                            continue;
                        }
                        close(fds[i].fd);
                        fds[i].fd = -1;
                        compress_array = 1;
                    } else {
#ifdef STATS
                        g_events++; // Task 5: count request-producing ready data event
#endif
                        ssize_t total_written = 0;
                        while (total_written < bytes_read) {
                            ssize_t n = write(fds[i].fd, buf + total_written, bytes_read - total_written);
                            if (n < 0) {
                                if (errno == EAGAIN || errno == EWOULDBLOCK) {
                                    usleep(100);
                                    continue;
                                }
                                break;
                            }
                            total_written += n;
                        }
                        if (total_written < bytes_read) {
                            close(fds[i].fd);
                            fds[i].fd = -1;
                            compress_array = 1;
                        } else {
#ifdef STATS
                            g_requests++; // Task 5: one completed read-then-full-echo
#endif
                        }
                    }
                }
            }
        }

        // Compact fds array if any client closed
        if (compress_array) {
            for (nfds_t i = 0; i < nfds; ++i) {
                if (fds[i].fd == -1) {
                    for (nfds_t j = i; j < nfds - 1; ++j) {
                        fds[j] = fds[j + 1];
                    }
                    i--;
                    nfds--;
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
    printf("\n[STATS] server=server_poll waits=%llu events=%llu requests=%llu avg_events_per_wait=%.4f waits_per_request=%.6f req_per_s=%.2f\n",
           g_waits, g_events, g_requests, avg_events, waits_per_req, req_per_s);
    // Task 5: Consistency self-check between waits_per_request and 1/avg_events_per_wait
    double inv_avg = avg_events > 0.0 ? (1.0 / avg_events) : 0.0;
    double diff = fabs(waits_per_req - inv_avg);
    if (inv_avg > 0.0 && (diff / inv_avg) > 0.10) {
        fprintf(stderr, "[STATS WARNING] server=server_poll: waits_per_request (%.4f) and 1/avg_events (%.4f) disagree by >10%%!\n",
                waits_per_req, inv_avg);
    }
    fflush(stdout);
#endif

    free(fds);
    close(listen_fd);
    return 0;
}
