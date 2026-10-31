// R3 host test: the OS-held lock, not an OWNED tombstone or a PID, proves
// extinction of the previous native authority. Run with an isolated STATE_DIR.
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
  char token[65], stale[65], digest[65], key[65];
  memset(token, 'a', 64); token[64] = 0;
  memset(stale, 'b', 64); stale[64] = 0;
  memset(digest, 'c', 64); digest[64] = 0;
  memset(key, 'd', 64); key[64] = 0;

  assert(wb_rg_setup(&a, world) && a.state == WB_RG_NONE);
  char epoch_a[33]; memcpy(epoch_a, a.epoch, sizeof(epoch_a));
  assert(!wb_rg_setup(&b, world)); // second native lifetime cannot enter
  assert(!wb_rg_arm(&a, token, digest, key)); // no arm before claim
  assert(wb_rg_claim(&a));
  assert(wb_rg_refresh(&a) == WB_RG_OWNED);
  assert(!wb_rg_setup(&b, world)); // persistent lock even after OWNED
  assert(wb_rg_arm(&a, token, digest, key));
  assert(wb_rg_refresh(&a) == WB_RG_PENDING);
  assert(!wb_rg_setup(&b, world)); // PENDING stays intact through contention
  assert(!wb_rg_clear(&a, stale, digest));
  assert(!wb_rg_clear(&a, token, stale));
  assert(!wb_rg_clear(&a, token, ""));
  assert(wb_rg_clear(&a, token, digest));
  assert(wb_rg_refresh(&a) == WB_RG_OWNED);
  wb_rg_release(&a);

  // Second ordinary classroom session: residual OWNED can be reclaimed
  // ONLY after an actual OS release; it never clears or overwrites PENDING.
  assert(wb_rg_setup(&b, world) && b.state == WB_RG_OWNED);
  assert(strcmp(b.epoch, epoch_a) != 0); // stale 128-bit epoch cannot authorize
  assert(wb_rg_claim(&b));               // formerly deterministic P0-A failure
  assert(wb_rg_refresh(&b) == WB_RG_OWNED);
  assert(!wb_rg_setup(&a, world));
  assert(wb_rg_arm(&b, stale, digest, key));
  wb_rg_release(&b); // world reload / crash in PENDING

  assert(wb_rg_setup(&a, world) && a.state == WB_RG_PENDING);
  assert(!wb_rg_claim(&a)); // PENDING never becomes a fresh session
  assert(strcmp(a.token, stale) == 0 && strcmp(a.digest, digest) == 0);
  assert(strcmp(a.owner_key, key) == 0);
  assert(!wb_rg_clear(&a, token, digest));
  assert(!wb_rg_clear(&a, stale, stale));
  assert(wb_rg_clear(&a, stale, digest)); // only verified recovery can clear
  wb_rg_release(&a);

  // Aborted atomic write: orphan .next must not truncate the old OWNED.
  assert(wb_rg_setup(&a, world) && a.state == WB_RG_OWNED);
  assert(wb_rg_claim(&a));
  char tmp[sizeof(a.path) + 8];
  assert(snprintf(tmp, sizeof(tmp), "%s.next", a.path) < (int)sizeof(tmp));
  FILE *t = fopen(tmp, "wb");
  assert(t && fputs("TORN", t) >= 0 && fclose(t) == 0);
  assert(!wb_rg_arm(&a, token, digest, key));
  assert(wb_rg_refresh(&a) == WB_RG_OWNED);
  assert(remove(tmp) == 0); // controlled test cleanup, never production cleanup
  assert(wb_rg_arm(&a, token, digest, key));
  assert(wb_rg_refresh(&a) == WB_RG_PENDING);
  wb_rg_release(&a);

  // Legacy, interrupted durable records must remain invalid, never NONE.
  assert(wb_rg_setup(&a, world) && a.state == WB_RG_PENDING);
  t = fopen(a.path, "wb");
  assert(t && fputs("WEBEEBLOCKS_RECOVERY_V3 ", t) >= 0 && fclose(t) == 0);
  assert(wb_rg_refresh(&a) == WB_RG_INVALID);
  wb_rg_release(&a);
  assert(!wb_rg_setup(&b, world) && b.state == WB_RG_INVALID);
  assert(remove(a.path) == 0); // controlled test fixture reset
  t = fopen(a.path, "wb");
  assert(t && fprintf(t, "WEBEEBLOCKS_RECOVERY_V1 %s\n", stale) > 0 && fclose(t) == 0);
  assert(!wb_rg_setup(&b, world) && b.state == WB_RG_INVALID);
  puts("PASS: R3 lifetime lock, new-session OWNED, distinct epoch, PENDING persistence, atomic replacement, invalid records");
  return 0;
}
