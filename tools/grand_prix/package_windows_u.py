"""Compose the reviewed Windows supports into an isolated installable U project.

Build-time Python only. The classroom project/catalogue is never modified.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.grand_prix.layout_u import generate, world_text

NAME = 'WebeeBlocks-Grand-Prix-Windows-R2025a'
SEEDS = (0, 1, 4)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verified_files(root):
    root = root.resolve(strict=True)
    entries = {}
    for line in (root / 'MANIFEST.sha256').read_text(encoding='utf-8-sig').splitlines():
        match = re.fullmatch(r'([0-9a-f]{64})  (.+)', line)
        if not match:
            raise ValueError('Malformed input manifest')
        expected, name = match.groups()
        path = root / name
        if (name in entries or '\\' in name or path.is_symlink() or
                not path.resolve().is_relative_to(root) or not path.is_file() or
                digest(path) != expected):
            raise ValueError(f'Invalid input file: {name}')
        entries[name] = expected
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    if actual != set(entries) | {'MANIFEST.sha256'}:
        raise ValueError('Input file inventory differs from manifest')
    return entries


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f'Packaging anchor changed: {old}')
    return text.replace(old, new)


def local_world(seed, window):
    layout = generate(seed)
    text = world_text(layout, controller='grand_prix_u_flight', window=window,
                      evaluator=True)
    prefix = 'https://raw.githubusercontent.com/cyberbotics/webots/R2025a/projects/'
    text = replace_once(text, f'EXTERNPROTO "{prefix}robots/bitcraze/crazyflie/protos/Crazyflie.proto"',
                        'EXTERNPROTO "../protos/Crazyflie.proto"')
    for name, path in (('Floor', 'objects/floors/protos/'),
                       ('TexturedBackground', 'objects/backgrounds/protos/'),
                       ('TexturedBackgroundLight', 'objects/backgrounds/protos/')):
        text = replace_once(text, f'EXTERNPROTO "{prefix}{path}{name}.proto"\n', '')
    text = replace_once(text, 'TexturedBackground { }', 'Background { skyColor [ 0.75 0.83 0.92 ] }')
    text = replace_once(text, 'TexturedBackgroundLight { }', 'DirectionalLight { direction -0.4 -0.5 -1 intensity 1.5 }')
    size = layout.side + 2.5
    # Native R2025a Floor resolves to a locked Solid whose collision is a
    # Plane at z=0 (not a 5-cm Box). Preserve that exact physics geometry
    # offline; the visual surface is a separate IndexedFaceSet, as upstream.
    # The former box substituted by packaging, not by the mission generator,
    # created a distinct Windows landing/contact experiment.
    half = size / 2
    floor = '\n'.join((
        f'Solid {{ translation {layout.side/2} {layout.side/2} 0',
        '  name "floor"',
        '  locked TRUE',
        '  children [',
        '    Shape {',
        '      appearance PBRAppearance { baseColor 0.65 0.68 0.72 roughness 0.8 }',
        '      geometry IndexedFaceSet {',
        f'        coord Coordinate {{ point [ {-half} {-half} 0 {half} {-half} 0 {-half} {half} 0 {half} {half} 0 ] }}',
        '        coordIndex [ 2 0 1 3 -1 ]',
        '      }',
        '    }',
        '  ]',
        f'  boundingObject Plane {{ size {size} {size} }}',
        '}',
    ))
    text = replace_once(text, f'Floor {{ translation {layout.side/2} {layout.side/2} 0 size {size} {size} }}', floor)
    if re.search(r'"(?:https?|webots)://', text):
        raise ValueError('Nonlocal world resource')
    return text


def compose(classroom, controller, evaluator, output, sha):
    if not re.fullmatch('[0-9a-f]{40}', sha):
        raise ValueError('Exact source SHA required')
    inputs = {}
    for key, source in [('classroom', classroom), ('controller', controller), ('evaluator', evaluator)]:
        entries = verified_files(source)
        inputs[key] = {'manifest_sha256': digest(source / 'MANIFEST.sha256'), 'files': entries}
        if key != 'classroom' and (source / 'SOURCE_SHA').read_text(encoding='utf-8').strip() != sha:
            raise ValueError('Mixed source SHAs')
    if output.exists():
        raise ValueError('Use a fresh output directory')
    shutil.copytree(classroom, output)
    # Keep the full inherited dependency closure, but remove obsolete entry points.
    for name in ('controllers', 'worlds', 'Activites'):
        shutil.rmtree(output / name)
    (output / 'WINDOWS-ACCEPTANCE.md').unlink()
    for source in (controller, evaluator):
        for name in inputs['controller' if source == controller else 'evaluator']['files']:
            if name in ('SOURCE_SHA', 'README.md', 'THIRD_PARTY_NOTICES.md', 'BUILD_INPUTS.json'):
                continue
            target = output / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / name, target)
    windows = output / 'plugins/robot_windows'
    old = list(windows.glob('blockly_v2_[0-9a-f]*'))
    if len(old) != 1:
        raise ValueError('Exactly one classroom Robot Window required')
    staging = windows / 'u-staging'
    old[0].rename(staging)
    (staging / f'{old[0].name}.html').unlink()
    html = (ROOT / 'plugins/robot_windows/grand_prix_u/grand_prix_u.html').read_text(encoding='utf-8')
    html = html.replace('../blockly_v2/', '')
    setup = (ROOT / 'plugins/robot_windows/grand_prix_u/setup.js').read_text(encoding='utf-8')
    setup = replace_once(setup, "media:'../blockly_v2/vendor/media/'", "media:'vendor/media/'")
    (staging / 'setup.js').write_text(setup, encoding='utf-8')
    # Hash all shared assets as well as setup and the new top-level HTML.
    identity = html + '\n' + '\n'.join(
        f'{p.relative_to(windows).as_posix()} {digest(p)}'
        for p in sorted(windows.rglob('*')) if p.is_file())
    window = 'blockly_v2_' + hashlib.sha256(identity.encode()).hexdigest()[:16]
    window_root = windows / window
    staging.rename(window_root)
    def fingerprint(match):
        name = re.split('[?#]', match[2], maxsplit=1)[0]
        path = (window_root / name).resolve()
        if not path.is_relative_to(output.resolve()) or not path.is_file():
            raise ValueError(f'Unpackaged HTML dependency: {name}')
        return match[1] + name + '?wb=' + digest(path)[:16] + match[3]
    html = re.sub(r'((?:src|href)=")([^"]+)(")', fingerprint, html)
    (window_root / f'{window}.html').write_text(html, encoding='utf-8')
    worlds = output / 'worlds'
    worlds.mkdir()
    for seed in SEEDS:
        name = f'grand_prix_u_seed{seed}'
        (worlds / f'{name}.wbt').write_text(local_world(seed, window), encoding='utf-8')
        shutil.copyfile(ROOT / 'worlds/.crazyflie_runtime_v2.wbproj', worlds / f'.{name}.wbproj')
        # Opaque public configuration names do not reveal the gate count to Blockly.
        (output / f'Lancer-Grand-Prix-{seed + 1}.cmd').write_text(
            '@echo off\nsetlocal EnableExtensions DisableDelayedExpansion\n'
            f'set "WEBEEBLOCKS_GP_SEED={seed}"\ncall "%~dp0Launch-WebeeBlocks.cmd"\nexit /b %ERRORLEVEL%\n',
            encoding='utf-8')
    launcher = output / 'Launch-WebeeBlocks.ps1'
    text = launcher.read_text(encoding='utf-8-sig')
    text = replace_once(text, "$world = Join-Path $PSScriptRoot 'worlds\\crazyflie_runtime_v2.wbt'",
        "$seed = if ($env:WEBEEBLOCKS_GP_SEED) { $env:WEBEEBLOCKS_GP_SEED } else { '4' }\n"
        "if ($seed -notin @('0', '1', '4')) { throw 'Configuration Grand Prix inconnue.' }\n"
        "$env:WEBEEBLOCKS_GP_PYTHON_DIR = Join-Path $PSScriptRoot 'runtime\\python'\n"
        "$world = Join-Path $PSScriptRoot (\"worlds\\grand_prix_u_seed$seed.wbt\")")
    launcher.write_text(text, encoding='utf-8-sig')
    (output / 'Activites').mkdir()
    shutil.copyfile(ROOT / 'activities/grand-prix/02-grand-prix-u.wbb', output / 'Activites/08-grand-prix-u.wbb')
    # Teacher-only runnable witness: do not replace the empty pupil starter.
    demonstration = output / 'Exemples/Grand-Prix-demo-enseignant.wbb'
    demonstration.parent.mkdir()
    subprocess.run(['node', str(ROOT / 'tools/grand_prix/witness_workspace_u.js'),
                    str(demonstration)], cwd=ROOT, check=True)
    if not demonstration.is_file() or demonstration.stat().st_size == 0:
        raise ValueError('Teacher Grand Prix witness was not generated')
    shutil.copyfile(ROOT / 'docs/GRAND_PRIX_WINDOWS_PROJECT.md', output / 'README-WINDOWS.md')
    (output / 'SOURCE_SHA').write_text(sha + '\n', encoding='utf-8')
    (output / 'COMPOSITION.json').write_text(json.dumps(inputs, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    manifest = '\n'.join(f'{digest(p)}  {p.relative_to(output).as_posix()}'
                         for p in sorted(output.rglob('*')) if p.is_file() and p.name != 'MANIFEST.sha256')
    (output / 'MANIFEST.sha256').write_text(manifest + '\n', encoding='utf-8')
    verified_files(output)
    return window


def main():
    parser = argparse.ArgumentParser()
    for name in ('classroom', 'controller', 'evaluator', 'output'):
        parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args()
    sha = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
    compose(args.classroom, args.controller, args.evaluator, args.output, sha)
    archive = args.output.with_suffix('.zip')
    if archive.exists():
        raise ValueError('Archive already exists')
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for path in sorted(args.output.rglob('*')):
            if path.is_file():
                zip_file.write(path, path.relative_to(args.output))
    print('GP_U_INSTALLED_PACKAGE', archive, digest(archive))


if __name__ == '__main__':
    main()
