"""Read-only Linux process evidence and sealed archives; no READY oracle.

Record both procfs and syscall PIDs: they need not be in the same namespace.
Sampling cannot supply missed execs, complete descendant exit statuses or a stack.
Those gaps must remain explicit until a debugger/OS tracing backend supplies them.
"""
import hashlib
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import time
import zipfile

GRAPHICS_ENV = (
    'DISPLAY', 'WAYLAND_DISPLAY', 'LIBGL_ALWAYS_SOFTWARE', 'LIBGL_DRIVERS_PATH',
    'MESA_LOADER_DRIVER_OVERRIDE', 'GALLIUM_DRIVER', 'MESA_GL_VERSION_OVERRIDE',
    'MESA_GLSL_VERSION_OVERRIDE', 'LP_NUM_THREADS', 'LD_LIBRARY_PATH', 'LD_PRELOAD',
    'QT_QPA_PLATFORM', 'QT_PLUGIN_PATH', 'QT_OPENGL', 'QT_XCB_GL_INTEGRATION',
    'QT_ENABLE_HIGHDPI_SCALING', 'WEBOTS_HOME', 'WEBOTS_TMPDIR',
    'WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE', 'XDG_RUNTIME_DIR',
    'XDG_CONFIG_HOME', 'XDG_CACHE_HOME', 'XDG_CURRENT_DESKTOP',
)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    try:
        return Path(path).read_text()
    except OSError as error:
        return {'unavailable': str(error)}


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def proc_record(proc_pid):
    """A procfs identity, checked for exit/reuse across the read."""
    root = Path('/proc') / str(proc_pid)
    first = (root / 'stat').read_text()
    fields = first[first.rfind(')') + 2:].split()
    status = (root / 'status').read_text()
    namespaces = dict(line.split(':', 1) for line in status.splitlines() if ':' in line)
    record = {
        'proc_pid': int(first.split(' ', 1)[0]), 'proc_ppid': int(fields[1]),
        'state': fields[0], 'start_ticks': int(fields[19]),
        'nspid': [int(n) for n in namespaces.get('NSpid', '').split()],
        'pid_namespace': os.readlink(root / 'ns/pid'),
        'status': status, 'cmdline': (root / 'cmdline').read_bytes().replace(b'\0', b' ').decode(errors='replace'),
    }
    try:
        record['exe'] = os.readlink(root / 'exe')
    except OSError as error:
        record['exe_unavailable'] = str(error)
    last = (root / 'stat').read_text()
    last_fields = last[last.rfind(')') + 2:].split()
    if fields[19] != last_fields[19]:
        raise ProcessLookupError('PID reused during observation')
    return record


def identity(record):
    return (record['proc_pid'], record['start_ticks'])


def own_tree(known):
    """Discover descendants of already known identities, never by name alone.

    /proc/PID/task/TID/children is absent on some hosts. PPid traversal is the
    fallback; unrelated process details are never returned or archived.
    """
    table = {}
    for path in Path('/proc').iterdir():
        if path.name.isdigit():
            try:
                r = proc_record(int(path.name))
                table[r['proc_pid']] = r
            except (OSError, ValueError):
                pass
    selected = {pid: table[pid] for pid, ticks in known
                if pid in table and table[pid]['start_ticks'] == ticks}
    while True:
        extra = {pid: r for pid, r in table.items()
                 if pid not in selected and r['proc_ppid'] in selected}
        if not extra:
            return list(selected.values())
        selected.update(extra)


def environment():
    return {
        'observed_utc_ns': time.time_ns(), 'uname': list(os.uname()),
        'boot_id': read('/proc/sys/kernel/random/boot_id'),
        'clock_ticks_per_second': os.sysconf('SC_CLK_TCK'),
        'proc_stat': read('/proc/stat'), 'uptime': read('/proc/uptime'),
        'self_syscall_pid': os.getpid(), 'self_proc_pid': int(os.readlink('/proc/self')),
        'self_status': read('/proc/self/status'),
        'graphics_environment': {k: os.environ.get(k) for k in GRAPHICS_ENV},
        'core_pattern': read('/proc/sys/kernel/core_pattern'),
        'self_limits': read('/proc/self/limits'),
        'memory': memory(),
    }


def snapshot_process(proc_pid, expected_start_ticks, expected_exe_sha256, out):
    """Snapshot a previously identified process, preferably debugger-stopped.

    Caller must resolve the procfs PID at an exec/stop event. This is not an
    attach operation, liveness test, process-name search or stack acquisition.
    """
    before = proc_record(proc_pid)
    root = Path('/proc') / str(proc_pid)
    if before['start_ticks'] != expected_start_ticks or digest(root / 'exe') != expected_exe_sha256:
        raise ProcessLookupError('process identity or executable mismatch')
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    write_json(out / 'identity.json', before)
    for name in ('stat', 'status', 'maps', 'smaps_rollup', 'limits', 'cgroup'):
        write_json(out / (name + '.json'), read(root / name))
    try:
        env = dict(entry.split('=', 1) for entry in (root / 'environ').read_bytes().decode(errors='replace').split('\0') if '=' in entry)
        write_json(out / 'graphics-environment.json', {k: env.get(k) for k in GRAPHICS_ENV})
    except OSError as error:
        write_json(out / 'graphics-environment.json', {'unavailable': str(error)})
    maps = read(root / 'maps')
    objects = {}
    for line in maps.splitlines() if isinstance(maps, str) else []:
        fields = line.split(None, 5)
        if len(fields) != 6 or not fields[5].startswith('/'):
            continue
        path = fields[5]
        if path in objects:
            continue
        entry = {'mapped_device': fields[3], 'mapped_inode': int(fields[4])}
        objects[path] = entry
        try:
            target = root / 'root' / path.lstrip('/')
            with target.open('rb') as stream:
                stat = os.fstat(stream.fileno())
                dev = '%x:%x' % (os.major(stat.st_dev), os.minor(stat.st_dev))
                expected_dev = ':'.join('%x' % int(n, 16) for n in fields[3].split(':'))
                if stat.st_ino != entry['mapped_inode'] or dev != expected_dev:
                    raise ValueError('path does not identify the mapped inode/device')
                h = hashlib.sha256()
                for block in iter(lambda: stream.read(1024 * 1024), b''):
                    h.update(block)
                after_stat = os.fstat(stream.fileno())
                if (stat.st_size, stat.st_mtime_ns) != (after_stat.st_size, after_stat.st_mtime_ns):
                    raise ValueError('mapped object file changed during hashing')
                entry.update(sha256=h.hexdigest(), size=stat.st_size)
                try:
                    notes = subprocess.run(['readelf', '-n', '/proc/self/fd/' + str(stream.fileno())],
                                           pass_fds=(stream.fileno(),), capture_output=True, text=True, timeout=10)
                    entry['build_id_lines'] = [l.strip() for l in notes.stdout.splitlines() if 'Build ID:' in l]
                    entry['readelf_returncode'] = notes.returncode
                except (OSError, subprocess.TimeoutExpired) as error:
                    entry['build_id_unavailable'] = str(error)
        except (OSError, ValueError) as error:
            entry['unavailable'] = str(error)
    write_json(out / 'loaded-objects.json', objects)
    write_json(out / 'memory.json', memory())
    after = proc_record(proc_pid)
    if identity(before) != identity(after) or digest(root / 'exe') != expected_exe_sha256:
        raise ProcessLookupError('process exited, reused or execed during snapshot')
    write_json(out / 'snapshot.json', {
        'boot_id': read('/proc/sys/kernel/random/boot_id'), 'identity': identity(before),
        'exe_sha256': expected_exe_sha256, 'state_before': before['state'], 'state_after': after['state'],
        'claim': 'observed-process-and-mapped-object-files; not a core or a stack',
    })
    return objects


def memory():
    # Preserve raw membership and limits. The mount may cover other processes;
    # an OOM counter delta is not automatically attributed to the native target.
    paths = ['/proc/meminfo', '/proc/pressure/memory', '/proc/self/cgroup',
             '/proc/self/mountinfo', '/sys/fs/cgroup/memory.events',
             '/sys/fs/cgroup/memory.current', '/sys/fs/cgroup/memory.peak',
             '/sys/fs/cgroup/memory.max', '/sys/fs/cgroup/memory.swap.max']
    return {p: read(p) for p in paths}


def observe(command, out, timeout=5):
    """Bounded sampler used by fixtures, explicitly insufficient for admission."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    write_json(out / 'environment.json', environment())
    self_record = proc_record(int(os.readlink('/proc/self')))
    known = {identity(self_record)}
    births = {}
    timeline = []
    pidfd = None
    with (out / 'process.log').open('w') as stream:
        child = subprocess.Popen(command, stdout=stream, stderr=subprocess.STDOUT,
                                 start_new_session=True)
        try:
            try:
                pidfd = os.pidfd_open(child.pid)
            except (AttributeError, OSError):
                pass
            deadline = time.monotonic() + timeout
            while child.poll() is None and time.monotonic() < deadline:
                rows = own_tree(known)
                known.update(identity(r) for r in rows)
                owned = [r for r in rows if identity(r) != identity(self_record)]
                for record in owned:
                    key = '%s-%s' % identity(record)
                    if key not in births:
                        births[key] = record
                        root = Path('/proc') / str(record['proc_pid'])
                        write_json(out / (key + '.json'), record)
                        for name in ('maps', 'limits', 'cgroup'):
                            write_json(out / (key + '-' + name + '.json'), read(root / name))
                        try:
                            write_json(out / (key + '-exe.json'), {'sha256': digest(root / 'exe')})
                        except OSError as error:
                            write_json(out / (key + '-exe.json'), {'unavailable': str(error)})
                timeline.append({'monotonic_ns': time.monotonic_ns(), 'utc_ns': time.time_ns(),
                                 'processes': [{k: r[k] for k in ('proc_pid', 'start_ticks', 'nspid', 'state')}
                                               for r in owned],
                                 'launcher_pidfd_exited': bool(pidfd is not None and
                                                              select.select([pidfd], [], [], 0)[0])})
                time.sleep(.02)
            timed_out = child.poll() is None
            if timed_out:
                # The unreaped Popen child pins this process-group ID here.
                os.killpg(child.pid, signal.SIGTERM)
            try:
                code = child.wait(timeout=2)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                code = child.wait(timeout=2)
        finally:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait(timeout=2)
            if pidfd is not None:
                os.close(pidfd)
    result = {
        'command': [str(x) for x in command], 'launcher_syscall_pid': child.pid,
        'launcher_returncode': code, 'launcher_signal': -code if code < 0 else None,
        'termination_requested_by_capture': timed_out,
        'process_births': births, 'timeline': timeline, 'memory_after': memory(),
        'claim': 'sampled-process-observation-only',
        'limitations': ['execs or short-lived descendants may be missed',
                        'non-child exit statuses are unknown without tracing',
                        'a living wrapper is not a living native process',
                        'initial maps are not a complete loaded-library inventory'],
    }
    write_json(out / 'result.json', result)
    return result


def seal(directory, destination):
    """Only after all writers have been retired. Atomic availability after reopen."""
    directory, destination = Path(directory).resolve(), Path(destination).resolve()
    if destination.is_relative_to(directory) or destination.exists():
        raise ValueError('new archive must be outside the evidence directory')
    files = sorted(p for p in directory.rglob('*') if p.is_file())
    if any(p.is_symlink() for p in directory.rglob('*')):
        raise ValueError('symlink in evidence')
    manifest = {p.relative_to(directory).as_posix(): digest(p) for p in files}
    if 'manifest.json' in manifest:
        raise ValueError('manifest already present')
    write_json(directory / 'manifest.json', manifest)
    temporary = destination.with_suffix(destination.suffix + '.partial')
    try:
        with zipfile.ZipFile(temporary, 'x', zipfile.ZIP_DEFLATED) as archive:
            for p in files + [directory / 'manifest.json']:
                archive.write(p, p.relative_to(directory).as_posix())
        with zipfile.ZipFile(temporary) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)) or set(names) != set(manifest) | {'manifest.json'}:
                raise ValueError('archive member inventory mismatch')
            if json.loads(archive.read('manifest.json')) != manifest:
                raise ValueError('archive manifest mismatch')
            for name, sha in manifest.items():
                if hashlib.sha256(archive.read(name)).hexdigest() != sha or digest(directory / name) != sha:
                    raise ValueError('source/archive content changed: ' + name)
        current = {p.relative_to(directory).as_posix() for p in directory.rglob('*') if p.is_file()}
        if current != set(manifest) | {'manifest.json'} or any(p.is_symlink() for p in directory.rglob('*')):
            raise ValueError('source inventory changed during sealing')
        # Atomic publication without replacing an independently created archive.
        os.link(temporary, destination)
        temporary.unlink()
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return digest(destination)
