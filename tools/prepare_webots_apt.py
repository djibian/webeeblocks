#!/usr/bin/env python3
"""Exclude only unused NVIDIA/CUDA APT source from software-rendered Webots CI.

APT's ordinary verification remains mandatory. This modifies an ephemeral CI
container's source list, not the pinned Webots image or installed packages.
Unknown formats are refused rather than disabling other package repositories.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import sys

CUDA_HOST = 'developer.download.nvidia.com'
CUDA_REPO = 'https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64'
CUDA_LINE = re.compile(
    r'^\s*deb(?:-src)?\s+(?:\[[^\]\r\n]+\]\s+)?'
    + re.escape(CUDA_REPO) + r'/?\s+/\s*(?:#.*)?$'
)


def prepare(sources_root: Path, *, software_rendering: bool) -> list[tuple[str, str, str]]:
    """Return path/before/after hashes; reject ambiguity before any write."""
    if not software_rendering:
        raise RuntimeError('NVIDIA source may only be disabled with software rendering')
    if not sources_root.is_dir():
        raise RuntimeError('APT configuration directory unavailable')
    paths = [sources_root / 'sources.list']
    parts = sources_root / 'sources.list.d'
    if parts.exists():
        if not parts.is_dir():
            raise RuntimeError('invalid APT sourceparts directory')
        paths.extend(sorted(p for p in parts.iterdir() if p.suffix in ('.list', '.sources')))
    edits = []
    for path in paths:
        if not path.exists():
            continue
        if not path.is_file() or path.is_symlink():
            raise RuntimeError('unsafe APT configuration file: ' + str(path))
        original = path.read_bytes()
        text = original.decode('utf-8')
        if CUDA_HOST not in text:
            continue
        if path.suffix == '.sources':
            raise RuntimeError('unsupported NVIDIA Deb822 source: ' + str(path))
        changed = []
        for line in text.splitlines(keepends=True):
            if CUDA_HOST in line and not line.lstrip().startswith('#'):
                if not CUDA_LINE.fullmatch(line.rstrip('\r\n')):
                    raise RuntimeError('unexpected NVIDIA repository declaration: ' + str(path))
                changed.append('# WEBEEBLOCKS_SOFTWARE_RENDERING_ONLY ' + line)
            else:
                changed.append(line)
        replacement = ''.join(changed).encode('utf-8')
        if replacement != original:
            edits.append((path, original, replacement))
    # No partial disabling if a later entry is unrecognizable.
    for path, original, replacement in edits:
        if path.read_bytes() != original:
            raise RuntimeError('APT source changed during validation: ' + str(path))
    result = []
    for path, original, replacement in edits:
        path.write_bytes(replacement)
        digest = lambda value: hashlib.sha256(value).hexdigest()
        result.append((str(path), digest(original), digest(replacement)))
    return result


def main() -> None:
    if len(sys.argv) != 1:
        raise SystemExit('usage: prepare_webots_apt.py')
    edits = prepare(Path('/etc/apt'), software_rendering=os.environ.get('LIBGL_ALWAYS_SOFTWARE') == 'true')
    for path, before, after in edits:
        print(f'WEBEEBLOCKS_APT_NVIDIA_DISABLED path={path} sha256_before={before} sha256_after={after}')
    if not edits:
        print('WEBEEBLOCKS_APT_NVIDIA_NOT_PRESENT_OR_ALREADY_DISABLED')


if __name__ == '__main__':
    main()
