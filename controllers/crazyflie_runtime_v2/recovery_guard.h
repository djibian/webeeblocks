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
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#else
#include <fcntl.h>
#include <sys/file.h>
#include <unistd.h>
#endif

enum { WB_RG_INVALID = -1, WB_RG_NONE = 0, WB_RG_PENDING = 1, WB_RG_OWNED = 2 };
// OWNED is only a durable uncertainty marker, never a process lease.
// The distinct OS lock is held for the entire lifetime of the effectful C
// controller. A successor may reclaim OWNED only after it holds that lock.
#define WB_RG_OWNED_RECORD "WEBEEBLOCKS_OWNER_V1\n"
typedef struct {
  char path[1024];
  char token[65];
  char digest[65];
  char owner_key[65];  // Unicast upstream capability; never sent in replies/logs.
  int state;
  char epoch[33];  // Fresh OS RNG incarnation prefix, not a bearer secret.
  int lock_held;
#ifdef _WIN32
  HANDLE lock_handle;
#else
  int lock_fd;
#endif
} wb_recovery_guard_t;

/* Never unlink the stable .lock inode: replacing it would split the lock. */
static void wb_rg_release(wb_recovery_guard_t *g) {
  if (!g || !g->lock_held) return;
#ifdef _WIN32
  OVERLAPPED ov = {0};
  UnlockFileEx(g->lock_handle, 0, 1, 0, &ov);
  CloseHandle(g->lock_handle);
  g->lock_handle = INVALID_HANDLE_VALUE;
#else
  flock(g->lock_fd, LOCK_UN);
  close(g->lock_fd);
  g->lock_fd = -1;
#endif
  g->lock_held = 0;
}

static int wb_rg_lock(wb_recovery_guard_t *g) {
  char lock_path[sizeof(g->path) + 8];
  int n = snprintf(lock_path, sizeof(lock_path), "%s.lock", g->path);
  if (n < 0 || (size_t)n >= sizeof(lock_path)) return 0;
#ifdef _WIN32
  // OPEN_ALWAYS + non-inheritable HANDLE + kernel-managed byte-range lock.
  // The lock file is permanent, not an O_EXCL owner marker.
  HANDLE h = CreateFileA(lock_path, GENERIC_READ | GENERIC_WRITE,
                         FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_ALWAYS,
                         FILE_ATTRIBUTE_NORMAL, NULL);
  if (h == INVALID_HANDLE_VALUE) return 0;
  OVERLAPPED ov = {0};
  if (!LockFileEx(h, LOCKFILE_EXCLUSIVE_LOCK | LOCKFILE_FAIL_IMMEDIATELY,
                  0, 1, 0, &ov)) {
    CloseHandle(h);
    return 0;
  }
  g->lock_handle = h;
#else
  int fd = open(lock_path, O_RDWR | O_CREAT | O_CLOEXEC, 0600);
  if (fd < 0) return 0;
  if (flock(fd, LOCK_EX | LOCK_NB) != 0) {
    close(fd);
    return 0;
  }
  g->lock_fd = fd;
#endif
  g->lock_held = 1;
  return 1;
}

/* The current native incarnation has a fresh 128-bit namespace. */
static int wb_rg_random_epoch(char epoch[33]) {
  unsigned char data[16];
#ifdef _WIN32
  // Resolve the OS CSPRNG dynamically to avoid extra Webots linker settings.
  HMODULE dll = LoadLibraryA("bcrypt.dll");
  if (!dll) return 0;
  typedef LONG (WINAPI *bcrypt_rng_fn)(void *, unsigned char *, unsigned long, unsigned long);
  bcrypt_rng_fn rng = (bcrypt_rng_fn)(void *)GetProcAddress(dll, "BCryptGenRandom");
  LONG status = rng ? rng(NULL, data, (unsigned long)sizeof(data), 2 /* BCRYPT_USE_SYSTEM_PREFERRED_RNG */) : -1;
  FreeLibrary(dll);
  if (status < 0) return 0;
#else
  int fd = open("/dev/urandom", O_RDONLY | O_CLOEXEC);
  if (fd < 0) return 0;
  size_t pos = 0;
  while (pos < sizeof(data)) {
    ssize_t got = read(fd, data + pos, sizeof(data) - pos);
    if (got < 0 && errno == EINTR) continue;
    if (got <= 0) { close(fd); return 0; }
    pos += (size_t)got;
  }
  if (close(fd) != 0) return 0;
#endif
  const char hex[] = "0123456789abcdef";
  for (size_t i = 0; i < sizeof(data); ++i) {
    epoch[2 * i] = hex[data[i] >> 4];
    epoch[2 * i + 1] = hex[data[i] & 15];
  }
  epoch[32] = '\0';
  return 1;
}

/* Exclusive create, exact bytes, durable file content. Never truncate an
 * existing durable record (especially PENDING). Any partial new file is
 * INVALID, not NONE; any partial temporary file leaves the old record intact. */
static int wb_rg_write_new(const char *path, const char *record) {
  const size_t size = strlen(record);
#ifdef _WIN32
  HANDLE h = CreateFileA(path, GENERIC_WRITE, FILE_SHARE_READ,
                         NULL, CREATE_NEW, FILE_ATTRIBUTE_NORMAL, NULL);
  if (h == INVALID_HANDLE_VALUE) return 0;
  size_t pos = 0;
  int ok = 1;
  while (pos < size) {
    DWORD written = 0;
    if (!WriteFile(h, record + pos, (DWORD)(size - pos), &written, NULL) || !written) {
      ok = 0; break;
    }
    pos += written;
  }
  if (ok) ok = FlushFileBuffers(h) != 0;
  if (!CloseHandle(h)) ok = 0;
#else
  int fd = open(path, O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC, 0600);
  if (fd < 0) return 0;
  size_t pos = 0;
  int ok = 1;
  while (pos < size) {
    ssize_t written = write(fd, record + pos, size - pos);
    if (written < 0 && errno == EINTR) continue;
    if (written <= 0) { ok = 0; break; }
    pos += (size_t)written;
  }
  if (ok) ok = fsync(fd) == 0;
  if (close(fd) != 0) ok = 0;
#endif
  return ok;
}

/* Only the lock owner can replace OWNED/PENDING. The temp name is intentionally
 * stable and CREATE_NEW: an orphaned partial write cannot be mistaken for a
 * successful or replayable transaction. A replacement is a single namespace
 * change; no O_TRUNC window ever exposes a torn PENDING. */
static int wb_rg_replace(wb_recovery_guard_t *g, const char *record) {
  if (!g->lock_held) return 0;
  char tmp[sizeof(g->path) + 8];
  int n = snprintf(tmp, sizeof(tmp), "%s.next", g->path);
  if (n < 0 || (size_t)n >= sizeof(tmp) || !wb_rg_write_new(tmp, record)) return 0;
#ifdef _WIN32
  if (!MoveFileExA(tmp, g->path, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH))
    return 0;
#else
  if (rename(tmp, g->path) != 0) return 0;
  // Directory synchronization makes the rename durable across power failure.
  char dir[sizeof(g->path)];
  memcpy(dir, g->path, strlen(g->path) + 1);
  char *slash = strrchr(dir, '/');
  if (!slash) return 0;
  if (slash == dir) slash[1] = '\0';
  else *slash = '\0';
  int dfd = open(dir, O_RDONLY | O_DIRECTORY | O_CLOEXEC);
  if (dfd < 0) return 0;
  int ok = fsync(dfd) == 0;
  if (close(dfd) != 0) ok = 0;
  if (!ok) return 0;
#endif
  return 1;
}

static int wb_rg_hex64(const char *s) {
  if (!s || strlen(s) != 64) return 0;
  return strspn(s, "0123456789abcdef") == 64;
}

/* Admission key namespace validation, shared by C protocol and native tests. */
static int wb_rg_current_key(const wb_recovery_guard_t *g, const char *key) {
  return g && g->lock_held && wb_rg_hex64(key) &&
         memcmp(key, g->epoch, 32) == 0;
}

static int wb_rg_refresh(wb_recovery_guard_t *g) {
  g->state = WB_RG_INVALID;
  g->token[0] = '\0';
  g->digest[0] = '\0';
  g->owner_key[0] = '\0';
  if (!g->path[0]) return g->state;
  FILE *f = fopen(g->path, "rb");
  if (!f) {
    if (errno == ENOENT) g->state = WB_RG_NONE;
    return g->state;
  }
  char record[320] = {0};
  // V1 records are intentionally INVALID; never mistake legacy state for NONE.
  const char *prefix = "WEBEEBLOCKS_RECOVERY_V3 ";
  size_t n = fread(record, 1, sizeof(record), f);
  int eof = feof(f);
  int bad = ferror(f);
  fclose(f);
  const size_t p = strlen(prefix);
  if (!bad && eof && n == strlen(WB_RG_OWNED_RECORD) &&
      memcmp(record, WB_RG_OWNED_RECORD, n) == 0) {
    g->state = WB_RG_OWNED;
    return g->state;
  }
  // Exactly one complete record, never accept truncation or extra bytes.
  if (!bad && eof && n == p + 64 + 1 + 64 + 1 + 64 + 1 &&
      memcmp(record, prefix, p) == 0 && record[p + 64] == ' ' &&
      record[p + 64 + 1 + 64] == ' ' && record[p + 64 + 1 + 64 + 1 + 64] == '\n') {
    memcpy(g->token, record + p, 64); g->token[64] = '\0';
    memcpy(g->digest, record + p + 65, 64); g->digest[64] = '\0';
    memcpy(g->owner_key, record + p + 130, 64); g->owner_key[64] = '\0';
    if (wb_rg_hex64(g->token) && wb_rg_hex64(g->digest) && wb_rg_hex64(g->owner_key))
      g->state = WB_RG_PENDING;
  }
  return g->state;
}

static int wb_rg_setup(wb_recovery_guard_t *g, const char *world) {
  memset(g, 0, sizeof(*g));
  g->state = WB_RG_INVALID;
#ifdef _WIN32
  g->lock_handle = INVALID_HANDLE_VALUE;
#else
  g->lock_fd = -1;
#endif
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
  // A failed acquisition never has an effectful runtime; not even READY.
  if (!wb_rg_lock(g)) return 0;
  if (!wb_rg_random_epoch(g->epoch) || wb_rg_refresh(g) == WB_RG_INVALID) {
    wb_rg_release(g);
    return 0;
  }
  return 1;
}

static int wb_rg_claim(wb_recovery_guard_t *g) {
  if (!g->lock_held) return 0;
  int state = wb_rg_refresh(g);
  // Fresh process lifetime is proved by the exclusive OS lock, not by
  // deleting OWNED or trusting a previous PID. PENDING never becomes OWNED.
  if (state == WB_RG_OWNED) return 1;
  if (state != WB_RG_NONE || !wb_rg_write_new(g->path, WB_RG_OWNED_RECORD))
    return 0;
  return wb_rg_refresh(g) == WB_RG_OWNED;
}

static int wb_rg_arm(wb_recovery_guard_t *g, const char *token,
                     const char *digest, const char *owner_key) {
  if (!g->lock_held || !wb_rg_hex64(token) || !wb_rg_hex64(digest) ||
      !wb_rg_hex64(owner_key) || wb_rg_refresh(g) != WB_RG_OWNED) return 0;
  char record[320];
  int n = snprintf(record, sizeof(record), "WEBEEBLOCKS_RECOVERY_V3 %s %s %s\n",
                   token, digest, owner_key);
  if (n < 0 || (size_t)n >= sizeof(record) || !wb_rg_replace(g, record)) {
    g->state = WB_RG_INVALID; // The outcome may be uncertain: no reload.
    return 0;
  }
  return wb_rg_refresh(g) == WB_RG_PENDING &&
         strcmp(g->token, token) == 0 && strcmp(g->digest, digest) == 0 &&
         strcmp(g->owner_key, owner_key) == 0;
}

static int wb_rg_clear(wb_recovery_guard_t *g, const char *token,
                       const char *digest) {
  if (!g->lock_held || !wb_rg_hex64(token) || !wb_rg_hex64(digest) ||
      wb_rg_refresh(g) != WB_RG_PENDING || strcmp(g->token, token) != 0 ||
      strcmp(g->digest, digest) != 0) return 0;
  if (!wb_rg_replace(g, WB_RG_OWNED_RECORD)) {
    g->state = WB_RG_INVALID;
    return 0;
  }
  return wb_rg_refresh(g) == WB_RG_OWNED;
}
#endif
