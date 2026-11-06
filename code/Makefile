CC = gcc
CFLAGS = -O3 -Wall -Wextra -Iinclude
LDFLAGS = -pthread -luring

BIN_DIR = bin
SRC_DIR = src

TARGETS = $(BIN_DIR)/server_blocking \
          $(BIN_DIR)/server_select \
          $(BIN_DIR)/server_poll \
          $(BIN_DIR)/server_epoll \
          $(BIN_DIR)/epoll_lt_server \
          $(BIN_DIR)/epoll_et_server \
          $(BIN_DIR)/epoll_lt_lean_server \
          $(BIN_DIR)/server_uring \
          $(BIN_DIR)/io_uring_opt_server \
          $(BIN_DIR)/reference_server \
          $(BIN_DIR)/loadgen

STATS_TARGETS = $(BIN_DIR)/server_poll_stats \
                $(BIN_DIR)/epoll_lt_server_stats \
                $(BIN_DIR)/epoll_et_server_stats \
                $(BIN_DIR)/epoll_lt_lean_server_stats \
                $(BIN_DIR)/io_uring_opt_server_stats

all: $(BIN_DIR) $(TARGETS)

stats: $(BIN_DIR) $(STATS_TARGETS)

$(BIN_DIR):
	mkdir -p $(BIN_DIR)

# Standard optimized binaries
$(BIN_DIR)/server_blocking: $(SRC_DIR)/server_blocking.c include/common.h
	$(CC) $(CFLAGS) $< -o $@ -pthread

$(BIN_DIR)/server_select: $(SRC_DIR)/server_select.c include/common.h
	$(CC) $(CFLAGS) $< -o $@

$(BIN_DIR)/server_poll: $(SRC_DIR)/server_poll.c include/common.h
	$(CC) $(CFLAGS) $< -o $@

$(BIN_DIR)/server_epoll: $(SRC_DIR)/server_epoll.c include/common.h
	$(CC) $(CFLAGS) $< -o $@

$(BIN_DIR)/epoll_lt_server: $(SRC_DIR)/epoll_lt_server.c include/common.h
	$(CC) $(CFLAGS) $< -o $@

$(BIN_DIR)/epoll_et_server: $(SRC_DIR)/epoll_et_server.c include/common.h
	$(CC) $(CFLAGS) $< -o $@

$(BIN_DIR)/epoll_lt_lean_server: $(SRC_DIR)/epoll_lt_lean_server.c include/common.h
	$(CC) $(CFLAGS) $< -o $@

$(BIN_DIR)/server_uring: $(SRC_DIR)/server_uring.c include/common.h
	$(CC) $(CFLAGS) $< -o $@ -luring

$(BIN_DIR)/io_uring_opt_server: $(SRC_DIR)/io_uring_opt_server.c include/common.h
	$(CC) $(CFLAGS) $< -o $@ -luring

$(BIN_DIR)/reference_server: $(SRC_DIR)/reference_server.c include/common.h
	$(CC) $(CFLAGS) $< -o $@

$(BIN_DIR)/loadgen: loadgen/loadgen.c
	$(CC) $(CFLAGS) $< -o $@ -pthread

# Experiment 1: Instrumented stats binaries (-DSTATS)
$(BIN_DIR)/server_poll_stats: $(SRC_DIR)/server_poll.c include/common.h
	$(CC) $(CFLAGS) -DSTATS $< -o $@

$(BIN_DIR)/epoll_lt_server_stats: $(SRC_DIR)/epoll_lt_server.c include/common.h
	$(CC) $(CFLAGS) -DSTATS $< -o $@

$(BIN_DIR)/epoll_et_server_stats: $(SRC_DIR)/epoll_et_server.c include/common.h
	$(CC) $(CFLAGS) -DSTATS $< -o $@

$(BIN_DIR)/epoll_lt_lean_server_stats: $(SRC_DIR)/epoll_lt_lean_server.c include/common.h
	$(CC) $(CFLAGS) -DSTATS $< -o $@

$(BIN_DIR)/io_uring_opt_server_stats: $(SRC_DIR)/io_uring_opt_server.c include/common.h
	$(CC) $(CFLAGS) -DSTATS $< -o $@ -luring

clean:
	rm -rf $(BIN_DIR)

.PHONY: all stats clean
