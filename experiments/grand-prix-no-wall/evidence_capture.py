#!/usr/bin/env python3
"""Experimental #655 proof closure and fail-closed atomic archiving (Linux)."""
import argparse
from contextlib import contextmanager
import sys
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


def _note(error, message):
    # Ubuntu 22.04 / Python 3.10 has no BaseException.add_note yet.
    if callable(getattr(error, 'add_note', None)):
        error.add_note(message)
    else:
        error.capture_notes = (*getattr(error, 'capture_notes', ()), message)
        try:
            print('CAPTURE_DIAGNOSTIC ' + message, file=sys.stderr, flush=True)
        except BaseException as logging_error:
            error.capture_note_write_errors = (*getattr(error, 'capture_note_write_errors', ()), logging_error)


# Intentionally no PID translation: procfs must expose the calling PID namespace.
PROC = Path('/proc')


def _stat(path):
    raw = path.read_text()
    pid, rest = raw.split(' (', 1)
    f = rest.rsplit(')', 1)[1].split()
    return {'pid': int(pid), 'state': f[0], 'ppid': int(f[1]),
            'pgid': int(f[2]), 'sid': int(f[3]), 'birth': int(f[19])}


def _status(path):
    return dict(line.split(':', 1) for line in path.read_text().splitlines() if ':' in line)


def qualify_procfs():
    """Fail before spawn/scan/signal if identity or visibility is unqualified.

    The runner must be single-threaded, SIGCHLD default, with no other reaper,
    ptracer or concurrent namespace/mount/credential mutation. This is a bounded
    local runner contract, not protection against privileged hostile actors.
    """
    try:
        own = _stat(PROC / 'self/stat')
        status = _status(PROC / 'self/status')
        if (own['pid'] != os.getpid() or
            tuple(map(int, status['NSpid'].split())) != (os.getpid(),) or
            int(status['NSpgid']) != os.getpgrp() or int(status['NSsid']) != os.getsid(0)):
            raise EvidenceError('procfs/syscall PID namespace divergence; no mapping supported')
        namespace = os.readlink(PROC / 'self/ns/pid')
        if (os.readlink(PROC / '1/ns/pid') != namespace or
            os.readlink(PROC / 'self/ns/pid_for_children') != namespace):
            raise EvidenceError('procfs namespace visibility or future children namespace differs')
        if (len(list((PROC / 'self/task').iterdir())) != 1 or
            signal.getsignal(signal.SIGCHLD) != signal.SIG_DFL):
            raise EvidenceError('single-threaded runner with default SIGCHLD required')
        if any(int(uid) != os.geteuid() for uid in status['Uid'].split()):
            raise EvidenceError('uniform real/effective/saved/fs UID required')
        mounts = [line.split() for line in (PROC / 'self/mountinfo').read_text().splitlines()]
        mounts = [f for f in mounts if f[4] == str(PROC)]
        if len(mounts) != 1:
            raise EvidenceError('cannot qualify procfs mount visibility')
        mount = mounts[0]
        separator = mount.index('-')
        options = ','.join((mount[5], mount[separator + 3])).split(',')
        if (mount[3] != '/' or mount[separator + 1] != 'proc' or
            any(o.startswith('hidepid=') and o != 'hidepid=0' for o in options)):
            raise EvidenceError('restricted procfs visibility')
        return {'pid_namespace': namespace, 'uid': os.geteuid(),
                'procfs_pid': own['pid'], 'nspid': [own['pid']]}
    except (OSError, ValueError, KeyError, IndexError) as error:
        raise EvidenceError('cannot qualify procfs identity/permissions') from error


def observe_exit(child):
    """Observe without harvesting the direct child or freeing its PID/PGID."""
    if getattr(child, '_capture_registration_error', None) is not None:
        raise EvidenceError('writer registration failed; no signal permitted') from child._capture_registration_error
    if child.returncode is not None:
        raise EvidenceError(f'leader already reaped: {child.pid}')
    try:
        result = os.waitid(os.P_PID, child.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
    except ChildProcessError as error:
        raise EvidenceError(f'leader no longer owned/unreaped: {child.pid}') from error
    if result is None:
        return None
    if result.si_pid != child.pid or result.si_uid != os.geteuid():
        raise EvidenceError('waitid child identity/UID mismatch')
    return result.si_status if result.si_code == os.CLD_EXITED else -result.si_status


def wait_writer(child, timeout):
    deadline = time.monotonic() + timeout
    while True:
        code = observe_exit(child)
        if code is not None:
            return code
        if time.monotonic() >= deadline:
            raise subprocess.TimeoutExpired(child.args, timeout)
        time.sleep(.025)


def _leader_identity(child, domain):
    # WNOWAIT first: an already harvested/reused numeric PID is never authority.
    observe_exit(child)
    try:
        entry = PROC / str(child.pid)
        info, status = _stat(entry / 'stat'), _status(entry / 'status')
        if (info['pid'] != child.pid or info['ppid'] != os.getpid() or
            info['pgid'] != child.pid or info['sid'] != child.pid or
            tuple(map(int, status['NSpid'].split())) != (child.pid,) or
            int(status['NSpgid']) != child.pid or int(status['NSsid']) != child.pid or
            any(int(uid) != domain['uid'] for uid in status['Uid'].split()) or
            os.getpgid(child.pid) != child.pid or os.getsid(child.pid) != child.pid):
            raise EvidenceError('leader identity/group/session/UID mismatch')
        # Zombie namespace links may be unavailable. Ownership + singleton NSpid
        # in the qualified procfs still bind the retained zombie's namespace.
        if info['state'] not in ('Z', 'X') and os.readlink(entry / 'ns/pid') != domain['pid_namespace']:
            raise EvidenceError('leader PID namespace changed')
        return {k: info[k] for k in ('pid', 'ppid', 'pgid', 'sid', 'birth')} | domain
    except (OSError, ValueError, KeyError, IndexError) as error:
        raise EvidenceError('cannot qualify retained leader') from error


def spawn_writer(args, **kwargs):
    domain = qualify_procfs()  # Before Popen: unsupported hosts create no writer.
    child = subprocess.Popen(args, start_new_session=True, **kwargs)
    # Retain ownership even if procfs registration fails; caller appends the child
    # immediately. close_capture will refuse signalling an unqualified identity.
    child._capture_domain = domain
    try:
        child._capture_identity = _leader_identity(child, domain)
    except BaseException as error:
        child._capture_registration_error = error
    return child


def _group_members(pgid, domain=None):
    """Only compare syscall PGIDs in a qualified, fully visible procfs."""
    domain = qualify_procfs() if domain is None else domain
    members = []
    for entry in PROC.iterdir():
        if not entry.name.isdecimal():
            continue
        try:
            info = _stat(entry / 'stat')
            if info['pgid'] == pgid:
                status = _status(entry / 'status')
                if (info['sid'] != pgid or int(status['NSpgid']) != pgid or
                    int(status['NSsid']) != pgid or
                    tuple(map(int, status['NSpid'].split())) != (info['pid'],) or
                    any(int(uid) != domain['uid'] for uid in status['Uid'].split())):
                    raise EvidenceError('group member identity/namespace/UID mismatch')
                if info['state'] not in ('Z', 'X'):
                    members.append(int(entry.name))
        except (FileNotFoundError, ProcessLookupError):
            continue
        except (OSError, ValueError, KeyError, IndexError) as error:
            raise EvidenceError('cannot inspect process membership') from error
    return members


def stop_writer_groups(children, *, grace=5.0, kill_grace=5.0):
    """Keep direct session leaders unreaped until every known group is drained."""
    domain = qualify_procfs()
    identities = {}
    for child in children:
        identity = _leader_identity(child, domain)
        previous = getattr(child, '_capture_identity', identity)
        if identity != previous or getattr(child, '_capture_domain', domain) != domain:
            raise EvidenceError('retained leader birth/namespace changed')
        child._capture_identity = identity
        identities[child.pid] = identity

    def members(child):
        if qualify_procfs() != domain or _leader_identity(child, domain) != identities[child.pid]:
            raise EvidenceError('retained leader identity changed before scan/signal')
        return _group_members(child.pid, domain)

    def send(child, sig):
        if members(child):
            # Revalidate AFTER scanning and immediately before killpg. The direct
            # session leader is still owned and unreaped; its PID cannot be reused.
            # WNOWAIT alone would not suffice with SIGCHLD=IGN, another reaper,
            # namespace mismatch, or an arbitrary (non-session-leader) child.
            if qualify_procfs() != domain or _leader_identity(child, domain) != identities[child.pid]:
                raise EvidenceError('unqualified signal identity')
            try:
                os.killpg(child.pid, sig)
            except ProcessLookupError:
                pass

    for sig, budget in ((signal.SIGTERM, grace), (signal.SIGKILL, kill_grace)):
        for child in reversed(children):
            send(child, sig)
        deadline = time.monotonic() + budget
        while any(members(child) for child in children) and time.monotonic() < deadline:
            time.sleep(.025)
    if any(members(child) for child in children):
        raise EvidenceError('known writer groups still alive')
    # No signals or scans keyed by these PIDs after this point. Reap ONLY after
    # all groups have been established empty, not in an exception's finally.
    exits = []
    for child in children:
        wait_writer(child, 1)
        child.wait(timeout=1)
        exits.append({'identity': identities[child.pid], 'returncode': child.returncode})
    return exits


@contextmanager
def preserve_errors(primary=None):
    """Attempt every cleanup, retaining primary exception object and traceback."""
    errors = []
    def attempt(action):
        try:
            return action()
        except BaseException as error:
            errors.append(error)
    try:
        yield attempt
    finally:
        if errors:
            if primary is not None:
                primary.capture_cleanup_errors = (*getattr(primary, 'capture_cleanup_errors', ()), *errors)
                for error in errors:
                    _note(primary, f'capture/cleanup: {type(error).__name__}: {error}')
            else:
                first, *rest = errors
                first.capture_cleanup_errors = (*getattr(first, 'capture_cleanup_errors', ()), *rest)
                for error in rest:
                    _note(first, f'additional cleanup: {type(error).__name__}: {error}')
                raise first


def _open_writer_fds(folder):
    """Same-UID processes with write-enabled FDs under this capture directory."""
    root = str(folder.resolve()) + os.sep
    writers = []
    for entry in PROC.iterdir():
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
    # Keep group and stream errors together; never seal after either failure.
    # A native error is preserved by the runner's outer preserve_errors scope.
    with preserve_errors() as attempt:
        exits = attempt(lambda: stop_writer_groups(children))
        for stream in streams:
            attempt(stream.close)
    if any(not stream.closed for stream in streams):
        raise EvidenceError('parent output stream still open')
    writers = _open_writer_fds(folder)
    if writers:
        raise EvidenceError(f'untracked writable evidence descriptors: {writers}')
    if (folder / 'capture-seal.json').exists() or (folder / 'sha256.json').exists():
        raise EvidenceError('refusing to rewrite an existing capture seal')
    (folder / 'capture-seal.json').write_text(json.dumps({
        'schema': 2, 'known_writer_groups_exited': True,
        'procfs_domain': qualify_procfs(),
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
    if (not isinstance(seal, dict) or seal.get('schema') != 2
        or not isinstance(seal.get('procfs_domain'), dict)
        or seal.get('known_writer_groups_exited') is not True
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
    publication_attempted = False
    publication_error = None
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
        publication_attempted = True
        try:
            os.link(temporary, destination)
        except FileExistsError:
            publication_attempted = False  # This atomic operation made no link.
            raise
        if hook:
            hook('after_link')
        directory_fd = os.open(destination.parent, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
        directory_error = None
        try:
            os.fsync(directory_fd)
        except BaseException as error:
            directory_error = error
            raise
        finally:
            with preserve_errors(directory_error) as attempt:
                attempt(lambda: os.close(directory_fd))
        return {'archive': str(destination), 'bytes': destination.stat().st_size,
                'sha256': _hash(destination), 'members': len(hashes)}
    except BaseException as error:
        publication_error = error
        if publication_attempted:
            error.publication_uncertain = True
            error.archive_destination = str(destination)
            _note(error, f'publication attempted: {destination}; inspect before retry; no rollback')
        raise
    finally:
        with preserve_errors(publication_error) as attempt:
            def remove_temporary():
                try:
                    Path(temporary).unlink(missing_ok=True)
                except BaseException as error:
                    if publication_attempted:
                        error.publication_uncertain = True
                        error.archive_destination = str(destination)
                        _note(error, 'archive link may exist; temporary cleanup failed; inspect before retry')
                    raise
            attempt(remove_temporary)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--qualify', action='store_true', help='qualify host without starting writers; exit 77 on refusal')
    parser.add_argument('source', nargs='?', type=Path, help='trial directory sealed by a runner')
    parser.add_argument('archive', nargs='?', type=Path, help='new .tar.xz output (no overwrite)')
    args = parser.parse_args()
    if args.qualify:
        try:
            domain = qualify_procfs()
            # Verify membership scan and same-UID FD visibility without signals.
            _group_members(-1, domain)
            _open_writer_fds(Path('/__gp_capture_qualification_no_output__'))
        except (EvidenceError, OSError) as error:
            print(json.dumps({'capture_host': 'REFUSED', 'reason': str(error)}, sort_keys=True))
            raise SystemExit(77)
        print(json.dumps({'capture_host': 'QUALIFIED', 'domain': domain}, sort_keys=True))
        return
    if args.source is None or args.archive is None:
        parser.error('source and archive required without --qualify')
    print(json.dumps(archive_capture(args.source, args.archive), sort_keys=True))


if __name__ == '__main__':
    main()
