#!/usr/bin/env bash
# Same disposable image, loaded application variant only differs between trials.
set -Eeuo pipefail
evidence=$(realpath "${1:?evidence directory}")
experiment=$(cd "$(dirname "$0")" && pwd)
runtime=/usr/local/webots
observer_source=/workspace/signal-observer-source/experiments/qt665-signal-context/observe.c
test -r "$observer_source"
sha256sum "$observer_source" > "$evidence/observer-source.sha256"
cc -std=c11 -Wall -Wextra -Werror -shared -fPIC -O2 \
  "$observer_source" -ldl -o "$evidence/observe.so"
sha256sum "$evidence/observe.so" > "$evidence/observer-binary.sha256"
echo '1445efb2820d151dee40b79ef4128dca7e4a75e02630b49354e557c7e35e66eb  /usr/local/webots/bin/webots-bin' | sha256sum --check
sha256sum "$runtime"/lib/webots/libQt6*.so.6.5.3 > "$evidence/native-qt-before.sha256"
export WEBOTS_HOME="$runtime"
export LIBGL_ALWAYS_SOFTWARE=true
export QT_QPA_PLATFORM=xcb
for variant in baseline selfpipe; do
  cp "$evidence/$variant-webots-bin" "$runtime/bin/webots-bin"
  python3 -u "$experiment/run_variant.py" "$variant" \
    "$evidence/$variant-webots-bin" "$evidence/observe.so" "$evidence"
done
sha256sum "$runtime"/lib/webots/libQt6*.so.6.5.3 > "$evidence/native-qt-after.sha256"
cmp "$evidence/native-qt-before.sha256" "$evidence/native-qt-after.sha256"
python3 - "$evidence" <<'PY'
import json,pathlib,sys
root=pathlib.Path(sys.argv[1])
before=json.loads((root/'baseline/RESULT.json').read_text())
after=json.loads((root/'selfpipe/RESULT.json').read_text())
for key in ('events_sha256','world_sha256'):
    assert before[key]==after[key], (key,before[key],after[key])
assert before['native_result']['ast_sha256']==after['native_result']['ast_sha256']
assert before['allocations_inside_handler'] and not after['allocations_inside_handler']
result={'claim':'compiled actual Webots POSIX signal-context contrast, bounded unavailable negative',
        'baseline':before,'selfpipe':after,
        'limits':['no historical #665 crash reproduced', 'no full native suite or Windows qualification',
                  'no product OCI adoption, Ready HEAD or CI Gate',
                  'development overlay, not execution in the unmodified official OCI environment']}
(root/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n')
print('QT665_MATCHED_COMPILED_CONSUMERS '+json.dumps(result),flush=True)
PY
