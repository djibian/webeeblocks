#!/usr/bin/env python3
"""Offline-only integrity and claim checks for checkpoint #572 observations."""
import base64
import csv
import hashlib
import io
import json
import lzma
import statistics
import tarfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARCHIVE = HERE / "raw-evidence.tar.xz.base64"
EXPECTED_XZ_SHA256 = "5574217d0deda4da57267a880a0682ab4aa0cac39c3f58c519c80f311c8a4b1a"
EXPECTED_ORIGINAL_ZIP_SHA256 = "5cd8794d53f9015d58b086c7b766778422e6a635b059fa2f9658c2cad8504337"


def check():
    compressed = base64.b64decode(ARCHIVE.read_bytes().strip(), validate=True)
    assert hashlib.sha256(compressed).hexdigest() == EXPECTED_XZ_SHA256, "archive hash differs"
    members = {}
    with tarfile.open(fileobj=io.BytesIO(lzma.decompress(compressed)), mode="r:") as tf:
        for item in tf:
            assert item.isfile() and item.name not in members, "non-file or duplicate member"
            assert not item.name.startswith("/") and ".." not in item.name.split("/"), "unsafe path"
            members[item.name] = tf.extractfile(item).read()
    manifest = json.loads(members.pop("MANIFEST_PUBLIC.json"))
    assert manifest["original_owner_archive_sha256"] == EXPECTED_ORIGINAL_ZIP_SHA256
    assert len(manifest["files"]) == len(members) == 30
    assert "source_local" not in manifest
    expected = {"raw/" + f["path"] for f in manifest["files"]}
    assert expected == members.keys(), "raw file inventory differs"
    for f in manifest["files"]:
        data = members["raw/" + f["path"]]
        assert len(data) == f["bytes"] and hashlib.sha256(data).hexdigest() == f["sha256"], f["path"]
    for case, mean, low, high in (("near", 480.26, 477, 485), ("far", 989.24, 981, 997)):
        data = members[f"raw/front-{case}/front-range.csv"].decode("utf-8")
        rows = list(csv.DictReader(io.StringIO(data)))
        assert len(rows) == 100 and all(r["classification"] == "available" for r in rows)
        values = [int(r["raw_mm"]) for r in rows]
        stamps = [int(r["device_timestamp_ms"]) for r in rows]
        assert statistics.mean(values) == mean and min(values) == low and max(values) == high
        assert all(b - a == 100 for a, b in zip(stamps, stamps[1:])), "timestamp anomaly"
        result = json.loads(members[f"raw/front-{case}/diagnostic-result.json"])
        assert result["status"] == "OBSERVED" and result["physical_verdict"] is None
        print(f"{case}: 100 finite samples, mean={mean:.2f} mm; OBSERVED acquisition only")
    print("PASS: 30 raw files match the SHA-256 manifest; no flight qualification")


if __name__ == "__main__":
    check()
