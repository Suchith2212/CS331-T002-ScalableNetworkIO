#include "../include/common.h"
#include <sys/epoll.h>

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

    struct epoll_event ev, events[MAX_EVENTS];
    ev.events = EPOLLIN | EPOLLET;
    ev.data.fd = listen_fd;

    if (epoll_ctl(epoll_fd, EPOLL_CTL_ADD, listen_fd, &ev) < 0) {
        perror("epoll_ctl listen_fd");
        exit(EXIT_FAILURE);
    }

    printf("[epoll] Server running on port %d (Edge-Triggered O(1) epoll)\n", port);

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

            if (fd == listen_fd) {
                // Edge-triggered accept loop: accept ALL pending connections until EAGAIN
                while (1) {
                    struct sockaddr_in client_addr;
                    socklen_t client_len = sizeof(client_addr);
                    int client_fd = accept(listen_fd, (struct sockaddr *)&client_addr, &client_len);
                    if (client_fd < 0) {
                        if (errno == EAGAIN || errno == EWOULDBLOCK) {
                            break; // All pending connections accepted
                        }
                        perror("accept");
                        break;
                    }

                    set_nonblocking(client_fd);

                    ev.events = EPOLLIN | EPOLLET;
                    ev.data.fd = client_fd;
                    if (epoll_ctl(epoll_fd, EPOLL_CTL_ADD, client_fd, &ev) < 0) {
                        perror("epoll_ctl add client");
                        close(client_fd);
                    }
                }
            } else {
                // Edge-triggered read loop: read until EAGAIN or connection end
                int disconnect = 0;
                while (1) {
                    ssize_t bytes_read = read(fd, buf, sizeof(buf));
                    if (bytes_read < 0) {
                        if (errno == EAGAIN || errno == EWOULDBLOCK) {
                            // Drained read buffer for edge-triggered socket
                            break;
                        }
                        // Real socket read error
                        disconnect = 1;
                        break;
                    } else if (bytes_read == 0) {
                        // EOF / client disconnected
                        disconnect = 1;
                        break;
                    }

                    // Echo back data
                    ssize_t total_written = 0;
                    while (total_written < bytes_read) {
                        ssize_t n = write(fd, buf + total_written, bytes_read - total_written);
                        if (n < 0) {
                            if (errno == EAGAIN || errno == EWOULDBLOCK) {
                                usleep(100);
                                continue;
                            }
                            disconnect = 1;
                            break;
                        }
                        total_written += n;
                    }
                    if (total_written < bytes_read) {
                        disconnect = 1;
                        break;
                    }
                }

                if (disconnect) {
                    epoll_ctl(epoll_fd, EPOLL_CTL_DEL, fd, NULL);
                    close(fd);
                }
            }
        }
    }

    close(epoll_fd);
    close(listen_fd);
    return 0;
}
