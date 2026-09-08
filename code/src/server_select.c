#include "../include/common.h"

int main(int argc, char *argv[]) {
    int port = PORT;
    if (argc > 1) {
        port = atoi(argv[1]);
    }

    signal(SIGPIPE, SIG_IGN);

    int listen_fd = make_listener(port);
    set_nonblocking(listen_fd);

    fd_set master_set, readfds;
    FD_ZERO(&master_set);
    FD_SET(listen_fd, &master_set);
    int max_fd = listen_fd;

    printf("[select] Server running on port %d (FD_SETSIZE limit = %d)\n", port, FD_SETSIZE);

    char buf[BUF_SIZE];

    while (1) {
        readfds = master_set; // Copy master set as select() mutates it

        int activity = select(max_fd + 1, &readfds, NULL, NULL, NULL);
        if (activity < 0) {
            if (errno == EINTR) continue;
            perror("select");
            break;
        }

        for (int i = 0; i <= max_fd; ++i) {
            if (!FD_ISSET(i, &readfds)) continue;

            if (i == listen_fd) {
                // New incoming connection(s)
                while (1) {
                    struct sockaddr_in client_addr;
                    socklen_t client_len = sizeof(client_addr);
                    int client_fd = accept(listen_fd, (struct sockaddr *)&client_addr, &client_len);
                    if (client_fd < 0) {
                        if (errno == EAGAIN || errno == EWOULDBLOCK) {
                            break; // No more pending connections
                        }
                        perror("accept");
                        break;
                    }

                    if (client_fd >= FD_SETSIZE) {
                        fprintf(stderr, "[select] Client fd %d exceeds FD_SETSIZE limit (%d)! Rejecting connection.\n", client_fd, FD_SETSIZE);
                        close(client_fd);
                        continue;
                    }

                    set_nonblocking(client_fd);
                    FD_SET(client_fd, &master_set);
                    if (client_fd > max_fd) {
                        max_fd = client_fd;
                    }
                }
            } else {
                // Client socket ready for reading
                ssize_t bytes_read = read(i, buf, sizeof(buf));
                if (bytes_read <= 0) {
                    if (bytes_read < 0 && (errno == EAGAIN || errno == EWOULDBLOCK)) {
                        continue;
                    }
                    // Connection closed or error
                    close(i);
                    FD_CLR(i, &master_set);
                    // Recalculate max_fd if necessary
                    if (i == max_fd) {
                        while (max_fd > 0 && !FD_ISSET(max_fd, &master_set)) {
                            max_fd--;
                        }
                    }
                } else {
                    // Echo back full buffer
                    ssize_t total_written = 0;
                    while (total_written < bytes_read) {
                        ssize_t n = write(i, buf + total_written, bytes_read - total_written);
                        if (n < 0) {
                            if (errno == EAGAIN || errno == EWOULDBLOCK) {
                                usleep(100); // Wait briefly if output buffer full
                                continue;
                            }
                            break;
                        }
                        total_written += n;
                    }
                    if (total_written < bytes_read) {
                        close(i);
                        FD_CLR(i, &master_set);
                        if (i == max_fd) {
                            while (max_fd > 0 && !FD_ISSET(max_fd, &master_set)) {
                                max_fd--;
                            }
                        }
                    }
                }
            }
        }
    }

    close(listen_fd);
    return 0;
}
