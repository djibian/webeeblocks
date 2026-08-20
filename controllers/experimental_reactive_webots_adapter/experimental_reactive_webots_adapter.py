#!/usr/bin/env python3
import json
import math
import queue
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from controller import Supervisor

PORT = 8765
MAX_MOVE_STEP_M = 0.02

robot = Supervisor()
timestep = int(robot.getBasicTimeStep())
self_node = robot.getSelf()
translation = self_node.getField('translation')
range_front = robot.getDevice('range_front')
requests = queue.Queue()
trace = []
ready = False
fatal = None
origin = None
anchor = None

class RpcRequest:
    def __init__(self, payload):
        self.payload = payload
        self.event = threading.Event()
        self.response = None

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')

    def send_json(self, status, payload):
        body = json.dumps(payload, separators=(',', ':')).encode('utf-8')
        self.send_response(status)
        self.cors()
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.cors()
        self.end_headers()

    def do_GET(self):
        if self.path == '/health':
            self.send_json(200, {'ready': ready, 'fatal': fatal})
        elif self.path == '/trace':
            self.send_json(200, {'trace': trace})
        else:
            self.send_json(404, {'ok': False, 'error': 'not found'})

    def do_POST(self):
        if self.path != '/rpc':
            self.send_json(404, {'ok': False, 'error': 'not found'})
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            payload = json.loads(self.rfile.read(length).decode('utf-8'))
        except Exception as exc:
            self.send_json(400, {'ok': False, 'error': 'invalid JSON: ' + str(exc)})
            return
        if not ready or fatal:
            self.send_json(503, {'ok': False, 'error': fatal or 'Webots adapter not ready'})
            return
        request = RpcRequest(payload)
        requests.put(request)
        if not request.event.wait(20):
            self.send_json(504, {'ok': False, 'error': 'Webots adapter command timeout'})
            return
        self.send_json(200, request.response)

def pose():
    return [float(v) for v in translation.getSFVec3f()]

def hold(position, steps=1):
    global anchor
    anchor = list(position)
    for _ in range(steps):
        translation.setSFVec3f(anchor)
        self_node.resetPhysics()
        if robot.step(timestep) == -1:
            raise RuntimeError('simulation stopped during action')

def move_to(target):
    start = pose()
    dx, dy, dz = [target[i] - start[i] for i in range(3)]
    distance = math.sqrt(dx * dx + dy * dy + dz * dz)
    count = max(1, int(math.ceil(distance / MAX_MOVE_STEP_M)))
    for i in range(1, count + 1):
        alpha = i / count
        hold([start[0] + dx * alpha, start[1] + dy * alpha, start[2] + dz * alpha])
    hold(target, 2)
    return start, pose()

def handle(payload):
    if not isinstance(payload, dict):
        raise ValueError('payload must be an object')
    op = payload.get('op')
    if op == 'range':
        if payload.get('direction') != 'front':
            raise ValueError('CAPABILITY_UNAVAILABLE range direction')
        hold(anchor, 1)
        raw = float(range_front.getValue())
        value_m = raw / 1000.0
        if not math.isfinite(value_m) or value_m < 0 or value_m > 2.001:
            raise ValueError('INVALID_RANGE_SAMPLE')
        entry = {'op': 'range', 'direction': 'front', 'raw': raw, 'value_m': value_m, 'pose': pose()}
        trace.append(entry)
        return {'ok': True, 'value_m': value_m, 'source': 'Webots range_front'}
    if op == 'takeoff':
        height = float(payload.get('height_m'))
        if not math.isfinite(height) or height < 0.2 or height > 1.5:
            raise ValueError('INVALID_TAKEOFF_HEIGHT')
        before, after = move_to([anchor[0], anchor[1], origin[2] + height])
        trace.append({'op': 'takeoff', 'height_m': height, 'before': before, 'after': after})
        return {'ok': True, 'before': before, 'after': after}
    if op == 'move':
        direction = payload.get('direction')
        distance = float(payload.get('distance_m'))
        if direction not in ('forward', 'left'):
            raise ValueError('CAPABILITY_UNAVAILABLE move direction')
        if not math.isfinite(distance) or distance < 0.1 or distance > 2.0:
            raise ValueError('INVALID_MOVE_DISTANCE')
        target = list(anchor)
        target[0 if direction == 'forward' else 1] += distance
        before, after = move_to(target)
        trace.append({'op': 'move', 'direction': direction, 'distance_m': distance, 'before': before, 'after': after})
        return {'ok': True, 'before': before, 'after': after}
    if op == 'land':
        before, after = move_to([anchor[0], anchor[1], origin[2]])
        trace.append({'op': 'land', 'before': before, 'after': after})
        return {'ok': True, 'before': before, 'after': after}
    raise ValueError('CAPABILITY_UNAVAILABLE operation')

def server_main():
    server = ThreadingHTTPServer(('0.0.0.0', PORT), Handler)
    server.daemon_threads = True
    server.serve_forever()

threading.Thread(target=server_main, daemon=True).start()

try:
    if range_front is None or self_node is None or translation is None:
        raise RuntimeError('required Webots capability missing')
    range_front.enable(timestep)
    origin = pose()
    anchor = list(origin)
    hold(anchor, 5)
    ready = True
    print('WEBEEBLOCKS_REACTIVE_WEBOTS_READY port=%d origin=%s' % (PORT, origin), flush=True)

    while robot.step(timestep) != -1:
        translation.setSFVec3f(anchor)
        self_node.resetPhysics()
        try:
            request = requests.get_nowait()
        except queue.Empty:
            continue
        try:
            response = handle(request.payload)
        except Exception as exc:
            response = {'ok': False, 'error': str(exc)}
            trace.append({'op': 'error', 'request': request.payload, 'error': str(exc)})
        request.response = response
        request.event.set()
except Exception as exc:
    fatal = str(exc)
    print('WEBEEBLOCKS_REACTIVE_WEBOTS_FATAL ' + fatal, flush=True)
    while robot.step(timestep) != -1:
        pass
