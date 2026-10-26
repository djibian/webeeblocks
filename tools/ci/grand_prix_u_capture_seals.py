"""Fail closed when a native Grand Prix trial changed after sha256.json was written.

This is a late recheck, not a producer/descendant lifetime guarantee. It cannot
prevent writes after the last check; #656 explores stronger writer retirement.
"""
import hashlib
import json
from pathlib import Path
import re
import stat


class CaptureSealError(RuntimeError):
    pass


def _unique_pairs(pairs):
    """A signed JSON object cannot have two meanings for the same key."""
    values = {}
    for name, value in pairs:
        if name in values:
            raise CaptureSealError(f'duplicate JSON manifest key: {name}')
        values[name] = value
    return values


def verify_new_capture_seals(root, baseline, expected):
    """Recheck EXACT trial inventory registered by trial(), not surviving names."""
    root = Path(root)
    if (not isinstance(baseline, set) or not isinstance(expected, set) or
            not expected or baseline.intersection(expected)):
        raise CaptureSealError('missing or inconsistent expected native trial inventory')
    if any(not isinstance(name, str) or not name.startswith('gp-u-v1-') or
           '/' in name or '\\' in name for name in expected | baseline):
        raise CaptureSealError('malformed trial directory inventory')
    # Do not use Path.is_dir() to filter entries: it follows symlinks and omits
    # substituted regular files and broken symlinks, producing false PASS.
    all_entries = {p.name: p for p in root.iterdir() if p.name.startswith('gp-u-v1-')}
    actual = set(all_entries) - baseline
    if actual != expected:
        raise CaptureSealError('missing or unexpected native trial directories: ' +
                               str(sorted(actual ^ expected)))
    for name in sorted(expected):
        folder = all_entries[name]
        if not stat.S_ISDIR(folder.lstat().st_mode):
            raise CaptureSealError(f'{name}: non-directory or symlink native trial evidence')
        manifest = folder / 'sha256.json'
        if manifest.is_symlink() or not manifest.is_file():
            raise CaptureSealError(f'{folder.name}: no regular sealed manifest')
        try:
            recorded = json.loads(manifest.read_text(), object_pairs_hook=_unique_pairs)
        except (OSError, ValueError) as error:
            raise CaptureSealError(f'{folder.name}: unreadable sha256 manifest') from error
        if not isinstance(recorded, dict) or not recorded:
            raise CaptureSealError(f'{folder.name}: empty or invalid sha256 manifest')
        signed_files = set(recorded)
        present = {p.name for p in folder.iterdir() if p.name != manifest.name}
        if signed_files != present:
            raise CaptureSealError(f'{folder.name}: missing or unsealed evidence files: {sorted(signed_files ^ present)}')
        for filename, digest in recorded.items():
            if (not isinstance(filename, str) or filename in ('.', '..') or '/' in filename or
                '\\' in filename or not isinstance(digest, str) or
                re.fullmatch(r'[0-9a-f]{64}', digest) is None):
                raise CaptureSealError(f'{folder.name}: malformed sealed entry')
            file = folder / filename
            if file.is_symlink() or not file.is_file():
                raise CaptureSealError(f'{folder.name}: non-regular evidence: {filename}')
            before = file.stat()
            actual = hashlib.sha256(file.read_bytes()).hexdigest()
            after = file.stat()
            if (actual != digest or before.st_size != after.st_size or
                before.st_mtime_ns != after.st_mtime_ns):
                raise CaptureSealError(f'{folder.name}: post-seal mutation: {filename}')
    print(f'GP_U_CAPTURE_SEALS_RECHECKED directories={len(expected)}', flush=True)
    return len(expected)
