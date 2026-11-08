"""Pair two rendered R2025a runs and correlate native spans with Supervisor cycles."""
import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from tools.grand_prix.compare_render_ab import compare
from tools.grand_prix.step_wall_probe import StepWallProbe


def percentile(values, fraction):
    return sorted(values)[math.ceil(fraction * len(values)) - 1]


def attribute(trace, path, start_index):
    cycles = [(a[0], b[0]) for a, b in zip(trace[start_index:], trace[start_index + 1:])]
    begin, end = cycles[0][0], cycles[-1][1]
    sections = {}
    # Fully contained spans support stage p99; WREN overlap attribution also
    # needs draws that straddle either boundary of the Supervisor window.
    boundary_draws = []
    with path.open(encoding='utf-8', newline='') as log:
        if log.readline().strip() != '# webots-render-trace-v1 complete=1':
            raise ValueError('missing or saturated native render trace')
        for row in csv.DictReader(log):
            first, last = int(row['start_ns']), int(row['end_ns'])
            if last < first:
                raise ValueError('negative native span')
            if row['section'] == 'wren_draw' and first < end and last > begin:
                boundary_draws.append((max(first, begin), min(last, end)))
            if first >= begin and last <= end:
                sections.setdefault(row['section'], []).append((first, last))
    for required in ('physics', 'controller_reply', 'qt_controller_ready', 'wren_draw', 'opengl_swap'):
        if not sections.get(required):
            raise ValueError(f'missing {required} spans in the Supervisor clock interval')

    worst = sorted(cycles, key=lambda cycle: cycle[1] - cycle[0], reverse=True)[:math.ceil(len(cycles) / 100)]

    # Measure the union of WREN drawing time intersecting each physical cycle.
    # Native trace spans can overlap or repeat; adding their lengths would
    # double-count the time and invent a majority-of-tail diagnosis.
    draw_intervals = sorted(boundary_draws)

    def draw_overlap(a, b):
        covered_ns, covered_until = 0, a
        for start, end in draw_intervals:
            if start >= b:
                break
            lo, hi = max(a, start, covered_until), min(b, end)
            if hi > lo:
                covered_ns += hi - lo
                covered_until = hi
        return covered_ns

    durations = [b - a for a, b in cycles]
    return {
        'cycles': len(cycles),
        'cycle_p50_ms': percentile(durations, .50) / 1e6,
        'cycle_p95_ms': percentile(durations, .95) / 1e6,
        'cycle_p99_ms': percentile(durations, .99) / 1e6,
        'cycle_max_ms': max(durations) / 1e6,
        'swap_completions_per_wall_second': len(sections['opengl_swap']) * 1e9 / (end - begin),
        'p99_ms_by_stage': {key: percentile([b - a for a, b in spans], .99) / 1e6
                            for key, spans in sorted(sections.items())},
        'draw_overlaps_majority_of_tail_cycles': sum(draw_overlap(a, b) >= (b - a) / 2 for a, b in worst),
        'tail_cycles': len(worst),
    }


def run(home, directory, fixture, fps, settings, bench, scale=None):
    directory.mkdir()
    (directory / 'worlds').mkdir()
    source = (fixture / 'observation.wbt').read_text(encoding='utf-8')
    world = directory / 'worlds/observation.wbt'
    # The transport fixture has no lights. Make the actual rendered scene
    # visible in both arms without changing any collision or sensor input.
    lighting = '''
Background { skyColor [ 0.14 0.18 0.23 ] }
DirectionalLight { direction -0.3 -0.2 -1 intensity 0.8 ambientIntensity 0.4 }
'''
    source, viewpoints = re.subn(r'(?s)Viewpoint \{.*?\}', '''
Viewpoint {
  orientation 0 1 0 1.5707963267948966
  position 0 0 2.2
}'''.strip(), source, count=1)
    if viewpoints != 1:
        raise ValueError('expected one fixture viewpoint')
    world.write_text(source.replace('  basicTimeStep 8', f'  basicTimeStep 8\n  FPS {fps}')
                     .replace('controller "observe"', 'controller "<extern>"') + lighting, encoding='utf-8')
    observer = directory / 'observe.py'
    shutil.copyfile(fixture / 'probe.py', observer)
    trace = directory / 'trace.json'
    performance = directory / 'performance.log'
    env = {k: v for k, v in os.environ.items()
           if k.lower() not in {'http_proxy', 'https_proxy', 'all_proxy', 'webots_home'}}
    env.update(WEEBEE_FRAME_MODE='compact', WEEBEE_FRAME_STEPS=str(settings.steps),
               WEEBEE_FRAME_RESULT=str(trace), WEBOTS_RENDER_TRACE='1',
               WEBOTS_EXPERIMENT_MAIN_RENDER_SCALE=str(scale or 100))
    executable, _, _ = bench.distribution(home)
    command = [str(executable), '--batch', '--stdout', '--stderr', '--mode=realtime', '--extern-urls',
               f'--port={settings.tcp_port}', f'--log-performance={performance},0', str(world)]
    with (directory / 'webots.log').open('wb') as log:
        bench.run_external(command, home, directory, observer, env, settings, log)

    result = json.loads(trace.read_text(encoding='utf-8'))
    timings = result['timings_ns']
    if (result['mode'] != 'compact' or result['steps'] != settings.steps or
            len(timings) != settings.steps or len(result['observations']) != settings.steps):
        raise ValueError('incomplete Supervisor trace')
    with (directory / 'step-wall.log').open('w', encoding='utf-8') as log:
        probe = StepWallProbe('native-render-fixture', lambda line: print(line, file=log))
        for index, timing in enumerate(timings):
            probe.record((result['start_sim_ms'] + 8 * (index + 1)) / 1000, *timing)
        probe.flush()
    details = attribute(timings, directory / 'performance.log.render.csv', 125)
    details['speed_x'] = 8_000_000 * details['cycles'] / (timings[-1][0] - timings[125][0])
    if scale is not None:
        log_text = (directory / 'webots.log').read_text(encoding='utf-8', errors='replace')
        sizes = re.findall(r'WEBOTS_MAIN_FRAMEBUFFER render=(\d+)x(\d+) screen=(\d+)x(\d+)', log_text)
        if not sizes:
            raise ValueError('missing measured framebuffer dimensions')
        rw, rh, sw, sh = map(int, sizes[-1])
        if (rw, rh) != (max(1, sw * scale // 100), max(1, sh * scale // 100)):
            raise ValueError('native framebuffer does not match experimental scale')
        details['render_size'] = [rw, rh]
        details['screen_size'] = [sw, sh]
        details['scale'] = scale
    details['world_sha256'] = hashlib.sha256(world.read_bytes()).hexdigest()
    return result, details


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--patched', type=Path, required=True)
    parser.add_argument('--frame-tools', type=Path, required=True, help='native_frame directory from #922')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--source-sha', required=True)
    parser.add_argument('--host-id', required=True)
    parser.add_argument('--display-mode', required=True)
    parser.add_argument('--tcp-port', type=int, default=1352)
    parser.add_argument('--timeout', type=int, default=45)
    parser.add_argument('--steps', type=int, default=500)
    parser.add_argument('--scale-ab', action='store_true', help='compare 100% and 50% draw sizes at the same 60-FPS cap')
    args = parser.parse_args()
    if args.steps < 250 or args.steps % 125:
        parser.error('use a multiple of 125 steps with one warm-up window and at least one measured window')
    home, fixture, output = (path.resolve() for path in (args.patched, args.frame_tools, args.output))
    sys.path.insert(0, str(fixture))
    import bench

    output.mkdir(parents=True, exist_ok=False)
    identity = bench.fingerprint(home)
    _, binary, _ = bench.distribution(home)
    doc = {
        'schema': 1, 'source_sha': args.source_sha, 'webots_executable_sha256': identity[binary.name],
        'program_sha256': hashlib.sha256((fixture / 'probe.py').read_bytes()).hexdigest(),
        'course': 'native-render-fixture', 'host_id': args.host_id, 'display_mode': args.display_mode,
        'render_fps': {'A': 60, 'B': 60 if args.scale_ab else 25}, 'trials': [],
    }
    scales = {'A': 100, 'B': 50} if args.scale_ab else {'A': None, 'B': None}
    if args.scale_ab:
        doc['framebuffer_scale'] = scales
    attribution = []
    reference = None
    settings = SimpleNamespace(steps=args.steps, tcp_port=args.tcp_port, timeout=args.timeout)
    for pair, order in enumerate(('AB', 'BA', 'AB'), 1):
        for arm in order:
            label = f'{pair}-{arm}'
            result, spans = run(home, output / label, fixture, doc['render_fps'][arm], settings, bench, scales[arm])
            if reference is None:
                reference = result
                origin = result['start_sim_ms']
                doc['phase_ms'] = [origin + 8 * 126, origin + 8 * (args.steps + 1)]
            else:
                bench.compare(reference, result, label)
            doc['trials'].append({'arm': arm, 'log': f'{label}/step-wall.log'})
            attribution.append({'pair': pair, 'arm': arm, **spans})
    manifest = output / 'manifest.json'
    manifest.write_text(json.dumps(doc, indent=2) + '\n', encoding='utf-8')
    if args.scale_ab:
        if len({(tuple(entry['screen_size']), entry['world_sha256']) for entry in attribution}) != 1:
            raise ValueError('the actual Webots viewport or world changed between paired runs')
        # The integrated cap comparator deliberately rejects equal caps.
        # Scale trials instead retain every native step-wall log and the same
        # actual cycle boundaries used for the stage attribution.
        comparison = doc
    else:
        comparison = compare(manifest)
    summary = {'engine': identity, 'comparison': comparison, 'native_spans': attribution}
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
