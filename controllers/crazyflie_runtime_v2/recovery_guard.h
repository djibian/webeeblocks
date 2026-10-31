// Webots world reload destroys its controller and Robot Window. This small
// on-disk witness is independent of the browser profile and of world memory.
// It does NOT store a pupil program: loss of Blockly storage must fail closed.
// One bounded file per local user/world; no automatic expiry or silent discard.
#ifndef WEBEEBLOCKS_RECOVERY_GUARD_H
#define WEBEEBLOCKS_RECOVERY_GUARD_H

#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <io.h>
#else
#include <unistd.h>
#endif

enum { WB_RG_INVALID = -1, WB_RG_NONE = 0, WB_RG_PENDING = 1 };
typedef struct {
  char path[1024];
  char token[65];
  char digest[65];
  int state;
} wb_recovery_guard_t;

static int wb_rg_hex64(const char *s) {
  if (!s || strlen(s) != 64) return 0;
  return strspn(s, "0123456789abcdef") == 64;
}

static int wb_rg_refresh(wb_recovery_guard_t *g) {
  g->state = WB_RG_INVALID;
  g->token[0] = '\0';
  g->digest[0] = '\0';
  if (!g->path[0]) return g->state;
  FILE *f = fopen(g->path, "rb");
  if (!f) {
    if (errno == ENOENT) g->state = WB_RG_NONE;
    return g->state;
  }
  char record[192] = {0};
  // V1 records are intentionally INVALID; never mistake legacy state for NONE.
  const char *prefix = "WEBEEBLOCKS_RECOVERY_V2 ";
  size_t n = fread(record, 1, sizeof(record), f);
  int eof = feof(f);
  int bad = ferror(f);
  fclose(f);
  const size_t p = strlen(prefix);
  // Exactly one complete record, never accept truncation or extra bytes.
  if (!bad && eof && n == p + 64 + 1 + 64 + 1 &&
      memcmp(record, prefix, p) == 0 && record[p + 64] == ' ' &&
      record[p + 64 + 1 + 64] == '\n') {
    memcpy(g->token, record + p, 64); g->token[64] = '\0';
    memcpy(g->digest, record + p + 65, 64); g->digest[64] = '\0';
    if (wb_rg_hex64(g->token) && wb_rg_hex64(g->digest))
      g->state = WB_RG_PENDING;
  }
  return g->state;
}

static int wb_rg_setup(wb_recovery_guard_t *g, const char *world) {
  memset(g, 0, sizeof(*g));
  g->state = WB_RG_INVALID;
  const char *home = getenv("WEBEEBLOCKS_RECOVERY_STATE_DIR");
  if (!home || !*home) {
#ifdef _WIN32
    home = getenv("LOCALAPPDATA");
#else
    home = getenv("HOME");
#endif
  }
  if (!home || !*home || !world || !*world) return 0;
  uint64_t hash = UINT64_C(14695981039346656037);
  for (const unsigned char *p = (const unsigned char *)world; *p; ++p) {
    hash ^= *p;
    hash *= UINT64_C(1099511628211);
  }
  int written = snprintf(g->path, sizeof(g->path),
    "%s/%s%016llx.state", home, ".webeeblocks-recovery-",
    (unsigned long long)hash);
  if (written < 0 || (size_t)written >= sizeof(g->path)) {
    g->path[0] = '\0';
    return 0;
  }
  wb_rg_refresh(g);
  return g->state != WB_RG_INVALID;
}

static int wb_rg_arm(wb_recovery_guard_t *g, const char *token, const char *digest) {
  if (!wb_rg_hex64(token) || !wb_rg_hex64(digest) || wb_rg_refresh(g) != WB_RG_NONE) return 0;
  // A crash during this write leaves an INVALID witness, never an absent one.
  FILE *f = fopen(g->path, "wb");
  if (!f) { g->state = WB_RG_INVALID; return 0; }
  int ok = fprintf(f, "WEBEEBLOCKS_RECOVERY_V2 %s %s\n", token, digest) > 0 &&
           fflush(f) == 0;
  if (ok) {
#ifdef _WIN32
    ok = _commit(_fileno(f)) == 0;
#else
    ok = fsync(fileno(f)) == 0;
#endif
  }
  if (fclose(f) != 0) ok = 0;
  if (!ok) { g->state = WB_RG_INVALID; return 0; }
  return wb_rg_refresh(g) == WB_RG_PENDING &&
         strcmp(g->token, token) == 0 && strcmp(g->digest, digest) == 0;
}

static int wb_rg_clear(wb_recovery_guard_t *g, const char *token, const char *digest) {
  if (!wb_rg_hex64(digest) || wb_rg_refresh(g) != WB_RG_PENDING ||
      strcmp(g->token, token) != 0 || strcmp(g->digest, digest) != 0) return 0;
  if (remove(g->path) != 0) { g->state = WB_RG_INVALID; return 0; }
  return wb_rg_refresh(g) == WB_RG_NONE;
}
#endif
