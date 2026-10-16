"""Falsify the assembled Windows project's bytes and entry-point closure."""
import argparse
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.grand_prix.package_windows_u import (compose, digest, local_world,
                                               replace_once, verified_files)


def verify(package):
    verified_files(package)
    inputs = json.loads((package / 'COMPOSITION.json').read_text())
    for name in ('controller', 'evaluator'):
        for relative, expected in inputs[name]['files'].items():
            if relative in ('SOURCE_SHA', 'README.md', 'THIRD_PARTY_NOTICES.md', 'BUILD_INPUTS.json'):
                continue
            assert digest(package / relative) == expected, relative
    windows = list((package / 'plugins/robot_windows').glob('blockly_v2_[0-9a-f]*'))
    assert len(windows) == 1
    window = windows[0]
    html = (window / (window.name + '.html')).read_text()
    for relative in re.findall(r'(?:src|href)="([^"]+)"', html):
        name, query = relative.split('?wb=')
        path = (window / name).resolve()
        assert path.is_relative_to(package.resolve()) and path.is_file()
        assert digest(path)[:16] == query
    setup = (window / 'setup.js').read_text()
    expected = (ROOT / 'plugins/robot_windows/grand_prix_u/setup.js').read_text()
    assert setup == replace_once(expected, "media:'../blockly_v2/vendor/media/'", "media:'vendor/media/'")
    for seed in (0, 1, 4):
        world = package / f'worlds/grand_prix_u_seed{seed}.wbt'
        assert world.read_text() == local_world(seed, window.name)
        assert (world.parent / ('.' + world.stem + '.wbproj')).read_bytes() == (ROOT / 'worlds/.crazyflie_runtime_v2.wbproj').read_bytes()
        assert f'WEBEEBLOCKS_GP_SEED={seed}' in (package / f'Lancer-Grand-Prix-{seed + 1}.cmd').read_text()
    starter = package / 'Activites/08-grand-prix-u.wbb'
    assert starter.read_bytes() == (ROOT / 'activities/grand-prix/02-grand-prix-u.wbb').read_bytes()
    assert json.loads(starter.read_text())['activity']['id'] == 'progression-grand-prix-u-v1'
    assert len(list((package / 'Activites').glob('*.wbb'))) == 1
    launcher = (package / 'Launch-WebeeBlocks.ps1').read_text(encoding='utf-8-sig')
    assert 'WEBEEBLOCKS_GP_PYTHON_DIR' in launcher
    assert "if ($seed -notin @('0', '1', '4'))" in launcher
    for file in ('controllers/grand_prix_u_flight/grand_prix_u_flight.exe',
                 'controllers/grand_prix_u_flight/runtime.ini',
                 'controllers/grand_prix_u_evaluator/grand_prix_u_evaluator.py',
                 'controllers/grand_prix_u_evaluator/evaluator_impl.py',
                 'controllers/grand_prix_u_evaluator/runtime.ini',
                 'runtime/python/webeeblocks-gp-python.exe', 'runtime/python/python312._pth',
                 'tools/grand_prix/layout_u.py', 'tools/grand_prix/oracle_u.py',
                 'tools/grand_prix/simulation_time.py'):
        assert (package / file).is_file(), file
    assert (package / 'runtime/python/python312._pth').read_text() == 'python312.zip\n.\n'
    assert (package / 'controllers/grand_prix_u_evaluator/runtime.ini').read_text() == (
        '[python]\nCOMMAND = $(WEBEEBLOCKS_GP_PYTHON_DIR)/webeeblocks-gp-python.exe\nOPTIONS = -I\n')
    assert not (package / 'controllers/crazyflie_runtime_v2').exists()
    print('PASS assembled Windows U project: local worlds/configurations, complete HTML/media, exact profile/starter, native/evaluator closure and source manifests')


class ManifestTests(unittest.TestCase):
    def test_corruption_escape_duplicate_and_unlisted_file_refuse(self):
        for mutation in ('corrupt', 'escape', 'duplicate', 'unlisted'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp) / 'input'
                root.mkdir()
                file = root / 'data'
                file.write_bytes(b'good')
                entry = digest(file) + '  data\n'
                (root / 'MANIFEST.sha256').write_text(entry)
                verified_files(root)
                if mutation == 'corrupt': file.write_bytes(b'bad')
                if mutation == 'escape': (root / 'MANIFEST.sha256').write_text(digest(file) + '  ../input/data\n' + entry)
                if mutation == 'duplicate': (root / 'MANIFEST.sha256').write_text(entry * 2)
                if mutation == 'unlisted': (root / 'extra').write_text('unexpected')
                with self.assertRaises(ValueError): verified_files(root)

    def test_mixed_shas_refuse_before_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            sources = []
            for name in ('classroom', 'controller', 'evaluator'):
                source = base / name
                source.mkdir()
                stamp = source / 'SOURCE_SHA'
                stamp.write_text('a' * 40 + '\n')
                (source / 'MANIFEST.sha256').write_text(digest(stamp) + '  SOURCE_SHA\n')
                sources.append(source)
            with self.assertRaisesRegex(ValueError, 'Mixed source SHAs'):
                compose(*sources, base / 'output', 'b' * 40)
            self.assertFalse((base / 'output').exists())


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--package', type=Path)
    args = parser.parse_args()
    if args.package: verify(args.package)
    else: unittest.main(argv=[sys.argv[0]])
