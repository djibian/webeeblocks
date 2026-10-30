#!/usr/bin/env python3
"""Fail-closed observational H6 Supervisor I/O repair; physics unchanged."""
from pathlib import Path
import hashlib
import sys

root = Path(sys.argv[1])
changes = {
    'controllers/h6_supervisor/h6_supervisor.py': [
        ("def sample(label):\n", """def emit(line):
    # Webots stdout/stderr multiplexing can splice C++ and Python output
    # and may lose final controller messages during simulationQuit(0).
    # Keep the original merged native log and separately persist the real
    # Supervisor output before it requests process termination.
    path = os.environ.get('WEBEE_H6_CONTROLLER_LOG')
    if not path:
        raise RuntimeError('H6 INVALID: missing independent Supervisor log path')
    with open(path, 'a', encoding='utf-8') as output:
        output.write(line + '\\n')
        output.flush()
        os.fsync(output.fileno())
    print(line, flush=True)


def sample(label):
"""),
        ('    print("H6_CONTROLLER " + json.dumps(d, sort_keys=True), flush=True)\n', '    emit("H6_CONTROLLER " + json.dumps(d, sort_keys=True))\n'),
        ("print(json.dumps({'kind':'H6_HEADER'", "emit(json.dumps({'kind':'H6_HEADER'"),
        ("                  'source':'c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b'}),flush=True)", "                  'source':'c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b'}))"),
        ("print('H6_CONTROLLER native Supervisor RESET requested',flush=True)", "emit('H6_CONTROLLER native Supervisor RESET requested')"),
        ("print('H6_CONTROLLER end_of_one_shot_experiment',flush=True)", "emit('H6_CONTROLLER end_of_one_shot_experiment')"),
    ],
    'source/run_ab.sh': [
        ('WEBEE_H6_MODE="$MODE" timeout --signal=TERM 70s', 'WEBEE_H6_MODE="$MODE" WEBEE_H6_CONTROLLER_LOG="$OUT/$MODE/controller.jsonl" timeout --signal=TERM 70s'),
        ('  if ! grep -q \'H6_CONTROLLER end_of_one_shot_experiment\' "$OUT/$MODE/run.log"; then', '  if ! grep -Fxq \'H6_CONTROLLER end_of_one_shot_experiment\' "$OUT/$MODE/controller.jsonl"; then'),
    ],
    'source/analyze_ab.py': [
        ('    controller=[]\n    for line in lines:\n', """    # Independent Supervisor records, written and fsynced before quit.
    # C++/Python stream remains preserved byte-for-byte in run.log.
    sidecar = path/'controller.jsonl'
    if not sidecar.is_file():
        invalid('missing independently persisted Supervisor log')
    controller = []
    for line in sidecar.read_text().splitlines():
        if line.startswith('H6_CONTROLLER {'):
            try: controller.append(json.loads(line[len('H6_CONTROLLER '):]))
            except (ValueError, TypeError): invalid('malformed independent Supervisor record')
        elif line.startswith('H6_CONTROLLER ') or line.startswith('{"kind": "H6_HEADER"'):
            pass
        else:
            invalid('unexpected independent Supervisor record')
    for line in lines:
"""),
        ("        i=line.find('H6_CONTROLLER {')\n        if i>=0:\n            try: controller.append(json.loads(line[i+len('H6_CONTROLLER '):]))\n            except (ValueError, TypeError): invalid('malformed Supervisor record')\n", ''),
        ("    if not any('H6_CONTROLLER end_of_one_shot_experiment' in line for line in lines):", "    if not any(line == 'H6_CONTROLLER end_of_one_shot_experiment' for line in (path/'controller.jsonl').read_text().splitlines()):"),
        ("    for key in ['contacts_prepared_by_ode']+[f'after_reset_step_{n}' for n in range(1,7)]:\n", "    if len(ctl) != 7 or len({x.get('label') for x in ctl}) != 7:\n        invalid('expected exactly seven distinct Supervisor observations')\n    for key in ['contacts_prepared_by_ode']+[f'after_reset_step_{n}' for n in range(1,7)]:\n"),
    ],
}
expected = {
    'controllers/h6_supervisor/h6_supervisor.py': 'd73c69ae2c0d1798c86fa38fc51583e4122e4dc0cc2968908441771b0c988abe',
    'source/run_ab.sh': '3f477d8753e4b3375a4f2bcd5fe28eb141311304ad99bbf63b1571dd1101c30e',
    'source/analyze_ab.py': 'fce0ca92ad8e16da99dec100d5c015b9ec1bbe448502e6c4aa71bbaf01bcc4ac',
}
# Validate every source and every unique anchor before modifying any file.
replacements = {}
for name, rules in changes.items():
    p = root / name
    raw = p.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if actual != expected[name]:
        raise SystemExit(f'H6 REFUSED: unrecognized {name} sha256={actual}')
    data = raw.decode('utf-8')
    for old, new in rules:
        if data.count(old) != 1:
            raise SystemExit(f'H6 REFUSED: nonunique patch anchor in {name}: {old[:65]!r}')
        data = data.replace(old, new, 1)
    replacements[name] = data
for name, data in replacements.items():
    p = root / name
    p.write_text(data)
    print('H6 OBSERVABILITY PATCH', name, expected[name], hashlib.sha256(p.read_bytes()).hexdigest(), flush=True)
