/* Host qualification only. This program never loads Webots or a controller. */
#include <errno.h>
#include <signal.h>
#include <stdio.h>
#include <string.h>
#include <sys/ptrace.h>
#include <sys/wait.h>
#include <unistd.h>

__attribute__((noinline)) static void intentional_fixture_segv(void) {
  raise(SIGSEGV);
}

int main(int argc, char **argv) {
  setbuf(stdout, NULL);
  if (argc != 2) return 2;
  printf("FIXTURE pid=%d mode=%s\n", getpid(), argv[1]);
  if (!strcmp(argv[1], "snapshot")) {
    raise(SIGSTOP);
    return 0;
  }
  if (!strcmp(argv[1], "ptrace")) {
    errno = 0;
    long result = ptrace(PTRACE_TRACEME, 0, NULL, NULL);
    printf("PTRACE result=%ld errno=%d\n", result, errno);
    return result < 0 ? 77 : 0;
  }
  if (!strcmp(argv[1], "wrapper")) {
    pid_t child = fork();
    if (child < 0) return 3;
    if (child == 0) {
      execl(argv[0], argv[0], "segv", (char *)NULL);
      _exit(4);
    }
    int status;
    if (waitpid(child, &status, 0) != child) return 5;
    printf("WAIT child=%d raw_status=%d exited=%d exit=%d signaled=%d signal=%d core_bit=%d\n",
           child, status, WIFEXITED(status), WIFEXITED(status) ? WEXITSTATUS(status) : -1,
           WIFSIGNALED(status), WIFSIGNALED(status) ? WTERMSIG(status) : 0,
           WIFSIGNALED(status) ? !!WCOREDUMP(status) : 0);
    /* A living launcher must not become a healthy-native-process assertion. */
    usleep(500000);
    return 0;
  }
  usleep(250000);
  if (!strcmp(argv[1], "segv")) intentional_fixture_segv();
  if (!strcmp(argv[1], "exit42")) return 42;
  return 6;
}
