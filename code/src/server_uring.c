#include "../include/common.h"
#include <liburing.h>

#define ENTRIES       4096
#define EVENT_ACCEPT  0
#define EVENT_READ    1
#define EVENT_WRITE   2

struct conn_info {
    int fd;
    int type;
    char buf[BUF_SIZE];
    size_t len;
};

static struct conn_info accept_conn;

static void add_accept(struct io_uring *ring, int listen_fd) {
    struct io_uring_sqe *sqe = io_uring_get_sqe(ring);
    if (!sqe) return;

    accept_conn.fd = listen_fd;
    accept_conn.type = EVENT_ACCEPT;

    io_uring_prep_accept(sqe, listen_fd, NULL, NULL, 0);
    io_uring_sqe_set_data(sqe, &accept_conn);
}

static void add_read(struct io_uring *ring, struct conn_info *conn) {
    struct io_uring_sqe *sqe = io_uring_get_sqe(ring);
    if (!sqe) return;

    conn->type = EVENT_READ;
    io_uring_prep_read(sqe, conn->fd, conn->buf, BUF_SIZE, 0);
    io_uring_sqe_set_data(sqe, conn);
}

static void add_write(struct io_uring *ring, struct conn_info *conn, size_t len) {
    struct io_uring_sqe *sqe = io_uring_get_sqe(ring);
    if (!sqe) return;

    conn->type = EVENT_WRITE;
    conn->len = len;
    io_uring_prep_write(sqe, conn->fd, conn->buf, len, 0);
    io_uring_sqe_set_data(sqe, conn);
}

int main(int argc, char *argv[]) {
    int port = PORT;
    if (argc > 1) {
        port = atoi(argv[1]);
    }

    signal(SIGPIPE, SIG_IGN);

    int listen_fd = make_listener(port);
    set_nonblocking(listen_fd);

    struct io_uring ring;
    if (io_uring_queue_init(ENTRIES, &ring, 0) < 0) {
        perror("io_uring_queue_init");
        exit(EXIT_FAILURE);
    }

    printf("[io_uring] Server running on port %d (Submission/Completion Ring Buffer)\n", port);

    add_accept(&ring, listen_fd);
    io_uring_submit(&ring);

    while (1) {
        struct io_uring_cqe *cqe;
        int ret = io_uring_wait_cqe(&ring, &cqe);
        if (ret < 0) {
            if (ret == -EINTR) continue;
            fprintf(stderr, "io_uring_wait_cqe error: %s\n", strerror(-ret));
            break;
        }

        struct io_uring_cqe *cqes[MAX_EVENTS];
        unsigned count = io_uring_peek_batch_cqe(&ring, cqes, MAX_EVENTS);
        if (count == 0 && cqe != NULL) {
            cqes[0] = cqe;
            count = 1;
        }

        for (unsigned i = 0; i < count; ++i) {
            struct io_uring_cqe *c = cqes[i];
            struct conn_info *conn = (struct conn_info *)io_uring_cqe_get_data(c);
            int res = c->res;

            if (!conn) {
                io_uring_cqe_seen(&ring, c);
                continue;
            }

            if (conn->type == EVENT_ACCEPT) {
                if (res >= 0) {
                    int client_fd = res;
                    set_nonblocking(client_fd);

                    struct conn_info *client_conn = malloc(sizeof(struct conn_info));
                    if (client_conn) {
                        client_conn->fd = client_fd;
                        add_read(&ring, client_conn);
                    } else {
                        close(client_fd);
                    }
                }
                // Re-arm accept request for next incoming client
                add_accept(&ring, listen_fd);
            } else if (conn->type == EVENT_READ) {
                if (res <= 0) {
                    // Closed or error
                    close(conn->fd);
                    free(conn);
                } else {
                    // Data read, post write event
                    add_write(&ring, conn, res);
                }
            } else if (conn->type == EVENT_WRITE) {
                if (res <= 0) {
                    close(conn->fd);
                    free(conn);
                } else {
                    // Data written, post next read request
                    add_read(&ring, conn);
                }
            }

            io_uring_cqe_seen(&ring, c);
        }

        io_uring_submit(&ring);
    }

    io_uring_queue_exit(&ring);
    close(listen_fd);
    return 0;
}
