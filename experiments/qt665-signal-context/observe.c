#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <unistd.h>

/* Observation only: forward unchanged handlers and glibc allocator calls.
 * No printf/dlsym/allocation in the handler instrumentation itself.
 * Initial-exec TLS avoids lazy TLS allocation in allocator interposition.
 * Fixed 48-byte writes fit PIPE_BUF; the trace file is outside mission seals.
 */
extern void *__libc_malloc(size_t);
extern void *__libc_calloc(size_t, size_t);
extern void *__libc_realloc(void *, size_t);
extern void __libc_free(void *);
typedef void (*handler_t)(int);
static handler_t (*real_signal)(int, handler_t);
static handler_t callbacks[NSIG];
static int trace_fd = -1;
static int active;
static __thread volatile sig_atomic_t depth __attribute__((tls_model("initial-exec")));

static void record(unsigned char event, uint64_t value) {
  if (trace_fd < 0) return;
  int saved = errno;
  uint64_t row[6] = {0x5154363635534947ULL, (uint64_t)getpid(),
                    (uint64_t)syscall(SYS_gettid), event, (uint64_t)depth, value};
  /* A failed/partial record makes the offline proof incomplete, never PASS. */
  (void)syscall(SYS_write, trace_fd, row, sizeof(row));
  errno = saved;
}

__attribute__((constructor)) static void initialize(void) {
  char exe[4096];
  ssize_t n = readlink("/proc/self/exe", exe, sizeof(exe)-1);
  if (n < 11) return;
  exe[n] = 0;
  if (strcmp(exe+n-11, "/webots-bin")) return;
  const char *path = getenv("QT665_SIGNAL_TRACE");
  if (!path) return;
  trace_fd = open(path, O_WRONLY|O_APPEND|O_CREAT|O_CLOEXEC, 0600);
  if (trace_fd < 0) _exit(91);
  real_signal = dlsym(RTLD_NEXT, "signal");
  if (!real_signal) _exit(92);
  active = 1;
  struct stat info;
  if (stat("/proc/self/exe", &info)) _exit(93);
  record('B', 0); record('I', info.st_ino); record('D', info.st_dev);
  const char *maps = getenv("QT665_SIGNAL_MAPS");
  if (!maps) _exit(94);
  int input = open("/proc/self/maps", O_RDONLY|O_CLOEXEC);
  int output = open(maps, O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC, 0600);
  if (input < 0 || output < 0) _exit(95);
  char buffer[4096];
  while ((n = read(input, buffer, sizeof(buffer))) > 0) {
    if (write(output, buffer, n) != n) _exit(96);
  }
  if (n < 0) _exit(97);
  close(input); close(output);
}

static void observed_handler(int number) {
  ++depth; record('E', number);
  callbacks[number](number);
  record('L', number); --depth;
}

handler_t signal(int number, handler_t callback) {
  if (!real_signal) real_signal = dlsym(RTLD_NEXT, "signal");
  if (!real_signal) _exit(98);
  if (!active || (number != SIGTERM && number != SIGINT && number != SIGQUIT && number != SIGHUP)
      || callback == SIG_DFL || callback == SIG_IGN || callback == SIG_ERR)
    return real_signal(number, callback);
  Dl_info owner;
  if (!dladdr((void *)callback, &owner) || !owner.dli_fname || !strstr(owner.dli_fname, "webots-bin"))
    return real_signal(number, callback);
  handler_t previous = callbacks[number];
  callbacks[number] = callback;
  handler_t result = real_signal(number, observed_handler);
  if (result == SIG_ERR) { callbacks[number] = previous; return result; }
  record('R', (uint64_t)(uintptr_t)callback); record('S', number);
  record('P', (uint64_t)(uintptr_t)owner.dli_fbase);
  return result == observed_handler ? previous : result;
}

void *malloc(size_t size) {
  if (depth) record('M', size);
  void *result = __libc_malloc(size);
  if (depth) record('m', (uint64_t)(uintptr_t)result);
  return result;
}
void *calloc(size_t n, size_t size) {
  if (depth) record('C', n*size);
  void *result = __libc_calloc(n, size);
  if (depth) record('c', (uint64_t)(uintptr_t)result);
  return result;
}
void *realloc(void *ptr, size_t size) {
  if (depth) record('A', size);
  void *result = __libc_realloc(ptr, size);
  if (depth) record('a', (uint64_t)(uintptr_t)result);
  return result;
}
void free(void *ptr) {
  if (depth) record('F', (uint64_t)(uintptr_t)ptr);
  __libc_free(ptr);
}
