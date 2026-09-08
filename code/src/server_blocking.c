#include "../include/common.h"
#include <pthread.h>

void *client_handler(void *arg) {
    int client_fd = *(int *)arg;
    free(arg);

    char buf[BUF_SIZE];
    while (1) {
        ssize_t bytes_read = read(client_fd, buf, sizeof(buf));
        if (bytes_read <= 0) {
            // Error or client disconnected
            break;
        }
        
        ssize_t total_written = 0;
        while (total_written < bytes_read) {
            ssize_t bytes_written = write(client_fd, buf + total_written, bytes_read - total_written);
            if (bytes_written <= 0) {
                break;
            }
            total_written += bytes_written;
        }
        if (total_written < bytes_read) {
            break;
        }
    }

    close(client_fd);
    return NULL;
}

int main(int argc, char *argv[]) {
    int port = PORT;
    if (argc > 1) {
        port = atoi(argv[1]);
    }

    signal(SIGPIPE, SIG_IGN);

    int listen_fd = make_listener(port);
    printf("[blocking] Server running on port %d (one-thread-per-client baseline)\n", port);

    while (1) {
        struct sockaddr_in client_addr;
        socklen_t client_len = sizeof(client_addr);
        int client_fd = accept(listen_fd, (struct sockaddr *)&client_addr, &client_len);
        if (client_fd < 0) {
            if (errno == EINTR) continue;
            perror("accept");
            break;
        }

        pthread_t thread_id;
        int *pfd = malloc(sizeof(int));
        if (!pfd) {
            close(client_fd);
            continue;
        }
        *pfd = client_fd;

        if (pthread_create(&thread_id, NULL, client_handler, pfd) != 0) {
            perror("pthread_create");
            free(pfd);
            close(client_fd);
        } else {
            pthread_detach(thread_id);
        }
    }

    close(listen_fd);
    return 0;
}
