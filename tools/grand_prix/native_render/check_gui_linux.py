"""Verify native screenshot and picking with Webots visible on a Linux X display."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from types import SimpleNamespace

SIZE = re.compile(r'WEBOTS_MAIN_FRAMEBUFFER render=(\d+)x(\d+) screen=(\d+)x(\d+)')

WORLD = '''#VRML_SIM R2025a utf8
WorldInfo { basicTimeStep 8 FPS 60 }
Viewpoint {
  orientation 0 1 0 1.5707963267948966
  position 0 0 2.2
}
Background { skyColor [ 0.14 0.18 0.23 ] }
DirectionalLight { direction -0.3 -0.2 -1 intensity 0.8 ambientIntensity 0.4 }
DEF PICK_TARGET Solid {
  translation -0.35 -0.45 0.12
  children [
    Shape {
      appearance PBRAppearance { baseColor 0.05 0.1 0.9 roughness 1 metalness 0 }
      geometry Box { size 0.24 0.28 0.2 }
    }
  ]
}
Robot {
  name "physics-frame-probe"
  supervisor TRUE
  controller "<extern>"
}
'''


def wait_for(predicate, timeout, name):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        result = predicate()
        if result:
            return result
        time.sleep(.05)
    raise RuntimeError(f'timeout waiting for {name}')


def blue_center(path):
    from PIL import Image

    with Image.open(path) as capture:
        width, height = capture.size
        rgb = capture.convert('RGB').tobytes()
        blue = [(i % width, i // width) for i, (r, g, b) in
                enumerate(zip(rgb[::3], rgb[1::3], rgb[2::3])) if b > 75 and b > 2 * max(r, g)]
    if len(blue) < 200:
        raise ValueError(f'blue target not visible: {path}')
    x, y = (sum(points) // len(blue) for points in zip(*blue))
    if x < width // 2 and y < height // 2:
        raise ValueError('target does not challenge the reduced framebuffer picking extent')
    return (width, height), (x, y), len(blue)


def viewport(log, screen):
    sizes = SIZE.findall(log.read_text(encoding='utf-8', errors='replace'))
    if not sizes:
        return None
    rw, rh, width, height = map(int, sizes[-1])
    if (width, height) != screen:
        return None
    tree = subprocess.check_output(['xwininfo', '-root', '-tree'], text=True)
    windows = re.findall(
        rf'^\s+(0x[\da-f]+) "Webots": .* {width}x{height}[+-]\d+[+-]\d+\s+[+-]\d+[+-]\d+\s*$',
        tree, re.M | re.I)
    return (windows[0], (rw, rh)) if len(windows) == 1 else None


def probe():
    from controller import Supervisor

    robot = Supervisor()
    directory = Path(os.environ['WEEBEE_GUI_FIXTURE'])
    log = directory / 'webots.log'
    target = robot.getFromDef('PICK_TARGET')
    if target is None:
        raise RuntimeError('missing selection target')
    for _ in range(16):
        if robot.step(8) == -1:
            raise RuntimeError('Webots stopped before rendering')
    capture = directory / 'visible.png'
    robot.exportImage(str(capture), 100)
    wait_for(lambda: capture.is_file() and capture.stat().st_size > 100, 8, 'native screenshot')
    screen, point, area = blue_center(capture)
    window, draw = wait_for(lambda: viewport(log, screen), 8, 'unscaled Qt viewport')
    scale = int(os.environ['WEBOTS_EXPERIMENT_MAIN_RENDER_SCALE'])
    if draw != tuple(x * scale // 100 for x in screen):
        raise ValueError(f'framebuffer does not match requested scale: {draw}, {screen}')
    subprocess.run(['xdotool', 'mousemove', '--window', window, *map(str, point), 'click', '1'], check=True)

    def picked():
        if robot.step(8) == -1:
            raise RuntimeError('Webots stopped during selection')
        node = robot.getSelected()
        return node and node.getId() == target.getId()

    wait_for(picked, 5, 'native selection at the capture coordinates')
    result = dict(scale=scale, capture_size=screen, framebuffer_size=draw, target_pixels=area,
                  target_click=point, picked_def=target.getDef())
    if scale == 50:
        movie = directory / 'recording.mp4'
        start_mark = len(SIZE.findall(log.read_text(encoding='utf-8', errors='replace')))
        robot.movieStartRecording(str(movie), 320, 240, 0, 80, 1, False)
        for _ in range(40):
            if robot.step(8) == -1 or robot.movieFailed():
                raise RuntimeError('native movie capture failed')
        stop_mark = len(SIZE.findall(log.read_text(encoding='utf-8', errors='replace')))
        sizes = SIZE.findall(log.read_text(encoding='utf-8', errors='replace'))
        if not any((rw, rh) == (sw, sh) for rw, rh, sw, sh in sizes[start_mark:stop_mark]):
            raise ValueError('recording never used a native-size framebuffer')
        robot.movieStopRecording()

        def recording_ready():
            if robot.step(8) == -1 or robot.movieFailed():
                raise RuntimeError('native movie encoding failed')
            return robot.movieIsReady() and movie.is_file() and movie.stat().st_size > 100

        wait_for(recording_ready, 20, 'encoded movie')
        width, height = screen
        resumed = tuple(map(str, (width // 2, height // 2, width, height)))
        sizes = SIZE.findall(log.read_text(encoding='utf-8', errors='replace'))
        if not sizes[stop_mark:] or sizes[-1] != resumed:
            raise ValueError('the reduced framebuffer did not resume after recording')
        metadata = subprocess.check_output(
            ['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
             'stream=width,height,nb_frames', '-of', 'json', str(movie)], text=True)
        video, = json.loads(metadata)['streams']
        if (video['width'], video['height']) != (320, 240) or int(video['nb_frames']) < 2:
            raise ValueError('native recording did not contain the expected video')
        result['recording'] = video
        result['restored_after_recording'] = list(draw)

    (directory / 'gui.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    robot.simulationQuit(0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--patched', type=Path, required=True)
    parser.add_argument('--frame-tools', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--port', type=int, default=1356)
    args = parser.parse_args()
    sys.path.insert(0, str(args.frame_tools.resolve()))
    from bench import distribution, fingerprint, run_external

    home = args.patched.resolve()
    output = args.output.resolve()
    output.mkdir()
    identity = fingerprint(home)
    executable, _, _ = distribution(home)
    results = []
    for scale in (100, 50):
        directory = output / str(scale)
        world = directory / 'worlds/picking.wbt'
        world.parent.mkdir(parents=True)
        world.write_text(WORLD, encoding='utf-8')
        env = dict(os.environ, WEEBEE_GUI_FIXTURE=str(directory), WEBOTS_RENDER_TRACE='1',
                   WEBOTS_EXPERIMENT_MAIN_RENDER_SCALE=str(scale),
                   WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE='true')
        command = [str(executable), '--batch', '--stdout', '--stderr', '--mode=realtime', '--extern-urls',
                   f'--port={args.port}', str(world)]
        with (directory / 'webots.log').open('wb') as log:
            run_external(command, home, directory, Path(__file__).resolve(), env,
                         SimpleNamespace(tcp_port=args.port, timeout=45), log)
        results.append(json.loads((directory / 'gui.json').read_text()))
    if results[0]['capture_size'] != results[1]['capture_size'] or any(
            abs(x - y) > 3 for x, y in zip(results[0]['target_click'], results[1]['target_click'])):
        raise ValueError('the onscreen capture or target position changed between resolutions')
    (output / 'summary.json').write_text(json.dumps(dict(engine=identity, trials=results), indent=2) + '\n')


if __name__ == '__main__':
    if 'WEEBEE_GUI_FIXTURE' in os.environ:
        probe()
    else:
        main()
