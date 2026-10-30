#!/usr/bin/env python3
"""Experimental ONE-SHOT CDP navigation after observed Chrome PROFILE_IN_USE=21.
No profile deletion, process kill, blind retry or success from CDP alone:
the unchanged native Webots browser oracle must independently observe Blockly.
"""
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

out, url = sys.argv[1:3]
endpoint = "http://127.0.0.1:9222/json/new?" + urllib.parse.quote(url, safe="")
record = {"kind": "CDP_RESCUE", "epoch_ns": time.time_ns(), "requested_url": url}
last = ""
deadline = time.monotonic() + 4.0
while time.monotonic() < deadline:
    try:
        req = urllib.request.Request(endpoint, method="PUT")
        with urllib.request.urlopen(req, timeout=0.6) as result:
            document = json.loads(result.read(65536))
        record.update({"http_status": result.status,
                       "target_id": document.get("id"),
                       "type": document.get("type"),
                       "url": document.get("url")})
        break
    except (OSError, ValueError) as exc:
        last = str(exc)
        time.sleep(0.12)
else:
    record["error"] = last or "CDP timed out"
with open(out, "a", encoding="utf-8") as f:
    f.write(json.dumps(record, sort_keys=True) + "\n")
if (record.get("target_id") and record.get("type") == "page" and
        record.get("url") in (url, url.replace(" ", "%20"))):
    print("CDP_DOCUMENT_TARGET_CREATED", record["target_id"], flush=True)
    sys.exit(0)
print("CDP_DOCUMENT_TARGET_NOT_CREATED", record, file=sys.stderr)
sys.exit(1)
