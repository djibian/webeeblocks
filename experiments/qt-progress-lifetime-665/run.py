#!/usr/bin/env python3
"""Bounded lifetime intervention; never an oracle for a Webots mission."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess

p = argparse.ArgumentParser()
p.add_argument('--webots-home', type=Path, required=True)
p.add_argument('--platform-plugins', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
w = a.webots_home.resolve()
out = a.out.resolve()
out.mkdir(parents=True, exist_ok=False)
source = Path(__file__).with_name('lifetime.cpp').resolve()
binary = out / 'lifetime'
cmd = ['g++', '-std=c++17', '-g', '-O0', '-fPIC', '-rdynamic', str(source), '-o', str(binary)]
for module in ['QtCore', 'QtGui', 'QtWidgets']:
    cmd += ['-I' + str(w / 'include/qt' / module)]
cmd += ['-L' + str(w / 'lib/webots'), '-Wl,-rpath,' + str(w / 'lib/webots'), '-lQt6Widgets', '-lQt6Core']
r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
(out / 'build.stdout').write_text(r.stdout)
(out / 'build.stderr').write_text(r.stderr)
r.check_returncode()
env = dict(os.environ, QT_QPA_PLATFORM='offscreen',
           QT_QPA_PLATFORM_PLUGIN_PATH=str(a.platform_plugins.resolve()),
           LD_LIBRARY_PATH=str(w / 'lib/webots'))
results = []
for mode in ['modal-direct', 'modal-deferred', 'nonmodal-direct']:
    r = subprocess.run([str(binary), mode], env=env, capture_output=True, text=True, timeout=15)
    (out / (mode + '.stdout')).write_text(r.stdout)
    (out / (mode + '.stderr')).write_text(r.stderr)
    results.append({'mode': mode, 'returncode': r.returncode})
    r.check_returncode()
    events = [line.split()[1] for line in r.stdout.splitlines() if line.startswith('EVENT ')]
    destroyed = events.index('BAR_DESTROYED')
    returned = events.index('SET_VALUE_RETURN')
    assert (destroyed < returned) == (mode == 'modal-direct'), (mode, events)
    if mode != 'nonmodal-direct':
        assert 'QProgressDialog8setValueEi' in r.stderr, (mode, r.stderr)
libraries = [w / 'lib/webots' / ('libQt6' + m + '.so.6.5.3') for m in ['Widgets', 'Core', 'Gui']]
libraries += [a.platform_plugins.resolve() / 'libqoffscreen.so']
provenance = {'platform': platform.platform(), 'compile': cmd,
              'qpa': env['QT_QPA_PLATFORM'], 'plugin_path': env['QT_QPA_PLATFORM_PLUGIN_PATH'],
              'libraries': {str(f): {'bytes': f.stat().st_size, 'sha256': hashlib.sha256(f.read_bytes()).hexdigest()} for f in libraries},
              'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest()}
(out / 'provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
(out / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
(out / 'linked-libraries.txt').write_text(subprocess.check_output(['ldd', str(binary)], text=True))
print(json.dumps(results))
