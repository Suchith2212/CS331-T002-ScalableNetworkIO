#define _GNU_SOURCE
#include "../include/common.h"
#include <sys/epoll.h>
#include <netinet/tcp.h>

// Trivial reference echo server for load generator calibration (Task 3)
// Architecture: Single thread, epoll Level-Triggered, shared stack buffer.

static inline void set_tcp_nodelay(int fd) {
    int opt = 1;
    setsockopt(fd, IPPROTO_TCP, TCP_NODELAY, &opt, sizeof(opt));
}

int main(int argc, char *argv[]) {
    int port = PORT;
    if (argc > 1) {
        port = atoi(argv[1]);
    }

    signal(SIGPIPE, SIG_IGN);

    int listen_fd = make_listener(port);
    set_nonblocking(listen_fd);

    int epoll_fd = epoll_create1(0);
    if (epoll_fd < 0) {
        perror("epoll_create1");
        exit(EXIT_FAILURE);
    }

    struct epoll_event ev;
    ev.events = EPOLLIN;
    ev.data.fd = listen_fd;
    if (epoll_ctl(epoll_fd, EPOLL_CTL_ADD, listen_fd, &ev) < 0) {
        perror("epoll_ctl add listener");
        exit(EXIT_FAILURE);
    }

    printf("[reference_epoll] Server running on port %d (single-threaded LT reference)\n", port);
    fflush(stdout);

    struct epoll_event events[MAX_EVENTS];
    char buf[BUF_SIZE];

    while (1) {
        int nfds = epoll_wait(epoll_fd, events, MAX_EVENTS, -1);
        if (nfds < 0) {
            if (errno == EINTR) continue;
            perror("epoll_wait");
            break;
        }

        for (int i = 0; i < nfds; ++i) {
            int fd = events[i].data.fd;
            uint32_t revents = events[i].events;

            if (revents & (EPOLLERR | EPOLLHUP)) {
                close(fd);
                continue;
            }

            if (fd == listen_fd) {
                while (1) {
                    struct sockaddr_in client_addr;
                    socklen_t client_len = sizeof(client_addr);
                    int client_fd = accept(listen_fd, (struct sockaddr *)&client_addr, &client_len);
                    if (client_fd < 0) {
                        if (errno == EAGAIN || errno == EWOULDBLOCK) {
                            break;
                        }
                        break;
                    }

                    set_nonblocking(client_fd);
                    set_tcp_nodelay(client_fd);

                    ev.events = EPOLLIN;
                    ev.data.fd = client_fd;
                    if (epoll_ctl(epoll_fd, EPOLL_CTL_ADD, client_fd, &ev) < 0) {
                        close(client_fd);
                    }
                }
            } else {
                if (revents & EPOLLIN) {
                    ssize_t bytes_read = read(fd, buf, sizeof(buf));
                    if (bytes_read <= 0) {
                        if (bytes_read < 0 && (errno == EAGAIN || errno == EWOULDBLOCK)) {
                            continue;
                        }
                        epoll_ctl(epoll_fd, EPOLL_CTL_DEL, fd, NULL);
                        close(fd);
                    } else {
                        // Echo immediately
                        ssize_t total_written = 0;
                        while (total_written < bytes_read) {
                            ssize_t n = write(fd, buf + total_written, bytes_read - total_written);
                            if (n <= 0) {
                                if (n < 0 && (errno == EAGAIN || errno == EWOULDBLOCK)) {
                                    continue;
                                }
                                break;
                            }
                            total_written += n;
                        }
                        if (total_written < bytes_read) {
                            epoll_ctl(epoll_fd, EPOLL_CTL_DEL, fd, NULL);
                            close(fd);
                        }
                    }
                }
            }
        }
    }

    close(epoll_fd);
    close(listen_fd);
    return 0;
}
