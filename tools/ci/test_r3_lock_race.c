// Two independent native processes synchronized at a file barrier.
// Each process must use the real OS lock in recovery_guard.h.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <windows.h>
#else
#include <time.h>
#include <unistd.h>
#endif
#include "../../controllers/crazyflie_runtime_v2/recovery_guard.h"

static void pause_millis(void) {
#ifdef _WIN32
  Sleep(20);
#else
  struct timespec ts = {0, 20000000};
  nanosleep(&ts, NULL);
#endif
}

static int exists(const char *path) {
  FILE *f = fopen(path, "rb");
  if (!f) return 0;
  fclose(f);
  return 1;
}

static int signal_file(const char *path, const char *value) {
  FILE *f = fopen(path, "wb");
  if (!f) return 0;
  int ok = fputs(value, f) >= 0 && fflush(f) == 0;
  if (fclose(f) != 0) ok = 0;
  return ok;
}

static int wait_for(const char *path) {
  for (int i = 0; i < 1500; ++i) {
    if (exists(path)) return 1;
    pause_millis();
  }
  return 0; // Timeout only fails the test; never grants authority.
}

int main(int argc, char **argv) {
  const char *dir = getenv("WEBEEBLOCKS_RECOVERY_STATE_DIR");
  const char *world = "/synthetic/robot/worlds/r3-interprocess.wbt";
  char ready[1200], result[1200], go[1200], stop[1200];
  if (!dir || argc != 2) return 90;
  if (snprintf(ready, sizeof(ready), "%s/ready-%s", dir, argv[1]) >= (int)sizeof(ready) ||
      snprintf(result, sizeof(result), "%s/result-%s", dir, argv[1]) >= (int)sizeof(result) ||
      snprintf(go, sizeof(go), "%s/go", dir) >= (int)sizeof(go) ||
      snprintf(stop, sizeof(stop), "%s/stop", dir) >= (int)sizeof(stop)) return 91;
  if (strcmp(argv[1], "crash-owner") == 0 ||
      strcmp(argv[1], "crash-pending") == 0) {
    wb_recovery_guard_t g;
    if (!wb_rg_setup(&g, world) || !wb_rg_claim(&g)) return 98;
    if (strcmp(argv[1], "crash-pending") == 0) {
      char key[65], token[65], digest[65];
      memset(key, 'd', 64); key[64] = 0;
      memset(token, 'a', 64); token[64] = 0;
      memset(digest, 'c', 64); digest[64] = 0;
      if (!wb_rg_arm(&g, token, digest, key)) return 99;
    }
    if (!signal_file(ready, "READY\n")) return 100;
    for (;;) pause_millis(); // Parent force-kills; OS MUST release the lock.
  }
  if (strcmp(argv[1], "check-pending") == 0) {
    wb_recovery_guard_t g;
    if (!wb_rg_setup(&g, world) || g.state != WB_RG_PENDING ||
        !wb_rg_hex64(g.token) || !wb_rg_hex64(g.digest) ||
        !wb_rg_hex64(g.owner_key) || wb_rg_claim(&g)) return 101;
    wb_rg_release(&g);
    puts("PASS: force-killed PENDING remains intact, cannot start a new session");
    return 0;
  }
  if (strcmp(argv[1], "restart") == 0) {
    wb_recovery_guard_t g;
    if (!wb_rg_setup(&g, world) || g.state != WB_RG_OWNED || !wb_rg_claim(&g))
      return 92;
    wb_rg_release(&g);
    puts("PASS: ordinary fresh-session claim after both processes exited");
    return 0;
  }
  if (strcmp(argv[1], "one") && strcmp(argv[1], "two")) return 93;
  if (!signal_file(ready, "READY\n") || !wait_for(go)) return 94;
  wb_recovery_guard_t g;
  const int won = wb_rg_setup(&g, world);
  if (won && !wb_rg_claim(&g)) return 95;
  if (!signal_file(result, won ? "OWNER\n" : "DENIED\n")) return 96;
  if (won) {
    if (!wait_for(stop)) return 97;
    wb_rg_release(&g);
  }
  return 0;
}
