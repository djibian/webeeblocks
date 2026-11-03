WEBOTS_HOME ?= /usr/local/webots
CC ?= gcc
CFLAGS = -O2 -std=c11 -fPIC -Wall -Wextra -I$(WEBOTS_HOME)/include
all: reset_wrench.so
reset_wrench.so: reset_wrench.c
	$(CC) $(CFLAGS) -shared -o $@ $< -lm
clean:
	rm -f reset_wrench.so
