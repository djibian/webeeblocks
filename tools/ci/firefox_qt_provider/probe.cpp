// Research-only controller. No student program or project-file operation.
#include "file_broker_c.h"
#include <webots/robot.h>
#include <webots/supervisor.h>
#include <csignal>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <execinfo.h>
#include <initializer_list>
#include <unistd.h>

static void fatal(int signal) {
  const char *mark = "Q87 FATAL\n";
  ::write(STDERR_FILENO, mark, std::strlen(mark));
  void *frames[64];
  int count = ::backtrace(frames, 64);
  ::backtrace_symbols_fd(frames, count, STDERR_FILENO);
  _exit(128 + signal);
}

int main() {
  setvbuf(stdout, nullptr, _IONBF, 0);
  void *warmup[1]; (void)::backtrace(warmup, 1);
  struct sigaction action {};
  action.sa_handler = fatal;
  sigemptyset(&action.sa_mask);
  action.sa_flags = SA_RESETHAND;
  for (int signal : {SIGSEGV, SIGABRT, SIGBUS, SIGILL, SIGFPE})
    if (sigaction(signal, &action, nullptr)) return 120;
  const char *evidence = std::getenv("Q87_EVIDENCE");
  if (!evidence) return 121;
  char filename[4096];
  if (std::snprintf(filename, sizeof(filename), "%s/controller.pid", evidence) >= static_cast<int>(sizeof(filename))) return 121;
  FILE *pid = std::fopen(filename, "wx");
  if (!pid) return 121;
  std::fprintf(pid, "%ld\n", static_cast<long>(::getpid()));
  std::fclose(pid);
  std::printf("Q87 BEFORE_WB_INIT pid=%ld\n", static_cast<long>(::getpid()));
  wb_robot_init();
  std::puts("Q87 WB_INIT_RETURN");
  std::puts("Q87 PROVIDER_CALLED");
  WbFileBroker *broker = wb_file_broker_create_qt();
  if (!broker) return 122;
  std::puts("Q87 PROVIDER_RETURNED");
  const double before = wb_robot_get_time();
  for (int step = 0; step < 8; ++step) {
    if (wb_robot_step(32) == -1) return 123;
  }
  const double after = wb_robot_get_time();
  if (!(after > before)) return 123;
  std::printf("Q87 LOOP_RETURN steps=8 before=%.6f after=%.6f\n", before, after);
  char response[1024];
  if (!wb_file_broker_handle_message(broker, "WEBEEBLOCKS_FILE_BROKER_V1 REQUEST 1 CAPABILITIES", response, sizeof(response))) return 124;
  if (!std::strstr(response, "\"operationsReady\":false")) return 124;
  std::puts("Q87 CAPABILITIES_RETURN operationsReady=false");
  wb_file_broker_destroy(broker);
  std::puts("Q87 PROVIDER_DESTROYED");
  wb_supervisor_simulation_quit(0);
  wb_robot_cleanup();
  std::puts("Q87 CONTROLLER_COMPLETE");
  return 0;
}
