#include "../include/common.h"

#define INITIAL_POLL_CAP 1024

int main(int argc, char *argv[]) {
    int port = PORT;
    if (argc > 1) {
        port = atoi(argv[1]);
    }

    signal(SIGPIPE, SIG_IGN);

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

    while (1) {
        int activity = poll(fds, nfds, -1);
        if (activity < 0) {
            if (errno == EINTR) continue;
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

    free(fds);
    close(listen_fd);
    return 0;
}
