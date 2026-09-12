// Research-only controller for the bounded #87 continuity re-evaluation.
// No student program or project-file operation.
#include "file_broker_c.h"
#include <webots/robot.h>
#include <webots/supervisor.h>
#include <cerrno>
#include <csignal>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <execinfo.h>
#include <fcntl.h>
#include <initializer_list>
#include <sys/stat.h>
#include <unistd.h>

static int gJournal = -1;
static unsigned gSequence = 0;

static bool journal_event(const char *format, ...) {
  if (gJournal < 0)
    return false;
  char detail[2048];
  va_list arguments;
  va_start(arguments, format);
  const int length = std::vsnprintf(detail, sizeof(detail), format, arguments);
  va_end(arguments);
  if (length < 0 || length >= static_cast<int>(sizeof(detail)))
    return false;
  char line[2304];
  const int written = std::snprintf(line, sizeof(line), "CONTINUITY_V1 seq=%u %s\n", ++gSequence, detail);
  if (written < 0 || written >= static_cast<int>(sizeof(line)))
    return false;
  if (::write(gJournal, line, static_cast<size_t>(written)) != written)
    return false;
  return ::fdatasync(gJournal) == 0;
}

static void fatal(int signal) {
  if (gJournal >= 0) {
    const char mark[] = "CONTINUITY_V1 FATAL\n";
    (void)::write(gJournal, mark, sizeof(mark) - 1);
  }
  const char mark[] = "Q87 FATAL\n";
  ::write(STDERR_FILENO, mark, sizeof(mark) - 1);
  void *frames[64];
  const int count = ::backtrace(frames, 64);
  ::backtrace_symbols_fd(frames, count, STDERR_FILENO);
  _exit(128 + signal);
}

static int open_journal(const char *evidence, char *ackPath, size_t ackSize) {
  char journalPath[4096];
  if (std::snprintf(journalPath, sizeof(journalPath), "%s/controller-continuity.log", evidence) >= static_cast<int>(sizeof(journalPath)))
    return -1;
  if (std::snprintf(ackPath, ackSize, "%s/continuity-observed.ack", evidence) >= static_cast<int>(ackSize))
    return -1;
  const int fd = ::open(journalPath, O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC, 0600);
  if (fd < 0)
    return -1;
  const int directory = ::open(evidence, O_RDONLY | O_DIRECTORY | O_CLOEXEC);
  if (directory < 0 || ::fsync(directory) != 0) {
    if (directory >= 0)
      ::close(directory);
    ::close(fd);
    return -1;
  }
  ::close(directory);
  return fd;
}

int main() {
  setvbuf(stdout, nullptr, _IONBF, 0);
  void *warmup[1]; (void)::backtrace(warmup, 1);
  struct sigaction action {};
  action.sa_handler = fatal;
  sigemptyset(&action.sa_mask);
  action.sa_flags = SA_RESETHAND;
  for (int signal : {SIGSEGV, SIGABRT, SIGBUS, SIGILL, SIGFPE})
    if (sigaction(signal, &action, nullptr))
      return 120;

  const char *evidence = std::getenv("Q87_EVIDENCE");
  if (!evidence)
    return 121;
  char ackPath[4096];
  gJournal = open_journal(evidence, ackPath, sizeof(ackPath));
  if (gJournal < 0)
    return 121;
  if (!journal_event("event=CONTROLLER_STARTED pid=%ld", static_cast<long>(::getpid())))
    return 121;

  char pidPath[4096];
  if (std::snprintf(pidPath, sizeof(pidPath), "%s/controller.pid", evidence) >= static_cast<int>(sizeof(pidPath)))
    return 121;
  FILE *pid = std::fopen(pidPath, "wx");
  if (!pid)
    return 121;
  std::fprintf(pid, "%ld\n", static_cast<long>(::getpid()));
  std::fclose(pid);

  std::printf("Q87 BEFORE_WB_INIT pid=%ld\n", static_cast<long>(::getpid()));
  wb_robot_init();
  if (!journal_event("event=WB_INIT_RETURN time=%.6f", wb_robot_get_time()))
    return 121;
  std::puts("Q87 WB_INIT_RETURN");

  if (!journal_event("event=PROVIDER_CALLED"))
    return 121;
  std::puts("Q87 PROVIDER_CALLED");
  WbFileBroker *broker = wb_file_broker_create_qt();
  if (!broker)
    return 122;
  if (!journal_event("event=PROVIDER_RETURNED"))
    return 121;
  std::puts("Q87 PROVIDER_RETURNED");

  const double before = wb_robot_get_time();
  if (!journal_event("event=LOOP_BEGIN time=%.6f", before))
    return 121;
  for (int step = 1; step <= 8; ++step) {
    const int result = wb_robot_step(32);
    const double now = wb_robot_get_time();
    if (!journal_event("event=STEP n=%d result=%d time=%.6f", step, result, now))
      return 121;
    if (result == -1)
      return 123;
  }
  const double after = wb_robot_get_time();
  if (!(after > before) || !journal_event("event=LOOP_END before=%.6f after=%.6f", before, after))
    return 123;

  char response[1024];
  if (!wb_file_broker_handle_message(broker, "WEBEEBLOCKS_FILE_BROKER_V1 REQUEST 1 CAPABILITIES", response, sizeof(response)))
    return 124;
  if (!std::strstr(response, "\"operationsReady\":false"))
    return 124;
  if (!journal_event("event=CAPABILITIES operationsReady=false"))
    return 121;

  wb_file_broker_destroy(broker);
  broker = nullptr;
  if (!journal_event("event=PROVIDER_DESTROYED"))
    return 121;
  if (!journal_event("event=PRE_SHUTDOWN_READY"))
    return 121;

  // The external harness creates this acknowledgement only after it has read and
  // validated the controller-owned journal while Webots and this controller are
  // still alive. Therefore the shutdown request cannot precede the continuity
  // observation that #301 was unable to establish.
  bool observed = false;
  for (int attempt = 0; attempt < 300; ++attempt) {
    if (::access(ackPath, F_OK) == 0) {
      observed = true;
      break;
    }
    if (errno != ENOENT)
      return 126;
    if (wb_robot_step(32) == -1)
      return 126;
  }
  if (!observed)
    return 126;
  if (!journal_event("event=SHUTDOWN_ACK_OBSERVED"))
    return 121;
  ::close(gJournal);
  gJournal = -1;

  wb_supervisor_simulation_quit(0);
  wb_robot_cleanup();
  return 0;
}
