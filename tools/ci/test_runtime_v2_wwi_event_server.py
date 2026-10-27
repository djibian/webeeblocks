#!/usr/bin/env python3
"""HTTP-level adversarial regression for the shared native CI event collector."""
from __future__ import annotations

import concurrent.futures
import contextlib
import http.client
import json
import pathlib
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request

SERVER = pathlib.Path(__file__).with_name('runtime_wwi_event_server.py')


@contextlib.contextmanager
def event_server():
    with tempfile.TemporaryDirectory(prefix='webeeblocks-wwi-events-') as directory:
        root = pathlib.Path(directory)
        events, done = root / 'events.jsonl', root / 'finished'
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            port = probe.getsockname()[1]
        process = subprocess.Popen(
            [sys.executable, str(SERVER), '--host', '127.0.0.1', '--port', str(port),
             '--output', str(events), '--completion-sentinel', str(done)],
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        )
        try:
            for _ in range(100):
                if process.poll() is not None:
                    raise AssertionError('event collector exited unexpectedly')
                try:
                    with urllib.request.urlopen(f'http://127.0.0.1:{port}/health', timeout=0.2) as result:
                        if result.status == 200:
                            break
                except (OSError, urllib.error.URLError):
                    time.sleep(0.02)
            else:
                raise AssertionError('event collector never became ready')
            yield port, events, done
        finally:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
            process.stderr.close()


def post(port: int, data: bytes, *, length: str | None = None) -> int:
    request = urllib.request.Request(
        f'http://127.0.0.1:{port}/event', data=data,
        headers={'Content-Type': 'application/json'}, method='POST',
    )
    if length is not None:
        request.add_header('Content-Length', length)
    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            return response.status
    except urllib.error.HTTPError as error:
        error.close()
        return error.code


class EventCollectorTests(unittest.TestCase):
    def test_invalid_events_do_not_corrupt_evidence_or_fake_completion(self):
        with event_server() as (port, events, done):
            invalid = [b'[]', b'null', b'"hello"', b'1', b'{bad', b'\xff', b'']
            # RFC 8259 excludes non-finite numbers; Python's JSON parser is
            # permissive by default, including finite-looking exponent overflow.
            # None may poison JSONL or create an early completion sentinel.
            invalid += [
                b'{"event":"VALID","sensor":NaN}',
                b'{"event":"CHALLENGE_TEST_COMPLETE","sensor":Infinity}',
                b'{"event":"CHALLENGE_TEST_COMPLETE","sensor":-Infinity}',
                b'{"event":"CHALLENGE_TEST_COMPLETE","data":{"values":[1e999]}}',
                b'{"event":"VALID","sensor":1e999}',
            ]
            for body in invalid:
                with self.subTest(body=body):
                    self.assertEqual(post(port, body), 400)
                    self.assertFalse(events.exists(), 'invalid event entered the evidence archive')
                    self.assertFalse(done.exists(), 'invalid event set completion sentinel')
            # Excess nesting is within the byte bound but previously raised
            # RecursionError in the HTTP thread, closing without an HTTP reply.
            nested = b'{"event":"CHALLENGE_TEST_COMPLETE","nested":' + b'[' * 20000 + b'0' + b']' * 20000 + b'}'
            self.assertEqual(post(port, nested), 400)
            self.assertFalse(events.exists())
            self.assertFalse(done.exists())
            for length in ('invalid', '-1', '0'):
                with self.subTest(content_length=length):
                    conn = http.client.HTTPConnection('127.0.0.1', port, timeout=3)
                    conn.putrequest('POST', '/event')
                    conn.putheader('Content-Length', length)
                    conn.endheaders()
                    self.assertEqual(conn.getresponse().status, 400)
                    conn.close()
            conn = http.client.HTTPConnection('127.0.0.1', port, timeout=3)
            conn.putrequest('POST', '/event')
            conn.putheader('Content-Length', str(4 * 1024 * 1024 + 1))
            conn.endheaders()
            self.assertEqual(conn.getresponse().status, 413)
            conn.close()
            # Reject a declared payload longer than the transmitted bytes.
            conn = http.client.HTTPConnection('127.0.0.1', port, timeout=3)
            conn.putrequest('POST', '/event')
            conn.putheader('Content-Length', '50')
            conn.endheaders(b'{}')
            conn.sock.shutdown(socket.SHUT_WR)
            self.assertEqual(conn.getresponse().status, 400)
            conn.close()
            self.assertFalse(events.exists())
            self.assertFalse(done.exists())
            self.assertEqual(post(port, b'{"event":"VALID","value":2}'), 204)
            self.assertEqual(json.loads(events.read_text()), {'event': 'VALID', 'value': 2})
            self.assertFalse(done.exists())
            self.assertEqual(post(port, b'{"event":"CHALLENGE_TEST_COMPLETE"}'), 204)
            self.assertEqual(done.read_text(), 'CHALLENGE_TEST_COMPLETE\n')
            self.assertEqual(len(events.read_text().splitlines()), 2)

    def test_concurrent_valid_events_remain_complete_rows(self):
        with event_server() as (port, events, done):
            values = list(range(32))
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                statuses = list(pool.map(lambda i: post(port, json.dumps({'event':'OBS','i':i}).encode()), values))
            self.assertEqual(statuses, [204] * len(values))
            rows = [json.loads(line) for line in events.read_text().splitlines()]
            self.assertEqual(len(rows), len(values))
            self.assertEqual(sorted(row['i'] for row in rows), values)
            self.assertTrue(all(row['event'] == 'OBS' for row in rows))
            self.assertFalse(done.exists())


if __name__ == '__main__':
    unittest.main()
