#!/usr/bin/env python3
"""Request a normal Chromium shutdown through the DevTools Browser.close command."""

from __future__ import annotations

import base64
import json
import os
import socket
import struct
import time
import urllib.request
from urllib.parse import urlparse

DEBUG_VERSION_URL = "http://127.0.0.1:9222/json/version"


def debugger_url(timeout_s: float = 5.0) -> str:
    deadline = time.monotonic() + timeout_s
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(DEBUG_VERSION_URL, timeout=0.5) as response:
                payload = json.load(response)
            url = payload.get("webSocketDebuggerUrl")
            if not isinstance(url, str) or not url.startswith("ws://"):
                raise RuntimeError(f"invalid webSocketDebuggerUrl: {url!r}")
            return url
        except Exception as error:  # Chrome may still be bringing DevTools up.
            last_error = error
            time.sleep(0.1)
    raise RuntimeError(f"Chrome DevTools endpoint did not become ready: {last_error}")


def send_browser_close(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "ws" or parsed.hostname != "127.0.0.1":
        raise RuntimeError(f"unexpected DevTools websocket URL: {url}")

    port = parsed.port or 80
    path = parsed.path or "/"
    key = base64.b64encode(os.urandom(16)).decode("ascii")

    with socket.create_connection((parsed.hostname, port), timeout=2.0) as sock:
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {parsed.hostname}:{port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        sock.sendall(request.encode("ascii"))

        response = bytearray()
        while b"\r\n\r\n" not in response:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response.extend(chunk)
        status_line = bytes(response).split(b"\r\n", 1)[0]
        if b" 101 " not in status_line:
            raise RuntimeError(f"DevTools websocket handshake failed: {status_line!r}")

        payload = json.dumps({"id": 1, "method": "Browser.close"}, separators=(",", ":")).encode("utf-8")
        if len(payload) >= 126:
            raise RuntimeError("Browser.close frame unexpectedly large")
        mask = os.urandom(4)
        masked = bytes(value ^ mask[index % 4] for index, value in enumerate(payload))
        frame = bytes((0x81, 0x80 | len(payload))) + mask + masked
        sock.sendall(frame)


if __name__ == "__main__":
    url = debugger_url()
    send_browser_close(url)
    print("CHROME_CDP_BROWSER_CLOSE_SENT=PASS", flush=True)
