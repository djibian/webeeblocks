#!/usr/bin/env python3
"""H6-only atomic native logging patch. Run after termination-observability patch."""
from pathlib import Path
import hashlib, sys

root = Path(sys.argv[1])
expected = {
 'source/patch_webots_h6.py': '2a3338ab073d330e37268fd09502e1a3666e42d5fbd5df7d4fbec21af23f9437',
 'source/run_ab.sh': '589503c875e49c187e27ac0fdd847f0a36af9a26478a1279ceba84ea71dc6fc8',
 'source/analyze_ab.py': 'e9833e8c05b960cc12b24e1991d08fa9e1fb357bbb5fc71b81e7721235ff553c',
}
source = {}
for name, digest in expected.items():
 raw = (root/name).read_bytes()
 if hashlib.sha256(raw).hexdigest() != digest:
  raise SystemExit(f'H6 REFUSED: unexpected source digest {name}')
 source[name] = raw.decode('utf-8')

def once(name, before, after):
 if source[name].count(before) != 1:
  raise SystemExit(f'H6 REFUSED: nonunique anchor in {name}: {before[:70]!r}')
 source[name] = source[name].replace(before, after, 1)

# Atomic single-write dedicated channel; stdout remains intact but is NOT
# parsed as physical data. Each native record carries PID and monotonic ns.
# Deliberately fail hard on overflow, partial write, bad path or newline.
header = r'''#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fcntl.h>
#include <ctime>
#include <unistd.h>
static inline void h6Log(const char *fmt, ...) {
  const char *path = std::getenv("WEBEE_H6_NATIVE_LOG");
  if (!path || path[0] != '/') _exit(94);
  char payload[32768];
  va_list args;
  va_start(args, fmt);
  const int n = std::vsnprintf(payload, sizeof(payload), fmt, args);
  va_end(args);
  if (n <= 0 || static_cast<size_t>(n) >= sizeof(payload)) _exit(95);
  if (payload[n - 1] != '\n' || std::strchr(payload, '\n') != payload + n - 1) _exit(96);
  struct timespec stamp;
  if (clock_gettime(CLOCK_MONOTONIC, &stamp) != 0) _exit(97);
  payload[n - 1] = 0;
  char record[33024];
  const int size = std::snprintf(record, sizeof(record), "%s h6_pid=%ld h6_ns=%lld\n",
                                 payload, static_cast<long>(getpid()),
                                 static_cast<long long>(stamp.tv_sec) * 1000000000LL + stamp.tv_nsec);
  if (size <= 0 || static_cast<size_t>(size) >= sizeof(record)) _exit(98);
  const int fd = open(path, O_WRONLY | O_APPEND | O_CLOEXEC);
  if (fd < 0) _exit(99);
  const ssize_t written = write(fd, record, static_cast<size_t>(size));
  if (written != size || close(fd) != 0) _exit(100);
}
'''
p='source/patch_webots_h6.py'
once(p, '#include <ode/ode.h>\n#include <cstdint>', '#include <ode/ode.h>\n#include <cstdint>\n'+header)
if source[p].count('std::fprintf(stderr,') < 10:
 raise SystemExit('H6 REFUSED: native printf anchors missing')
source[p] = source[p].replace('std::fprintf(stderr,', 'h6Log(')
once(p, '#include "WbPropeller.hpp"\n// BEGIN H6 ISOLATED EXPERIMENT\n#include <cstdio>',
        '#include "WbPropeller.hpp"\n// BEGIN H6 ISOLATED EXPERIMENT\n#include <ode/h6_probe.h>\n#include <cstdio>')

p='source/run_ab.sh'
once(p, '  echo "H6 $MODE exactly once, no retries"',
        '  ( set -o noclobber; : > "$OUT/$MODE/native.log" ) || { echo "H6 REFUSED: native log exists" >&2; exit 2; }\n  echo "H6 $MODE exactly once, no retries"')
once(p, 'WEBEE_H6_MODE="$MODE" WEBEE_H6_CONTROLLER_LOG=',
        'WEBEE_H6_REQUIRE_NATIVE=1 WEBEE_H6_NATIVE_LOG="$OUT/$MODE/native.log" WEBEE_H6_MODE="$MODE" WEBEE_H6_CONTROLLER_LOG=')
once(p, '"$OUT/$MODE/run.log"; then\n    echo "H6 INVALID: $MODE missing armed body/contacts marker"',
        '"$OUT/$MODE/native.log"; then\n    echo "H6 INVALID: $MODE missing armed body/contacts marker"')
once(p, '  if grep -q \'H6 INVALID\' "$OUT/$MODE/run.log"; then',
        '  if grep -q \'H6 INVALID\' "$OUT/$MODE/native.log" "$OUT/$MODE/run.log"; then')
once(p, '    python3 "$ROOT/source/analyze_ab.py" "$OUT" --check-a >"$OUT/A/precheck.json"',
        '    WEBEE_H6_REQUIRE_NATIVE=1 python3 "$ROOT/source/analyze_ab.py" "$OUT" --check-a >"$OUT/A/precheck.json"')
once(p, '  sed -n \'s/^.*H6 event=runtime_mapping detail=//p\' "$OUT/$MODE/run.log" \\',
        '  sed -n \'s/^.*H6 event=runtime_mapping detail=//p\' "$OUT/$MODE/native.log" \\')
once(p, '    > "$OUT/$MODE/runtime_loaded_mappings.txt"',
        '    | sed -E \'s/ h6_pid=[0-9]+ h6_ns=[0-9]+$//\' > "$OUT/$MODE/runtime_loaded_mappings.txt"')
once(p, 'python3 "$ROOT/source/analyze_ab.py" "$OUT" > "$OUT/verdict.json"',
        'WEBEE_H6_REQUIRE_NATIVE=1 python3 "$ROOT/source/analyze_ab.py" "$OUT" > "$OUT/verdict.json"')
once(p, 'sha256sum "$OUT"/{A,B}/run.log "$OUT/verdict.json" > "$OUT/evidence.sha256"',
        'sha256sum "$OUT"/{A,B}/{native.log,run.log,controller.jsonl} "$OUT/verdict.json" > "$OUT/evidence.sha256"')

p='source/analyze_ab.py'
once(p, "    for line in lines:\n        i=line.find('H6 event=')", """    native = path/'native.log'
    if os.environ.get('WEBEE_H6_REQUIRE_NATIVE') == '1' and not native.is_file():
        invalid('missing required dedicated native log')
    native_lines = native.read_text(encoding='utf-8').splitlines() if native.is_file() else lines
    native_pid = set()
    last_ns = -1
    if native.is_file() and (not native_lines or not native.read_bytes().endswith(b'\\n')):
        invalid('native record file missing or truncated')
    for line in native_lines:
        if native.is_file():
            if not line.startswith('H6 event='):
                invalid('non-native or truncated event in dedicated channel')
            if len(line) > 33024 or line.count(' h6_pid=') != 1 or line.count(' h6_ns=') != 1:
                invalid('malformed dedicated native record')
            m = re.search(r' h6_pid=([0-9]+) h6_ns=([0-9]+)$', line)
            if m is None:
                invalid('missing dedicated native event provenance')
            native_pid.add(m.group(1))
            ns = int(m.group(2))
            if ns < last_ns:
                invalid('nonmonotone native event timestamp')
            last_ns = ns
        i=line.find('H6 event=')""")
once(p, "            if 'event' in d: events.append(d)", """            if 'event' in d:
                if native.is_file() and d['event']=='body' and 'step' not in d:
                    invalid('native body event missing physical step')
                events.append(d)
    if native.is_file() and len(native_pid) != 1:
        invalid('native log crosses process identities')""")
once(p, 'historical #671 trajectory', 'historical #637 RESET_TIMEOUT trajectory')
once(p, "'historical_671_verdict'", "'historical_637_verdict'")

for name, data in source.items():
 (root/name).write_text(data)
 print('H6 ATOMIC', name, hashlib.sha256((root/name).read_bytes()).hexdigest(),flush=True)
