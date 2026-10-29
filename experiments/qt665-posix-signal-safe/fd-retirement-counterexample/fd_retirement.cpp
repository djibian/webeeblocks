// Native kernel counterexample for a sampled FD surviving global revocation.
// The signal handler/configurator are included byte-for-byte from the candidate.
// Only write() is gated to impose a legal preemption before its kernel call.
#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif
#include <cerrno>
#include <csignal>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fcntl.h>
#include <pthread.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <unistd.h>

static int watchedFd, enteredFd, releaseFd, readyFd, threadErrno;
static __thread volatile sig_atomic_t finished;
static ssize_t actualWrite;

extern "C" ssize_t write(int fd, const void *data, size_t size) {
  if (fd == watchedFd && size == 1) {
    const char marker = 'E';
    if (syscall(SYS_write, enteredFd, &marker, 1) != 1) _exit(80);
    char release;
    if (syscall(SYS_read, releaseFd, &release, 1) != 1) _exit(81);
    actualWrite = syscall(SYS_write, fd, data, size);
    finished = 1;
    return actualWrite;
  }
  return syscall(SYS_write, fd, data, size);
}

#include "handler.inc"

static void require(bool value, const char *message) {
  if (!value) { perror(message); exit(90); }
}

static void *worker(void *) {
  const char ready = 'R';
  if (syscall(SYS_write, readyFd, &ready, 1) != 1) _exit(82);
  errno = E2BIG;
  while (!finished) syscall(SYS_sched_yield);
  threadErrno = errno;
  return nullptr;
}

int main(int argc, char **argv) {
  require(argc == 3, "arguments");
  const bool retire = strcmp(argv[1], "retire") == 0;
  const bool full = strcmp(argv[1], "full") == 0;
  require(retire || full || strcmp(argv[1], "keep") == 0, "mode");
  int pipeFd[2], entered[2], released[2], ready[2];
  require(pipe(pipeFd) == 0 && configureQuitPipeFd(pipeFd[0]) &&
          configureQuitPipeFd(pipeFd[1]), "self pipe");
  require((fcntl(pipeFd[1], F_GETFL) & O_NONBLOCK) &&
          (fcntl(pipeFd[1], F_GETFD) & FD_CLOEXEC), "nonblocking and CLOEXEC");
  if (full) {
    unsigned char block[4096]; memset(block, SIGTERM, sizeof(block));
    while (syscall(SYS_write, pipeFd[1], block, sizeof(block)) > 0) {}
    require(errno == EAGAIN, "fill nonblocking pipe");
  }
  require(pipe(entered) == 0 && pipe(released) == 0 && pipe(ready) == 0, "test gates");
  watchedFd = pipeFd[1]; enteredFd = entered[1]; releaseFd = released[0]; readyFd = ready[1];
  gQuitNotificationFd = pipeFd[1];
  require(signal(SIGTERM, quitApplication) != SIG_ERR, "handler registration");
  pthread_t thread;
  require(pthread_create(&thread, nullptr, worker, nullptr) == 0, "thread");
  char marker;
  require(read(ready[0], &marker, 1) == 1, "worker ready");
  require(pthread_kill(thread, SIGTERM) == 0, "real SIGTERM");
  require(read(entered[0], &marker, 1) == 1, "handler sampled fd");

  // Existing candidate's teardown, with no Qt operation needed for this race.
  gQuitNotificationFd = -1;
  signal(SIGINT, SIG_DFL); signal(SIGTERM, SIG_DFL);
  signal(SIGQUIT, SIG_DFL); signal(SIGHUP, SIG_DFL);
  if (retire) { close(pipeFd[0]); close(pipeFd[1]); }
  const int destination = open(argv[2], O_CREAT|O_TRUNC|O_RDWR, 0600);
  require(destination >= 0, "owned replacement file");
  if (retire) require(dup2(destination, watchedFd) == watchedFd, "legal fd reuse");
  const char release = 'L';
  require(syscall(SYS_write, released[1], &release, 1) == 1, "resume handler");
  require(pthread_join(thread, nullptr) == 0, "join handler thread");
  unsigned char byte = 0;
  const ssize_t bytes = pread(destination, &byte, 1, 0);
  require(actualWrite == (full ? -1 : 1) && threadErrno == E2BIG, "handler result and errno");
  require(bytes == (retire ? 1 : 0), "destination size");
  if (retire) require(byte == SIGTERM, "foreign destination byte");
  else require(read(pipeFd[0], &byte, 1) == 1 && byte == SIGTERM, "original pipe byte");
  printf("{\"mode\":\"%s\",\"sampled_fd\":%d,\"global_revoked\":true,"
         "\"write_return\":%zd,\"foreign_file_bytes\":%zd,\"byte\":%u,"
         "\"errno_preserved\":true}\n", argv[1], watchedFd, actualWrite, bytes, byte);
  return 0;
}
