"""Inject malformed terminal frame 104 replies through the real Linux Controller sockets.

Only the peer is a fixture. The compiled R2025a library owns both schedulers,
clock, device configuration, normal distance sample and frame decoding.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
UPSTREAM = 'c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b'
FAULTS = ('bad_version', 'truncated_header', 'truncated_body',
          'overlong_body', 'unavailable_with_data', 'unavailable')


def exact(connection, size):
    result = bytearray()
    while len(result) < size:
        data = connection.recv(size - len(result))
        if not data:
            raise EOFError(f'Received {len(result)} of {size} bytes')
        result.extend(data)
    return bytes(result)


def request(connection, duration):
    length, = struct.unpack('<I', exact(connection, 4))
    if not 8 <= length <= 1024:
        raise ValueError(f'Unexpected Controller request size {length}')
    delay, = struct.unpack('<i', exact(connection, 4))
    if delay != duration:
        raise ValueError(f'Expected {duration}-ms request, got {delay}')
    return exact(connection, length - 8)


def reply(connection, transport, body):
    payload = struct.pack('<i', 0) + body
    if transport == 'tcp':
        packet = struct.pack('<HIIB', 1, len(payload), len(payload), 0) + payload
    else:
        packet = struct.pack('<I', len(payload) + 4) + payload
    connection.sendall(packet)


def tagged(tag, code):
    return struct.pack('<HB', tag, code)


def trial(executable, source, working, transport, protocol):
    version, robot, distance, configure, time_code, distance_code, frame_code, mode = protocol
    env = dict(os.environ, WEBOTS_HOME=str(source))
    for key in ('WEBOTS_CONTROLLER_URL', 'WEBOTS_ROBOT_NAME', 'WEBOTS_INSTANCE_PATH',
                'WEBOTS_STDOUT_REDIRECT', 'WEBOTS_STDERR_REDIRECT', 'LD_PRELOAD', 'LD_LIBRARY_PATH'):
        env.pop(key, None)

    with socket.socket(socket.AF_INET if transport == 'tcp' else socket.AF_UNIX) as listener:
        listener.settimeout(5)
        if transport == 'tcp':
            listener.bind(('127.0.0.1', 0))
            env['WEBOTS_CONTROLLER_URL'] = f'tcp://127.0.0.1:{listener.getsockname()[1]}'
        else:
            address = working / 'ipc/probe/intern'
            address.parent.mkdir(parents=True)
            listener.bind(str(address))
            env.update(WEBOTS_INSTANCE_PATH=str(working) + '/', WEBOTS_ROBOT_NAME='probe')
        listener.listen(1)

        with subprocess.Popen([str(executable)], env=env, text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE) as client:
            try:
                connection, _ = listener.accept()
                with connection:
                    connection.settimeout(5)
                    if transport == 'tcp':
                        if exact(connection, 3) != b'CTR':
                            raise ValueError('Unexpected TCP handshake')
                        connection.sendall(b'CONNECTED\0')
                    request(connection, 0)
                    configuration = (tagged(0, configure) + b'probe\0R2025a\0' +
                                     struct.pack('<BBHHdH', 1, 1, 2, robot, 0.0, distance) +
                                     b'distance\0\0' + struct.pack('<d', 8.0) +
                                     b'.\0fixture.wbt\0\0\0\0probe\0\0' +
                                     struct.pack('<BBi', 0, 0, mode) +
                                     tagged(0, configure) + struct.pack('<IIBB', 1, 0, 0, 0) +
                                     b'Robot\0PROBE\0')
                    reply(connection, transport, configuration)

                    cases = []
                    for step in range(1, 13):
                        outgoing = request(connection, 8)
                        if struct.pack('<Bi', frame_code, 2) not in outgoing:
                            raise ValueError('Controller did not send the requested optional observation')
                        sensor_and_time = (tagged(0, time_code) + struct.pack('<d', step * 0.008) +
                                           tagged(1, distance_code) + struct.pack('<d', 100.0 + step))
                        prefix = tagged(0, frame_code)
                        body = struct.pack('<16siid18d', b'frame-generation', 1, 2, step * 8.0, *([0.0] * 18))
                        if version == 2:
                            body += struct.pack('<16sQ', b'scene-generation', 1)
                        good = struct.pack('<ii', version, 0) + body
                        variants = (struct.pack('<ii', version + 1, 0) + body, good[:5], good[:-1],
                                    good + b'\xff', struct.pack('<iiB', version, -1, 255),
                                    struct.pack('<ii', version, -1))
                        suffix = good if step % 2 else variants[step // 2 - 1]
                        cases.append('valid' if step % 2 else FAULTS[step // 2 - 1])
                        reply(connection, transport, sensor_and_time + prefix + suffix)

                    request(connection, 0)
                    reply(connection, transport, b'')
                    if exact(connection, 4) != bytes(4):
                        raise ValueError('Unexpected cleanup packet')
                stdout, stderr = client.communicate(timeout=5)
            finally:
                if client.poll() is None:
                    client.kill()
                    client.wait(timeout=5)
        rows = [json.loads(line) for line in stdout.splitlines()]
        if client.returncode or stderr or len(rows) != len(cases):
            raise RuntimeError(f'{transport} native client failed ({client.returncode}): {stderr}\n{stdout}')
        return [{'case': case, **row} for case, row in zip(cases, rows, strict=True)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--webots-source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--transport', choices=('both', 'ipc', 'tcp'), default='both')
    args = parser.parse_args()
    source = args.webots_source.resolve(strict=True)
    if subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip() != UPSTREAM:
        raise ValueError('Use the pinned R2025a checkout and build its patched Controller first')
    library = source / 'lib/controller/libController.so'
    digest = hashlib.sha256(library.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix='wb104-', dir='/tmp') as folder:
        working = Path(folder)
        executable = working / 'probe'
        subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                        '-I', str(source / 'include/controller/c'), '-I', str(source / 'src/controller/c'),
                        str(HERE / 'wire_transport_probe.c'), '-L', str(library.parent),
                        '-Wl,-rpath,' + str(library.parent), '-lController', '-lm',
                        '-o', str(executable)], check=True)
        protocol = tuple(map(int, subprocess.check_output([str(executable), '--describe'], text=True).split()))
        if protocol[0] not in (1, 2):
            raise ValueError(f'Unexpected frame version {protocol[0]}')
        transports = ('ipc', 'tcp') if args.transport == 'both' else (args.transport,)
        result = {name: trial(executable, source, working, name, protocol) for name in transports}
    if args.transport == 'both' and result['ipc'] != result['tcp']:
        raise ValueError('Native IPC and TCP observations differed')
    with args.output.open('x', encoding='utf-8') as out:
        json.dump({'upstream': UPSTREAM, 'controller_sha256': digest, 'frame_version': protocol[0],
                   'transports': result}, out, indent=2)
        out.write('\n')
    print(f'PASS native Controller {args.transport}, six invalid/unavailable and six valid frames per transport')


if __name__ == '__main__':
    main()
