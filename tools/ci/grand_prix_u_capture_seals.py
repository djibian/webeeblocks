"""Fail closed when a native Grand Prix trial changed after sha256.json was written.

This is a late recheck, not a producer/descendant lifetime guarantee. It cannot
prevent writes after the last check; #656 explores stronger writer retirement.
"""
import hashlib
import json
from pathlib import Path
import re


class CaptureSealError(RuntimeError):
    pass


def verify_new_capture_seals(root, baseline):
    """Recheck every trial created in this invocation, including camera probes."""
    root = Path(root)
    trial_dirs = sorted(p for p in root.iterdir() if p.is_dir()
                        and p.name.startswith('gp-u-v1-') and p.name not in baseline)
    if not trial_dirs:
        raise CaptureSealError('no new native trial directory to verify')
    for folder in trial_dirs:
        manifest = folder / 'sha256.json'
        if manifest.is_symlink() or not manifest.is_file():
            raise CaptureSealError(f'{folder.name}: no regular sealed manifest')
        try:
            recorded = json.loads(manifest.read_text())
        except (OSError, ValueError) as error:
            raise CaptureSealError(f'{folder.name}: unreadable sha256 manifest') from error
        if not isinstance(recorded, dict) or not recorded:
            raise CaptureSealError(f'{folder.name}: empty or invalid sha256 manifest')
        expected = set(recorded)
        present = {p.name for p in folder.iterdir() if p.name != manifest.name}
        if expected != present:
            raise CaptureSealError(f'{folder.name}: missing or unsealed evidence files: {sorted(expected ^ present)}')
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
    print(f'GP_U_CAPTURE_SEALS_RECHECKED directories={len(trial_dirs)}', flush=True)
    return len(trial_dirs)
