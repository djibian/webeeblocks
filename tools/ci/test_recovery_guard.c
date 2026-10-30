// Host-only adversarial verification of the exact native recovery witness.
#ifdef NDEBUG
#undef NDEBUG
#endif
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../../controllers/crazyflie_runtime_v2/recovery_guard.h"

int main(void) {
  const char *world = "/synthetic/robot/worlds/guard-world.wbt";
  wb_recovery_guard_t a, b;
  assert(wb_rg_setup(&a, world));
  // The job uses its own temporary HOME; do not erase any real pupil state.
  assert(a.state == WB_RG_NONE);
  assert(!wb_rg_arm(&a, "broken"));
  char token[65]; memset(token, 'a', 64); token[64] = 0;
  char stale[65]; memset(stale, 'b', 64); stale[64] = 0;
  assert(wb_rg_arm(&a, token));
  assert(wb_rg_setup(&b, world) && b.state == WB_RG_PENDING);
  assert(strcmp(b.token, token) == 0);
  assert(!wb_rg_arm(&b, stale)); // no overwrite of an unfinished recovery
  assert(!wb_rg_clear(&b, stale)); // old ACK never clears live witness
  assert(wb_rg_refresh(&a) == WB_RG_PENDING);
  assert(wb_rg_clear(&a, token));
  assert(wb_rg_refresh(&b) == WB_RG_NONE);
  // A corrupt/incomplete checkpoint is a permanent lock, not a new session.
  FILE *f = fopen(a.path, "wb");
  assert(f);
  assert(fputs("WEBEEBLOCKS_RECOVERY_V1 bad", f) > 0);
  assert(fclose(f) == 0);
  assert(!wb_rg_setup(&b, world) && b.state == WB_RG_INVALID);
  assert(!wb_rg_arm(&b, token));
  assert(!wb_rg_clear(&b, token));
  assert(remove(a.path) == 0); // test cleanup only
  // A stale but valid witness on a legitimate startup stays locked.
  assert(wb_rg_arm(&a, stale));
  assert(wb_rg_setup(&b, world) && b.state == WB_RG_PENDING);
  assert(!wb_rg_clear(&b, token));
  assert(wb_rg_clear(&b, stale));
  puts("PASS: native independent witness, interrupted reload, stale token, corrupt record, no silent expiry");
  return 0;
}
