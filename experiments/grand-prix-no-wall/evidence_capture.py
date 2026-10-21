#!/usr/bin/env python3
"""Experimental #655 proof closure and fail-closed atomic archiving (Linux)."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import tarfile
import tempfile
import time


class EvidenceError(RuntimeError):
    """Evidence capture is incomplete; never a verdict on the native mission."""


def _group_members(pgid):
    """Live non-zombie members of a known Linux start_new_session group."""
    if not Path('/proc/self/stat').is_file():
        raise EvidenceError('Linux /proc required for process attestation')
    members = []
    for entry in Path('/proc').iterdir():
        if not entry.name.isdecimal():
            continue
        try:
            fields = (entry / 'stat').read_text().rsplit(')', 1)[1].split()
        except (FileNotFoundError, ProcessLookupError):
            continue
        except PermissionError as error:
            raise EvidenceError('cannot inspect process membership') from error
        if int(fields[2]) == pgid and fields[0] not in ('Z', 'X'):
            members.append(int(entry.name))
    return members


def stop_writer_groups(children, *, grace=5.0, kill_grace=5.0):
    """Drain all known process groups, not just their Popen leaders."""
    groups = list(dict.fromkeys(child.pid for child in children))

    def send(pgid, sig):
        if _group_members(pgid):
            try:
                os.killpg(pgid, sig)
            except ProcessLookupError:
                pass

    try:
        for pgid in reversed(groups):
            send(pgid, signal.SIGTERM)
        deadline = time.monotonic() + grace
        while any(_group_members(pgid) for pgid in groups) and time.monotonic() < deadline:
            time.sleep(.025)
        for pgid in reversed(groups):
            send(pgid, signal.SIGKILL)
        deadline = time.monotonic() + kill_grace
        while any(_group_members(pgid) for pgid in groups) and time.monotonic() < deadline:
            time.sleep(.025)
        remaining = {pgid: _group_members(pgid) for pgid in groups if _group_members(pgid)}
        if remaining:
            raise EvidenceError(f'known writer groups still alive: {remaining}')
    finally:
        for child in children:
            try:
                child.wait(timeout=1)
            except subprocess.TimeoutExpired as error:
                raise EvidenceError(f'direct writer remains alive: {child.pid}') from error
    return [{'pgid': child.pid, 'returncode': child.returncode} for child in children]


def _open_writer_fds(folder):
    """Same-UID processes with write-enabled FDs under this capture directory."""
    root = str(folder.resolve()) + os.sep
    writers = []
    for entry in Path('/proc').iterdir():
        if not entry.name.isdecimal():
            continue
        try:
            if entry.stat().st_uid != os.geteuid():
                continue
            for handle in (entry / 'fd').iterdir():
                try:
                    target = os.readlink(handle)
                    if not target.startswith(root):
                        continue
                    flags = (entry / 'fdinfo' / handle.name).read_text().splitlines()
                    line = next((s for s in flags if s.startswith('flags:')), None)
                    if line is None:
                        raise EvidenceError('cannot attest FD flags')
                    if (int(line.split()[1], 8) & os.O_ACCMODE) in (os.O_WRONLY, os.O_RDWR):
                        writers.append((int(entry.name), handle.name, target))
                except (FileNotFoundError, ProcessLookupError):
                    continue
        except (FileNotFoundError, ProcessLookupError):
            continue
        except PermissionError as error:
            raise EvidenceError('cannot inspect same-UID output descriptors') from error
    return writers


def _files(folder):
    if not folder.is_dir() or folder.is_symlink():
        raise EvidenceError('source must be a real directory')
    entries = {}
    for path in folder.iterdir():
        if not path.is_file() or path.is_symlink() or not stat.S_ISREG(path.lstat().st_mode):
            raise EvidenceError(f'non-regular source entry: {path.name}')
        entries[path.name] = path
    if not entries:
        raise EvidenceError('empty evidence set')
    return dict(sorted(entries.items()))


def _hash(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def close_capture(children, streams, folder):
    """End known writers, close parent streams, then seal a single inventory."""
    folder = Path(folder)
    try:
        exits = stop_writer_groups(children)
    finally:
        for stream in streams:
            stream.close()
    if any(not stream.closed for stream in streams):
        raise EvidenceError('parent output stream still open')
    writers = _open_writer_fds(folder)
    if writers:
        raise EvidenceError(f'untracked writable evidence descriptors: {writers}')
    if (folder / 'capture-seal.json').exists() or (folder / 'sha256.json').exists():
        raise EvidenceError('refusing to rewrite an existing capture seal')
    (folder / 'capture-seal.json').write_text(json.dumps({
        'schema': 1, 'known_writer_groups_exited': True,
        'parent_output_streams_closed': True,
        'no_same_uid_writable_evidence_fds': True,
        'writer_leaders': exits,
        'scope': 'known start_new_session groups and same-UID FDs only'
    }, sort_keys=True, indent=2) + '\n')
    inventory = _files(folder)
    (folder / 'sha256.json').write_text(json.dumps(
        {name: _hash(path) for name, path in inventory.items()},
        sort_keys=True, indent=2) + '\n')


def _snapshot(folder):
    paths = _files(folder)
    if 'sha256.json' not in paths or 'capture-seal.json' not in paths:
        raise EvidenceError('missing completed capture seal or manifest')
    try:
        seal = json.loads(paths['capture-seal.json'].read_text())
        manifest = json.loads(paths['sha256.json'].read_text())
    except (ValueError, UnicodeError) as error:
        raise EvidenceError('invalid seal or manifest') from error
    if (not isinstance(seal, dict) or seal.get('known_writer_groups_exited') is not True
        or seal.get('parent_output_streams_closed') is not True
        or seal.get('no_same_uid_writable_evidence_fds') is not True):
        raise EvidenceError('capture is not attested closed')
    if not isinstance(manifest, dict) or set(manifest) != set(paths) - {'sha256.json'}:
        raise EvidenceError('manifest does not exactly enumerate captured files')
    if any(not isinstance(h, str) or re.fullmatch('[0-9a-f]{64}', h) is None
           for h in manifest.values()):
        raise EvidenceError('malformed SHA-256 manifest')
    hashes = {name: _hash(path) for name, path in paths.items()}
    if any(hashes[name] != expected for name, expected in manifest.items()):
        raise EvidenceError('source bytes do not match capture manifest')
    return paths, hashes


def _read_archive(archive, folder_name, hashes):
    expected = {f'{folder_name}/{name}': digest for name, digest in hashes.items()}
    seen = {}
    with tarfile.open(archive, 'r:xz') as handle:
        for member in handle:
            if not member.isfile() or member.name not in expected or member.name in seen:
                raise EvidenceError(f'unexpected/duplicate archive member: {member.name}')
            payload = handle.extractfile(member)
            if payload is None:
                raise EvidenceError(f'unreadable archive member: {member.name}')
            digest = hashlib.sha256()
            for block in iter(lambda: payload.read(1024 * 1024), b''):
                digest.update(block)
            seen[member.name] = digest.hexdigest()
    if seen != expected:
        raise EvidenceError('archive missing members or source/archive digest disagreement')


def archive_capture(source, destination, *, hook=None):
    """Validate and publish a no-clobber archive; hook is test-only."""
    source, destination = Path(source), Path(destination)
    if source.resolve() == destination.resolve() or source.resolve() in destination.resolve().parents:
        raise EvidenceError('archive must reside outside the capture directory')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', source.name):
        raise EvidenceError('invalid capture directory name')
    paths, hashes = _snapshot(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() or destination.is_symlink():
        raise EvidenceError('published archive already exists; no overwrite')
    fd, temporary = tempfile.mkstemp(prefix=f'.{destination.name}.', suffix='.partial',
                                     dir=destination.parent)
    try:
        with os.fdopen(fd, 'wb') as output:
            with tarfile.open(fileobj=output, mode='w:xz', format=tarfile.PAX_FORMAT) as archive:
                for name, path in paths.items():
                    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
                    with os.fdopen(os.open(path, flags), 'rb') as stream:
                        metadata = os.fstat(stream.fileno())
                        if not stat.S_ISREG(metadata.st_mode):
                            raise EvidenceError('source replaced by non-regular file')
                        info = tarfile.TarInfo(f'{source.name}/{name}')
                        info.size = metadata.st_size
                        info.mode = 0o444
                        info.mtime = 0
                        archive.addfile(info, stream)
            output.flush()
            os.fsync(output.fileno())
        if hook:
            hook('after_write')
        _read_archive(temporary, source.name, hashes)
        if hook:
            hook('after_verify')
        changed_paths, changed_hashes = _snapshot(source)
        if set(changed_paths) != set(paths) or changed_hashes != hashes:
            raise EvidenceError('source changed during archiving')
        _read_archive(temporary, source.name, hashes)
        os.chmod(temporary, 0o444)
        with open(temporary, 'rb') as handle:
            os.fsync(handle.fileno())
        os.link(temporary, destination)
        directory_fd = os.open(destination.parent, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        return {'archive': str(destination), 'bytes': destination.stat().st_size,
                'sha256': _hash(destination), 'members': len(hashes)}
    finally:
        Path(temporary).unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path, help='trial directory sealed by a runner')
    parser.add_argument('archive', type=Path, help='new .tar.xz output (no overwrite)')
    args = parser.parse_args()
    print(json.dumps(archive_capture(args.source, args.archive), sort_keys=True))


if __name__ == '__main__':
    main()
