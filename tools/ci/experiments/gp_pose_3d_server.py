"""Read-only localhost 3D presentation adapter for experimental 160-byte poses.

No Webots API imports, no controls, no oracle data, no socket to the simulator.
--replay only replays existing native observations; never proves live coupling.
"""
import argparse
import bisect
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mmap
import os
from pathlib import Path
import re
import time
import uuid

from tools.ci.experiments.pose_mailbox_v1 import SIZE, read_once

NUMBER = r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][-+]?\d+)?'
BOX = re.compile(
    r'DEF\s+(GP_V2_(?:WHITE_[0-2]|L_\d+_\d+|H_\d+_\w+|FINAL_\w+)'
    r'|GP_ROUTE_(?:START|TARGET_[123]))\s+(?:Solid|Pose)\s*\{\s*'
    r'translation\s+(' + NUMBER + r')\s+(' + NUMBER + r')\s+(' + NUMBER
    + r')\s+[^\n]*?baseColor\s+(' + NUMBER + r')\s+(' + NUMBER
    + r')\s+(' + NUMBER + r')\s+[^\n]*?geometry\s+Box\s*\{\s*'
    r'size\s+(' + NUMBER + r')\s+(' + NUMBER + r')\s+(' + NUMBER + r')',
    re.M,
)


def visible_world(path):
    content = Path(path).read_bytes()
    boxes = []
    for m in BOX.finditer(content.decode('utf-8')):
        values = [float(x) for x in m.groups()[1:]]
        boxes.append(dict(name=m.group(1), position=values[:3],
                          color=values[3:6], size=values[6:9]))
    if not any('H_' in b['name'] for b in boxes) or not any(
            'L_' in b['name'] for b in boxes):
        raise ValueError('incomplete native Grand Prix visible geometry')
    return dict(boxes=boxes, world_sha256=hashlib.sha256(content).hexdigest(),
                scope='Visible static Box geometry only, not oracle information')


class PoseSource:
    def __init__(self, mailbox=None, replay=None):
        self.map = None
        self.rows = None
        self.started = time.monotonic()
        self.identities = {}
        if mailbox is not None:
            fd = os.open(mailbox, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
            try:
                if os.fstat(fd).st_size != SIZE:
                    raise ValueError('unexpected presentation mailbox size')
                self.map = mmap.mmap(fd, SIZE, access=mmap.ACCESS_READ)
            finally:
                os.close(fd)
        else:
            data = json.loads(Path(replay).read_text())
            self.rows = [r for r in data['samples']
                         if type(r.get('time_ms')) is int]
            if not self.rows:
                raise ValueError('empty native replay')
            self.times = [r['time_ms'] for r in self.rows]

    def latest(self):
        if self.map is not None:
            return read_once(self.map)
        elapsed_ms = min(self.times[-1], int(
            (time.monotonic() - self.started) * 1000))
        pos = bisect.bisect_right(self.times, elapsed_ms) - 1
        if pos < 0:
            return None
        row = self.rows[pos]
        attempt = row.get('attempt')
        key = str(attempt)
        if key not in self.identities:
            self.identities[key] = uuid.uuid4().hex
        valid = (attempt is not None and row.get('position') is not None
                 and row.get('orientation') is not None)
        return dict(incarnation=self.identities[key],
                    sequence=pos + 1,
                    time_ms=row['time_ms'] if valid else 0,
                    position=row['position'] if valid else [0.0] * 3,
                    orientation=row['orientation'] if valid else [0.0] * 9,
                    valid=valid)


def run(world, mailbox=None, replay=None, port=8769):
    scene = visible_world(world)
    source = PoseSource(mailbox, replay)
    html = Path(__file__).with_name('gp_pose_3d_viewer.html').read_bytes()

    class ReadOnlyHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/':
                data, content_type = html, 'text/html; charset=utf-8'
            elif self.path == '/scene':
                data, content_type = json.dumps(scene).encode(), 'application/json'
            elif self.path == '/pose':
                data, content_type = json.dumps(source.latest()).encode(), 'application/json'
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            self.send_error(405, 'presentation is read-only')

        def log_message(self, *unused):
            pass

    if type(port) is not int or not 0 <= port <= 65535:
        raise ValueError('invalid port')
    server = ThreadingHTTPServer(('127.0.0.1', port), ReadOnlyHandler)
    print(json.dumps(dict(url=f'http://127.0.0.1:{server.server_port}/',
                          mode='native-mailbox' if mailbox else 'offline-replay',
                          scene_sha256=scene['world_sha256'],
                          static_boxes=len(scene['boxes']))), flush=True)
    try:
        server.serve_forever(poll_interval=0.1)
    finally:
        server.server_close()


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--mailbox', help='existing 160-byte read-only mmap')
    group.add_argument('--replay', help='native pose-observations.json; offline replay')
    parser.add_argument('--world', required=True, help='exact world.wbt, geometry only')
    parser.add_argument('--port', type=int, default=8769)
    args = parser.parse_args()
    run(args.world, mailbox=args.mailbox, replay=args.replay, port=args.port)


if __name__ == '__main__':
    main()
