// Host-only adversarial verification of native token + independent SHA-256.
// All files reside in a temporary HOME supplied by the invoking job.
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
  assert(wb_rg_setup(&a, world) && a.state == WB_RG_NONE);
  char token[65], stale[65], digest[65], wrong[65];
  memset(token, 'a', 64); token[64] = 0;
  memset(stale, 'b', 64); stale[64] = 0;
  memset(digest, 'c', 64); digest[64] = 0;
  memset(wrong, 'd', 64); wrong[64] = 0;
  assert(!wb_rg_arm(&a, "broken", digest));
  assert(!wb_rg_arm(&a, token, "broken"));
  assert(wb_rg_arm(&a, token, digest));
  assert(wb_rg_setup(&b, world) && b.state == WB_RG_PENDING);
  assert(strcmp(b.token, token) == 0 && strcmp(b.digest, digest) == 0);
  assert(!wb_rg_arm(&b, stale, wrong)); // no overwrite
  assert(!wb_rg_clear(&b, stale, digest)); // wrong token
  assert(!wb_rg_clear(&b, token, wrong)); // semantic alteration
  assert(!wb_rg_clear(&b, token, "")); // missing digest
  assert(wb_rg_refresh(&a) == WB_RG_PENDING);
  assert(wb_rg_clear(&a, token, digest));
  assert(wb_rg_refresh(&b) == WB_RG_NONE);

  // Interrupted record and mismatching old format must remain INVALID.
  FILE *f = fopen(a.path, "wb");
  assert(f && fputs("WEBEEBLOCKS_RECOVERY_V2 ", f) > 0);
  assert(fclose(f) == 0);
  assert(!wb_rg_setup(&b, world) && b.state == WB_RG_INVALID);
  assert(!wb_rg_arm(&b, token, digest));
  assert(!wb_rg_clear(&b, token, digest));
  assert(remove(a.path) == 0);
  f = fopen(a.path, "wb");
  assert(f && fprintf(f, "WEBEEBLOCKS_RECOVERY_V1 %s\\n", stale) > 0);
  assert(fclose(f) == 0);
  assert(!wb_rg_setup(&b, world) && b.state == WB_RG_INVALID);
  assert(!wb_rg_arm(&b, token, digest)); // cannot auto-migrate V1
  assert(remove(a.path) == 0);
  // A valid but stale witness requires the exact token AND exact digest.
  assert(wb_rg_arm(&a, stale, digest));
  assert(wb_rg_setup(&b, world) && b.state == WB_RG_PENDING);
  assert(!wb_rg_clear(&b, token, digest));
  assert(!wb_rg_clear(&b, stale, wrong));
  assert(wb_rg_clear(&b, stale, digest));
  puts("PASS: witness SHA-256 binding, bad digest, legacy V1, interrupted write, stale token, fail closed");
  return 0;
}
