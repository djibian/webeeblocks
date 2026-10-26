#!/usr/bin/env python3
"""Prepare the exact R2025a outcome world's assets before its native deadline.

The stock Ubuntu image omits project assets. Remote EXTERNPROTOs otherwise put
network retrieval inside the 35 s native proof. Never replace missing assets
with simplified geometry or treat a failed preparation as a native result.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from urllib.request import urlopen

from localize_webots_world import localize

SOURCE_COMMIT = "c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b"
LOCK = Path(__file__).with_name("runtime_v2_outcome_assets.lock.json")
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_TOTAL_BYTES = 16 * 1024 * 1024


def load_lock(path: Path = LOCK) -> dict:
    lock = json.loads(path.read_text(encoding="utf-8"))
    if lock.get("schema") != 1 or lock.get("source_commit") != SOURCE_COMMIT:
        raise ValueError("unexpected outcome asset source/schema")
    assets = lock.get("assets")
    if not isinstance(assets, list) or not assets or len(assets) > 64:
        raise ValueError("invalid outcome asset inventory")
    seen = set()
    total = 0
    for item in assets:
        name = item.get("path", "")
        parts = PurePosixPath(name).parts
        if (not parts or parts[0] != "projects" or ".." in parts or
                PurePosixPath(name).as_posix() != name or "\\" in name or
                name in seen or not re.fullmatch(r"[A-Za-z0-9_./-]+", name)):
            raise ValueError("unsafe/duplicate outcome asset path")
        size = item.get("bytes")
        if (type(size) is not int or not 0 < size <= MAX_FILE_BYTES or
                not re.fullmatch(r"[0-9a-f]{64}", item.get("sha256", "")) or
                not re.fullmatch(r"[0-9a-f]{40}", item.get("git_blob", ""))):
            raise ValueError("invalid outcome asset size/digest")
        seen.add(name)
        total += size
    if total > MAX_TOTAL_BYTES:
        raise ValueError("unbounded outcome asset inventory")
    return lock


def prepare(root: Path, source_world: Path, evidence: Path) -> tuple[Path, Path]:
    """New private directory; each download verified before any Webots launch."""
    lock = load_lock()
    root.mkdir()  # refuse stale files, symlinks and an existing prepared tree
    for item in lock["assets"]:
        url = f"https://raw.githubusercontent.com/cyberbotics/webots/{SOURCE_COMMIT}/{item['path']}"
        with urlopen(url, timeout=30) as response:
            data = response.read(item["bytes"] + 1)
        blob = b"blob " + str(len(data)).encode("ascii") + b"\0" + data
        if (len(data) != item["bytes"] or
                hashlib.sha256(data).hexdigest() != item["sha256"] or
                hashlib.sha1(blob).hexdigest() != item["git_blob"]):
            raise ValueError(f"outcome asset integrity failure: {item['path']}")
        target = root / item["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    world = root / "runtime_v2_outcome_probe.wbt"
    localize(source_world, world, expected=4)
    # Record exactly what will be mounted, not a claim of native readiness.
    evidence.write_text(json.dumps({
        "schema": 1, "status": "PREPARED", "source_commit": SOURCE_COMMIT,
        "lock_sha256": hashlib.sha256(LOCK.read_bytes()).hexdigest(),
        "source_world_sha256": hashlib.sha256(source_world.read_bytes()).hexdigest(),
        "local_world_sha256": hashlib.sha256(world.read_bytes()).hexdigest(),
        "assets": lock["assets"],
    }, indent=2) + "\n", encoding="utf-8")
    return world, root / "projects"
