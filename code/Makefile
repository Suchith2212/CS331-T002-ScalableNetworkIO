CC = gcc
CFLAGS = -O3 -Wall -Wextra -Iinclude
LDFLAGS = -pthread -luring

BIN_DIR = bin
SRC_DIR = src

TARGETS = $(BIN_DIR)/server_blocking \
          $(BIN_DIR)/server_select \
          $(BIN_DIR)/server_poll \
          $(BIN_DIR)/server_epoll \
          $(BIN_DIR)/server_uring

all: $(BIN_DIR) $(TARGETS)

$(BIN_DIR):
	mkdir -p $(BIN_DIR)

$(BIN_DIR)/server_blocking: $(SRC_DIR)/server_blocking.c include/common.h
	$(CC) $(CFLAGS) $< -o $@ -pthread

$(BIN_DIR)/server_select: $(SRC_DIR)/server_select.c include/common.h
	$(CC) $(CFLAGS) $< -o $@

$(BIN_DIR)/server_poll: $(SRC_DIR)/server_poll.c include/common.h
	$(CC) $(CFLAGS) $< -o $@

$(BIN_DIR)/server_epoll: $(SRC_DIR)/server_epoll.c include/common.h
	$(CC) $(CFLAGS) $< -o $@

$(BIN_DIR)/server_uring: $(SRC_DIR)/server_uring.c include/common.h
	$(CC) $(CFLAGS) $< -o $@ -luring

clean:
	rm -rf $(BIN_DIR) results/*.json results/*.csv results/*.png

.PHONY: all clean
