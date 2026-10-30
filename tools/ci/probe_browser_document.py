#!/usr/bin/env python3
"""Bounded disposable CI probe: CDP targets, Webots HTTP readiness, browser PID.
This observer never declares success and never controls a pupil's browser.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

out = sys.argv[1]
doc = "http://127.0.0.1:1234/robot_windows/blockly_v2/blockly_v2.html?name=Crazyflie"
cdp = "http://127.0.0.1:9222/json/list"

def get(url):
    try:
        with urllib.request.urlopen(url, timeout=0.3) as response:
            body = response.read(150000)
            if url == cdp:
                targets = json.loads(body)
                return dict(status=response.status, targets=[
                    {"id": t.get("id"), "type": t.get("type"), "url": t.get("url"),
                     "title": t.get("title")} for t in targets])
            return dict(status=response.status, length=len(body))
    except (OSError, ValueError) as error:
        return dict(error=str(error)[:180])

for i in range(45):
    record = {
        "kind": "DOCUMENT_PROBE", "seq": i, "epoch_ns": time.time_ns(),
        "cdp": get(cdp), "http_readiness": get(doc),
    }
    with open(out, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")
        f.flush()
    time.sleep(0.25)
