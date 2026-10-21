#!/usr/bin/env python3
"""Inspect existing archive bytes only; never launches Webots or a controller."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tarfile
import zipfile

HEAD655 = '6c0a58daecd86b4ad7fa6f4d768f8491603eb3f7'
ARTIFACTS = {
    12193597782: 'f017e3d1f7c84e420177100986de9e21a013c0e6c364eb8634ccbd1627e28b86',
    12197204926: 'c781622fe2fc68831114d0594ea792d38b51febd23b2c98d6a13fe21387feb74',
    12329503523: 'a08591122f676fa76d64b9cbb32ddc898867ec99a03513fc9e6d902e38fb6ccf',
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def check_names(names):
    if len(names) != len(set(names)):
        raise ValueError('duplicate archive member')
    for name in names:
        path = PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts:
            raise ValueError('unsafe archive member')


def inspect(files):
    rows = []
    for name, world in files.items():
        if not name.endswith('/world.wbt'):
            continue
        parent = name.rsplit('/', 1)[0] + '/'
        log = files.get(parent + 'webots.log', b'').decode(errors='replace')
        manifest = json.loads(files[parent + 'sha256.json'])
        rows.append({
            'case': parent[:-1], 'world_sha256': sha(world), 'world_bytes': len(world),
            'viewpoints': [s.decode() for s in re.findall(rb'Viewpoint\s*\{[^}]*\}', world)],
            'ready_count_webots_log': log.count('WEBEEBLOCKS_RUNTIME_V2 READY'),
            'segfault_log_lines': [s for s in log.splitlines() if 'Segmentation fault' in s],
            'controller_start_lines': [s for s in log.splitlines() if 'Starting controller' in s],
            'manifest_missing': [n for n in manifest if parent + n not in files],
            'manifest_mismatches': [n for n, h in manifest.items() if parent + n in files and sha(files[parent + n]) != h],
            'unlisted_members': [n[len(parent):] for n in files if n.startswith(parent)
                                 and n != parent + 'sha256.json' and n[len(parent):] not in manifest],
        })
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate655', required=True, type=Path)
    parser.add_argument('--artifact-dir', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    candidate = args.candidate655.resolve()
    if subprocess.check_output(['git', '-C', str(candidate), 'rev-parse', 'HEAD'], text=True).strip() != HEAD655:
        raise ValueError('wrong #655 checkout')
    # Refuse local mutations of source or archived evidence in this audit input.
    if subprocess.check_output(['git', '-C', str(candidate), 'status', '--porcelain', '--untracked-files=no'], text=True):
        raise ValueError('modified #655 checkout')
    sys.path.insert(0, str(candidate))
    from tools.grand_prix.layout_u import generate, world_text
    evidence = candidate / 'experiments/grand-prix-no-wall/evidence'
    index = json.loads((evidence / 'archives.json').read_text())
    report = {'head655': HEAD655, 'archives655': [], 'artifacts646': []}
    native_worlds = {}
    for item in index:
        archive = evidence / item['name']
        data = archive.read_bytes()
        if len(data) != item['size'] or sha(data) != item['sha256']:
            raise ValueError('archive size/hash mismatch: ' + item['name'])
        with tarfile.open(archive) as tar:
            members = [m for m in tar.getmembers() if m.isfile()]
            check_names([m.name for m in members])
            files = {m.name: tar.extractfile(m).read() for m in members}
        cases = inspect(files)
        manifest_checks = []
        for name, contents in files.items():
            if PurePosixPath(name).name != 'sha256.json':
                continue
            parent = name.rsplit('/', 1)[0] + '/' if '/' in name else ''
            manifest = json.loads(contents)
            missing = [n for n in manifest if parent + n not in files]
            bad = [n for n, h in manifest.items() if parent + n in files and sha(files[parent + n]) != h]
            if (missing and cases) or bad != item['internal_manifest_mismatches']:
                raise ValueError('unexpected historical manifest discrepancy')
            manifest_checks.append({'member': name, 'missing': missing, 'mismatches': bad})
        for case in cases:
            parent = case['case'] + '/'
            layout = json.loads(files[parent + 'layout.json'])
            expected = world_text(generate(layout['seed'], 2), controller='<extern>', window='<none>', evaluator=True)
            expected = expected.replace('controller "grand_prix_u_evaluator"', 'controller "<extern>"')
            expected = expected.replace('https://raw.githubusercontent.com/cyberbotics/webots/R2025a/', 'webots://').encode()
            case['byte_equal_to_exact_generator_tcp_world'] = files[parent + 'world.wbt'] == expected
            if not case['byte_equal_to_exact_generator_tcp_world'] or case['manifest_missing']:
                raise ValueError('world/manifest discrepancy')
            if case['manifest_mismatches'] != item['internal_manifest_mismatches']:
                raise ValueError('unexpected historical mismatch')
        report['archives655'].append({'name': item['name'], 'sha256': sha(data), 'size': len(data),
                                      'members': list(files), 'cases': cases,
                                      'manifest_checks': manifest_checks,
                                      'world_absent': not bool(cases)})
    for aid, expected in ARTIFACTS.items():
        archive = args.artifact_dir / ('artifact-%d.zip' % aid)
        data = archive.read_bytes()
        if sha(data) != expected:
            raise ValueError('wrong GitHub ZIP: ' + str(aid))
        with zipfile.ZipFile(archive) as z:
            names = [n for n in z.namelist() if not n.endswith('/')]
            check_names(names)
            files = {n: z.read(n) for n in names}
        cases = inspect(files)
        if any(c['manifest_missing'] or c['manifest_mismatches'] for c in cases):
            raise ValueError('GitHub manifest mismatch')
        for name, content in files.items():
            if name.endswith('/world.wbt'):
                native_worlds[(aid, name)] = content
        report['artifacts646'].append({'id': aid, 'sha256': sha(data), 'size': len(data),
                                      'cases': cases, 'members': list(files)})
    crash = next(b for (aid, n), b in native_worlds.items() if aid == 12193597782 and 's1-witness-' in n)
    success = next(b for (aid, n), b in native_worlds.items() if aid == 12197204926 and 's1-witness-' in n)
    static = next(b for (aid, n), b in native_worlds.items() if aid == 12329503523 and 'camera-static-' in n)
    tracking = next(b for (aid, n), b in native_worlds.items() if aid == 12329503523 and 'camera-tracking-' in n)
    report['comparisons646'] = {
        'crash_and_success_world_bytes_equal': crash == success,
        'tracking_equals_static_after_exact_follow_field_removal': tracking.replace(
            b'follow "Crazyflie WebeeBlocks" followType "Tracking Shot" followSmoothness 0.20 ', b'') == static,
    }
    if not all(report['comparisons646'].values()):
        raise ValueError('historical byte comparison contradicted')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print('ARCHIVE_AUDIT_OK: 12 #655 archives, 3 #646 ZIPs; historical partial/refused cases preserved')


if __name__ == '__main__':
    main()
