"""Temporary same-run countercheck for the A3 refusal on Draft #1078."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def git(repo, *args):
    return subprocess.check_output(['git', '-C', repo, *args], text=True).strip()


PROBE = Path('tools/ci/grand_prix_progression_node_probe.js')
RUNNER = Path('tools/ci/run_grand_prix_progression_native.py')
EVALUATOR = Path('tools/grand_prix/evaluator_publisher_v2.py')
LAST_MOVE = "  await backend.move('forward', .10);\n"
HOLD = """  const holdStart = await backend.readElapsedTime();
  let holdEnd = holdStart;
  while (holdEnd - holdStart < .512 && Date.now() < holdDeadline)
    holdEnd = await backend.readElapsedTime();
  assert(holdEnd - holdStart >= .512, 'diagnostic hold not observed');
  console.log(JSON.stringify({event: 'A3_HOLD', holdStart, holdEnd}));
"""


def run_ab(repo, out, assets, image, source, base, head):
    if git(repo, 'rev-parse', 'HEAD') != head:
        raise RuntimeError('A/B candidate checkout does not match the Draft event')
    git(repo, 'fetch', '--no-tags', '--depth=1', 'origin', base)
    if git(repo, 'rev-parse', 'FETCH_HEAD') != base:
        raise RuntimeError('A/B control checkout does not match the Draft event')
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='gp-a3-ab-') as temp:
        folder = Path(temp)
        (folder / 'webots-assets').symlink_to(assets, target_is_directory=True)
        checkouts = [folder / 'A', folder / 'B']
        try:
            for checkout, sha in zip(checkouts, (base, head)):
                git(repo, 'worktree', 'add', '--detach', str(checkout), sha)
            main, candidate = checkouts
            shutil.copyfile(candidate / EVALUATOR, main / EVALUATOR)
            main_runner = main / RUNNER
            env_line = "    env = dict(env, WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE='true')\n"
            runner = main_runner.read_text()
            if runner.count(env_line) != 1:
                raise RuntimeError('A/B trace overlay could not be applied exactly')
            main_runner.write_text(runner.replace(env_line, env_line + (
                "    if activity == 3:\n"
                "        env['WEBEEBLOCKS_GP_A3_TRACE'] = str(out / 'trajectory.csv')\n")))
            harness = main / 'tools/ci/run_grand_prix_native_campaign.sh'
            command = ['bash', str(harness)]
            env = dict(os.environ, ACTIVITY='3', PROTO_SHA=source, WEBOTS_M2_IMAGE=image)
            for index, (checkout, hold) in enumerate(
                    ((main, False), (candidate, False), (candidate, True), (main, True)), 1):
                arm = out / f'{index}-{checkout.name}-{"hold" if hold else "ordinary"}'
                arm.mkdir()
                if hold:
                    probe = checkout / PROBE
                    script = probe.read_text()
                    if script.count(LAST_MOVE) != 1:
                        raise RuntimeError('A/B hold insertion point is ambiguous')
                    probe.write_text(script.replace(LAST_MOVE, LAST_MOVE
                        + '  const holdDeadline = Date.now() + 10000;\n' + HOLD))
                raw = checkout / 'ci-artifacts/grand-prix-u-geometry/route-a3-native'
                if raw.exists():
                    shutil.rmtree(raw)
                sha = git(checkout, 'rev-parse', 'HEAD')
                (arm / 'inputs.txt').write_text('\n'.join((
                    f'commit={sha}', f'image={image}', f'proto={source}',
                    f'evaluator_sha256={hashlib.sha256((checkout / EVALUATOR).read_bytes()).hexdigest()}',
                    f'diagnostic_hold={hold}',
                )) + '\n')
                (arm / 'overlay.patch').write_text(git(checkout, 'diff') + '\n')
                with (arm / 'campaign.log').open('w') as log:
                    result = subprocess.run(command, cwd=checkout, env=env,
                                            stdout=log, stderr=subprocess.STDOUT)
                if raw.is_dir():
                    shutil.copytree(raw, arm, dirs_exist_ok=True)
                (arm / 'status.txt').write_text(f'{result.returncode}\n')
                if not (arm / 'trajectory.csv').is_file():
                    raise RuntimeError(f'A/B {arm.name} produced no native trajectory')
                print(f'A3 A/B {arm.name}: native campaign exit {result.returncode}', flush=True)
        finally:
            for checkout in checkouts:
                if checkout.exists():
                    git(repo, 'worktree', 'remove', '--force', str(checkout))
