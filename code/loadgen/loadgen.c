#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <fcntl.h>
#include <pthread.h>
#include <sched.h>
#include <getopt.h>
#include <time.h>
#include <sys/socket.h>
#include <sys/epoll.h>
#include <sys/resource.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <arpa/inet.h>
#include <signal.h>

#define PAYLOAD "PING_ECHO_PAYLOAD_1234567890\n"
#define PAYLOAD_LEN 29
#define HISTOGRAM_BUCKETS 1000000 // 0 to 999,999 us (up to 1s)
#define MAX_EVENTS_PER_WAIT 1024

struct conn_state {
    int fd;
    int is_active;
    int state; // 0 = idle, 1 = sending, 2 = receiving
    size_t send_offset;
    size_t recv_offset;
    struct timespec req_start;
    char recv_buf[64];
};

struct worker_arg {
    int thread_id;
    int core_id;
    const char *host;
    int port;
    int num_conns;
    int num_active;
    double warmup_s;
    double duration_s;

    // Output stats from steady state window
    unsigned long long completed_requests;
    unsigned long long errors;
    double thread_cpu_pct;
    uint32_t *histogram; // dynamically allocated before benchmark, size HISTOGRAM_BUCKETS
    unsigned long long overflow_latencies;
    double actual_duration_s;
};

static volatile sig_atomic_t g_stop = 0;

static void sig_handler(int sig) {
    (void)sig;
    g_stop = 1;
}

static inline void set_nonblocking(int fd) {
    int flags = fcntl(fd, F_GETFL, 0);
    if (flags >= 0) {
        fcntl(fd, F_SETFL, flags | O_NONBLOCK);
    }
}

static inline void set_tcp_nodelay(int fd) {
    int opt = 1;
    setsockopt(fd, IPPROTO_TCP, TCP_NODELAY, &opt, sizeof(opt));
}

static inline double get_timespec_diff_us(struct timespec *start, struct timespec *end) {
    return (double)(end->tv_sec - start->tv_sec) * 1e6 + (double)(end->tv_nsec - start->tv_nsec) / 1e3;
}

static inline double get_timespec_diff_s(struct timespec *start, struct timespec *end) {
    return (double)(end->tv_sec - start->tv_sec) + (double)(end->tv_nsec - start->tv_nsec) / 1e9;
}

static void *worker_thread(void *arg) {
    struct worker_arg *w = (struct worker_arg *)arg;

    // 1. Pin thread to core
    if (w->core_id >= 0) {
        cpu_set_t cpuset;
        CPU_ZERO(&cpuset);
        CPU_SET(w->core_id, &cpuset);
        if (pthread_setaffinity_np(pthread_self(), sizeof(cpu_set_t), &cpuset) != 0) {
            perror("pthread_setaffinity_np");
        }
    }

    // Allocate connection states
    struct conn_state *conns = calloc(w->num_conns, sizeof(struct conn_state));
    if (!conns) {
        perror("calloc conns");
        return NULL;
    }

    // Allocate histogram (1M buckets of 1 us = 4MB)
    w->histogram = calloc(HISTOGRAM_BUCKETS, sizeof(uint32_t));
    if (!w->histogram) {
        perror("calloc histogram");
        free(conns);
        return NULL;
    }

    int epoll_fd = epoll_create1(0);
    if (epoll_fd < 0) {
        perror("epoll_create1");
        free(conns);
        free(w->histogram);
        return NULL;
    }

    struct sockaddr_in saddr;
    memset(&saddr, 0, sizeof(saddr));
    saddr.sin_family = AF_INET;
    saddr.sin_port = htons(w->port);
    inet_pton(AF_INET, w->host, &saddr.sin_addr);

    // 2. Connect all assigned sockets
    for (int i = 0; i < w->num_conns; ++i) {
        int fd = socket(AF_INET, SOCK_STREAM, 0);
        if (fd < 0) {
            perror("socket");
            w->errors++;
            continue;
        }

        set_nonblocking(fd);
        set_tcp_nodelay(fd);

        conns[i].fd = fd;
        conns[i].is_active = (i < w->num_active) ? 1 : 0;
        conns[i].state = 1; // ready to send if active
        conns[i].send_offset = 0;
        conns[i].recv_offset = 0;

        int rc = connect(fd, (struct sockaddr *)&saddr, sizeof(saddr));
        if (rc < 0 && errno != EINPROGRESS) {
            perror("connect");
            w->errors++;
            close(fd);
            conns[i].fd = -1;
            continue;
        }

        struct epoll_event ev;
        ev.data.u32 = i;
        // If active, watch for EPOLLOUT to begin sending immediately once connected
        ev.events = conns[i].is_active ? EPOLLOUT : 0;
        if (epoll_ctl(epoll_fd, EPOLL_CTL_ADD, fd, &ev) < 0) {
            perror("epoll_ctl add");
            w->errors++;
            close(fd);
            conns[i].fd = -1;
        }
    }

    // Wait until connections establish
    usleep(50000); // 50ms connect settle

    struct epoll_event events[MAX_EVENTS_PER_WAIT];
    struct timespec loop_start, now;
    clock_gettime(CLOCK_MONOTONIC, &loop_start);

    struct timespec steady_start, steady_end;
    struct rusage ru_start, ru_end;
    int in_steady_state = 0;
    int warm_up_done = 0;

    double total_run_s = w->warmup_s + w->duration_s;

    while (!g_stop) {
        clock_gettime(CLOCK_MONOTONIC, &now);
        double elapsed_s = get_timespec_diff_s(&loop_start, &now);

        if (!warm_up_done && elapsed_s >= w->warmup_s) {
            warm_up_done = 1;
            in_steady_state = 1;
            clock_gettime(CLOCK_MONOTONIC, &steady_start);
            getrusage(RUSAGE_THREAD, &ru_start);
        }

        if (elapsed_s >= total_run_s) {
            break;
        }

        int nfds = epoll_wait(epoll_fd, events, MAX_EVENTS_PER_WAIT, 100);
        if (nfds < 0) {
            if (errno == EINTR) continue;
            perror("epoll_wait");
            break;
        }

        for (int i = 0; i < nfds; ++i) {
            uint32_t c_idx = events[i].data.u32;
            struct conn_state *c = &conns[c_idx];
            uint32_t revents = events[i].events;

            if (revents & (EPOLLERR | EPOLLHUP)) {
                w->errors++;
                close(c->fd);
                c->fd = -1;
                continue;
            }

            // 1. Send path
            if (revents & EPOLLOUT) {
                if (c->is_active && c->state == 1) {
                    if (c->send_offset == 0) {
                        clock_gettime(CLOCK_MONOTONIC, &c->req_start);
                    }
                    while (c->send_offset < PAYLOAD_LEN) {
                        ssize_t n = write(c->fd, PAYLOAD + c->send_offset, PAYLOAD_LEN - c->send_offset);
                        if (n < 0) {
                            if (errno == EAGAIN || errno == EWOULDBLOCK) {
                                break; // Kernel socket send buffer full, wait for next EPOLLOUT
                            }
                            w->errors++;
                            close(c->fd);
                            c->fd = -1;
                            break;
                        }
                        c->send_offset += n;
                    }

                    if (c->fd >= 0 && c->send_offset == PAYLOAD_LEN) {
                        // Fully transmitted request, switch to reading response
                        c->state = 2; // receiving
                        c->send_offset = 0;
                        c->recv_offset = 0;
                        struct epoll_event ev;
                        ev.data.u32 = c_idx;
                        ev.events = EPOLLIN;
                        epoll_ctl(epoll_fd, EPOLL_CTL_MOD, c->fd, &ev);
                    }
                }
            }

            // 2. Recv path
            if (revents & EPOLLIN) {
                if (c->is_active && c->state == 2) {
                    while (c->recv_offset < PAYLOAD_LEN) {
                        ssize_t n = read(c->fd, c->recv_buf + c->recv_offset, PAYLOAD_LEN - c->recv_offset);
                        if (n <= 0) {
                            if (n < 0 && (errno == EAGAIN || errno == EWOULDBLOCK)) {
                                break;
                            }
                            // Connection closed or fatal error
                            w->errors++;
                            close(c->fd);
                            c->fd = -1;
                            break;
                        }
                        c->recv_offset += n;
                    }

                    if (c->fd >= 0 && c->recv_offset == PAYLOAD_LEN) {
                        // Complete echo response received!
                        struct timespec req_end;
                        clock_gettime(CLOCK_MONOTONIC, &req_end);

                        // Verify payload integrity
                        if (memcmp(c->recv_buf, PAYLOAD, PAYLOAD_LEN) != 0) {
                            w->errors++;
                        } else if (in_steady_state) {
                            w->completed_requests++;
                            double lat_us = get_timespec_diff_us(&c->req_start, &req_end);
                            if (lat_us >= 0.0) {
                                unsigned long lat_idx = (unsigned long)lat_us;
                                if (lat_idx < HISTOGRAM_BUCKETS) {
                                    w->histogram[lat_idx]++;
                                } else {
                                    w->overflow_latencies++;
                                }
                            }
                        }

                        // Closed-loop: immediately send next request
                        c->state = 1; // sending
                        c->send_offset = 0;
                        c->recv_offset = 0;

                        // Try immediate write to avoid an extra epoll roundtrip
                        clock_gettime(CLOCK_MONOTONIC, &c->req_start);
                        ssize_t n = write(c->fd, PAYLOAD, PAYLOAD_LEN);
                        if (n == PAYLOAD_LEN) {
                            c->state = 2; // receiving
                            // epoll already configured for EPOLLIN
                        } else if (n > 0) {
                            c->send_offset = n;
                            struct epoll_event ev;
                            ev.data.u32 = c_idx;
                            ev.events = EPOLLOUT;
                            epoll_ctl(epoll_fd, EPOLL_CTL_MOD, c->fd, &ev);
                        } else if (n < 0 && (errno == EAGAIN || errno == EWOULDBLOCK)) {
                            c->send_offset = 0;
                            struct epoll_event ev;
                            ev.data.u32 = c_idx;
                            ev.events = EPOLLOUT;
                            epoll_ctl(epoll_fd, EPOLL_CTL_MOD, c->fd, &ev);
                        } else {
                            w->errors++;
                            close(c->fd);
                            c->fd = -1;
                        }
                    }
                }
            }
        }
    }

    if (in_steady_state) {
        clock_gettime(CLOCK_MONOTONIC, &steady_end);
        getrusage(RUSAGE_THREAD, &ru_end);
        w->actual_duration_s = get_timespec_diff_s(&steady_start, &steady_end);

        double u_sec = (double)(ru_end.ru_utime.tv_sec - ru_start.ru_utime.tv_sec) +
                       (double)(ru_end.ru_utime.tv_usec - ru_start.ru_utime.tv_usec) / 1e6;
        double s_sec = (double)(ru_end.ru_stime.tv_sec - ru_start.ru_stime.tv_sec) +
                       (double)(ru_end.ru_stime.tv_usec - ru_start.ru_stime.tv_usec) / 1e6;
        double cpu_total_s = u_sec + s_sec;

        if (w->actual_duration_s > 0) {
            w->thread_cpu_pct = (cpu_total_s / w->actual_duration_s) * 100.0;
        }
    }

    // Clean up
    for (int i = 0; i < w->num_conns; ++i) {
        if (conns[i].fd >= 0) {
            close(conns[i].fd);
        }
    }
    close(epoll_fd);
    free(conns);

    return NULL;
}

static void parse_core_list(const char *str, int *cores, int max_cores, int *num_cores) {
    *num_cores = 0;
    if (!str || strlen(str) == 0) return;

    char *buf = strdup(str);
    char *token = strtok(buf, ",");
    while (token && *num_cores < max_cores) {
        char *dash = strchr(token, '-');
        if (dash) {
            *dash = '\0';
            int start = atoi(token);
            int end = atoi(dash + 1);
            for (int c = start; c <= end && *num_cores < max_cores; ++c) {
                cores[(*num_cores)++] = c;
            }
        } else {
            cores[(*num_cores)++] = atoi(token);
        }
        token = strtok(NULL, ",");
    }
    free(buf);
}

int main(int argc, char *argv[]) {
    const char *host = "127.0.0.1";
    int port = 8080;
    int total_conns = 100;
    int active_conns = 100;
    int num_threads = 1;
    double duration_s = 10.0;
    double warmup_s = 1.0;
    const char *cores_str = NULL;

    static struct option long_options[] = {
        {"host",     required_argument, 0, 'h'},
        {"port",     required_argument, 0, 'p'},
        {"conns",    required_argument, 0, 'c'},
        {"active",   required_argument, 0, 'a'},
        {"threads",  required_argument, 0, 't'},
        {"duration", required_argument, 0, 'd'},
        {"warmup",   required_argument, 0, 'w'},
        {"cores",    required_argument, 0, 'C'},
        {0, 0, 0, 0}
    };

    int opt;
    while ((opt = getopt_long(argc, argv, "", long_options, NULL)) != -1) {
        switch (opt) {
            case 'h': host = optarg; break;
            case 'p': port = atoi(optarg); break;
            case 'c': total_conns = atoi(optarg); break;
            case 'a': active_conns = atoi(optarg); break;
            case 't': num_threads = atoi(optarg); break;
            case 'd': duration_s = atof(optarg); break;
            case 'w': warmup_s = atof(optarg); break;
            case 'C': cores_str = optarg; break;
            default:
                fprintf(stderr, "Usage: %s --host H --port P --conns N --active M --threads T --duration S --warmup W [--cores LIST]\n", argv[0]);
                exit(EXIT_FAILURE);
        }
    }

    if (active_conns > total_conns) {
        active_conns = total_conns;
    }
    if (num_threads < 1) num_threads = 1;

    signal(SIGINT, sig_handler);
    signal(SIGTERM, sig_handler);
    signal(SIGPIPE, SIG_IGN);

    int assigned_cores[128];
    int num_assigned_cores = 0;
    if (cores_str) {
        parse_core_list(cores_str, assigned_cores, 128, &num_assigned_cores);
    }

    pthread_t *threads = calloc(num_threads, sizeof(pthread_t));
    struct worker_arg *args = calloc(num_threads, sizeof(struct worker_arg));

    int base_conns = total_conns / num_threads;
    int rem_conns = total_conns % num_threads;
    int base_active = active_conns / num_threads;
    int rem_active = active_conns % num_threads;

    for (int i = 0; i < num_threads; ++i) {
        args[i].thread_id = i;
        args[i].core_id = (num_assigned_cores > 0) ? assigned_cores[i % num_assigned_cores] : -1;
        args[i].host = host;
        args[i].port = port;
        args[i].num_conns = base_conns + (i < rem_conns ? 1 : 0);
        args[i].num_active = base_active + (i < rem_active ? 1 : 0);
        args[i].warmup_s = warmup_s;
        args[i].duration_s = duration_s;

        if (pthread_create(&threads[i], NULL, worker_thread, &args[i]) != 0) {
            perror("pthread_create");
            exit(EXIT_FAILURE);
        }
    }

    for (int i = 0; i < num_threads; ++i) {
        pthread_join(threads[i], NULL);
    }

    // Merge statistics
    unsigned long long total_completed = 0;
    unsigned long long total_errors = 0;
    double max_thread_cpu = 0.0;
    double avg_duration = 0.0;

    uint64_t *merged_hist = calloc(HISTOGRAM_BUCKETS, sizeof(uint64_t));
    unsigned long long total_overflow = 0;

    for (int i = 0; i < num_threads; ++i) {
        total_completed += args[i].completed_requests;
        total_errors += args[i].errors;
        if (args[i].thread_cpu_pct > max_thread_cpu) {
            max_thread_cpu = args[i].thread_cpu_pct;
        }
        avg_duration += args[i].actual_duration_s;

        if (args[i].histogram) {
            for (int b = 0; b < HISTOGRAM_BUCKETS; ++b) {
                merged_hist[b] += args[i].histogram[b];
            }
            free(args[i].histogram);
        }
        total_overflow += args[i].overflow_latencies;
    }
    avg_duration /= num_threads;

    double req_s = (avg_duration > 0) ? ((double)total_completed / avg_duration) : 0.0;

    // Compute percentiles (p50, p99, p99.9)
    double p50_us = 0.0, p99_us = 0.0, p999_us = 0.0;
    if (total_completed > 0) {
        unsigned long long count_p50 = (total_completed * 50) / 100;
        unsigned long long count_p99 = (total_completed * 99) / 100;
        unsigned long long count_p999 = (total_completed * 999) / 1000;

        unsigned long long running = 0;
        int found50 = 0, found99 = 0, found999 = 0;

        for (int b = 0; b < HISTOGRAM_BUCKETS; ++b) {
            running += merged_hist[b];
            if (!found50 && running >= count_p50) {
                p50_us = (double)b;
                found50 = 1;
            }
            if (!found99 && running >= count_p99) {
                p99_us = (double)b;
                found99 = 1;
            }
            if (!found999 && running >= count_p999) {
                p999_us = (double)b;
                found999 = 1;
                break;
            }
        }
        if (!found999 && total_overflow > 0) {
            p999_us = 1000000.0; // In overflow bucket (>1s)
        }
    }

    // Machine-readable single line output as required:
    // req_s=... p50_us=... p99_us=... p999_us=... errors=... max_thread_cpu_pct=...
    printf("req_s=%.2f p50_us=%.2f p99_us=%.2f p999_us=%.2f errors=%llu max_thread_cpu_pct=%.2f\n",
           req_s, p50_us, p99_us, p999_us, total_errors, max_thread_cpu);

    if (max_thread_cpu > 85.0) {
        fprintf(stderr, "WARNING: Load generator max worker thread CPU utilization exceeded 85%% (%.2f%%)!\n", max_thread_cpu);
    }

    free(merged_hist);
    free(threads);
    free(args);

    return 0;
}
