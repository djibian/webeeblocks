"""Run the extracted Windows U assembly in real Webots, without a GUI claim.

This is test tooling, not a pupil launcher. No package byte, world, controller,
oracle or timeout is changed. Retain native traces and the exact ordinary AST.
"""
import argparse
from contextlib import ExitStack, contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import shutil
import socket
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.grand_prix.layout_u import generate
from tools.ci.test_grand_prix_windows_project import verify


def read(path):
    return path.read_text(encoding='utf-8', errors='replace') if path.exists() else ''


def validate(directory, seed):
    rows = [json.loads(line) for line in read(directory / 'events.jsonl').splitlines()]
    if any(row['event'] in ('error', 'wall-timeout', 'transport-error') for row in rows):
        raise ValueError('Installed witness reported an execution/transport failure')
    programs = [row['detail'] for row in rows if row['event'] == 'program']
    outcomes = [row['detail'] for row in rows if row['event'] == 'outcome']
    if len(programs) != 1 or len(outcomes) != 1 or outcomes[0].get('status') != 'achieved':
        raise ValueError('Exactly one program and successful shared-backend outcome required')
    text = read(directory / 'webots.stdout.log') + '\n' + read(directory / 'webots.stderr.log')
    if any(line.startswith('ERROR:') for line in text.splitlines()) or 'Traceback (most recent call last)' in text:
        raise ValueError('Native Webots/controller error')
    records = [json.loads(line.split('GP_U_RESULT ', 1)[1]) for line in text.splitlines()
               if line.startswith('GP_U_RESULT ')]
    result = json.loads((directory / 'native-result-1.json').read_text(encoding='utf-8'))
    layout = generate(seed)
    if (len(records) != 1 or records[0] != result or result['status'] != 'achieved' or
            result['configuration'] != layout.identifier or result['attempt'] != 1 or
            result['crossings'] != len(layout.gates) or
            not isinstance(result['seconds'], (int, float)) or isinstance(result['seconds'], bool) or
            not math.isfinite(result['seconds']) or not 0 < result['seconds'] < 210):
        raise ValueError('Missing, inconsistent or failed exact native outcome')
    # The unchanged world oracle checks route, altitude, crossings and pose. Keep
    # its actual trace/diagnostic too, rather than treating a Node exit as PASS.
    diagnostic = json.loads((directory / 'native-diagnostic-1.json').read_text(encoding='utf-8'))
    if diagnostic['crossings'] != len(layout.gates) or diagnostic['landing_target'] != list(layout.landing_target(len(layout.gates))):
        raise ValueError('Wrong native crossing/landing subject')
    trace = directory / 'native_trace.csv'
    if not trace.is_file() or trace.stat().st_size < 100:
        raise ValueError('Native trajectory evidence missing')
    result['ast_sha256'] = hashlib.sha256(json.dumps(programs[0], sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return result


def _filter_windows_tree(rows, root_pid, watched=()):
    """Bounded process-identity evidence; NEVER a successful-cleanup oracle."""
    if (not isinstance(rows, list) or len(rows) > 4096 or len(watched) > 64 or
            type(root_pid) is not int or root_pid <= 0 or
            any(type(pid) is not int or pid <= 0 for pid in watched)):
        raise ValueError('Windows process snapshot is malformed or too large')
    by_pid = {}
    system_idle_excluded = 0
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('Malformed process row')
        pid, parent = row.get('ProcessId'), row.get('ParentProcessId')
        # Win32_Process includes the reserved System Idle Process (PID 0).
        # It can never belong to a launched positive-PID tree. Its parent is
        # commonly 0 or null; reject any purported positive parent instead.
        # Only this well-defined system row may be omitted. A malformed
        # positive-PID row remains UNAVAILABLE, never evidence of cleanup.
        if type(pid) is int and pid == 0:
            if parent is not None and (type(parent) is not int or parent != 0):
                raise ValueError('Malformed System Idle Process parent')
            system_idle_excluded += 1
            if system_idle_excluded > 1:
                raise ValueError('Duplicate System Idle Process rows')
            continue
        if type(pid) is not int or type(parent) is not int or pid <= 0 or parent < 0:
            raise ValueError('Malformed process identifiers')
        created = row.get('CreationDate')
        if created is not None and not isinstance(created, str):
            raise ValueError('Malformed process creation identity')
        if isinstance(created, str) and not created.strip():
            created = None
        if pid in by_pid:
            raise ValueError('Duplicate process PID in CIM inventory')
        by_pid[pid] = dict(pid=pid, parent=parent, created=created,
                           name=str(row.get('Name', ''))[:128])
    owned = {root_pid}
    for _ in range(65):
        new = owned | {r['pid'] for r in by_pid.values() if r['parent'] in owned}
        if len(new) > 64:
            raise ValueError('Windows process tree exceeds diagnostic bound')
        if new == owned:
            break
        owned = new
    else:
        raise ValueError('Windows process tree did not converge')
    return dict(available=True, root_present=root_pid in by_pid,
                excluded_system_idle_rows=system_idle_excluded,
                owned=[by_pid[pid] for pid in sorted(owned) if pid in by_pid],
                watched=[by_pid[pid] for pid in sorted(set(watched))
                         if pid in by_pid])


def _windows_process_snapshot(root_pid, watched=()):
    """Observe process parent PID and creation identity via native Windows CIM.

    A Toolhelp/CIM snapshot can race child creation and is NOT proof of total
    extinction. Preserve both snapshots; never use them to excuse taskkill.
    """
    if sys.platform != 'win32':
        return {'available': False, 'error': 'Windows-only observation'}
    try:
        command = ("$ErrorActionPreference='Stop'; "
                   "Get-CimInstance Win32_Process | "
                   "Select-Object ProcessId,ParentProcessId,CreationDate,Name | "
                   "ConvertTo-Json -Compress -Depth 3")
        result = subprocess.run(
            ['powershell.exe', '-NoLogo', '-NoProfile', '-NonInteractive',
             '-Command', command], stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, check=True, timeout=15)
        if len(result.stdout) > 512000:
            raise ValueError('Process inventory exceeds diagnostic byte bound')
        rows = json.loads(result.stdout.decode('utf-8-sig', errors='replace'))
        if isinstance(rows, dict):
            rows = [rows]
        return _filter_windows_tree(rows, root_pid, watched)
    except (OSError, subprocess.SubprocessError, ValueError, UnicodeError) as error:
        return {'available': False,
                'error': (type(error).__name__ + ': ' + str(error))[:512]}


def _attempt_cleanup(failures, action, *args, **kwargs):
    try:
        action(*args, **kwargs)
    except BaseException as error:
        # Defer propagation until the other owned resources are released.
        failures.append(error)


class _Win32CloseSigintGuard:
    """Install before acquiring Win32 handles; restore only after both releases.

    Outside the tiny close section, forward SIGINT to the original Python
    handler. While armed, record rather than raise it; replay after closure.
    Installing/restoring signal handlers with an owned raw handle would merely
    relocate the original race. All ownership and closure is main-thread only.
    """

    def __init__(self):
        if threading.current_thread() is not threading.main_thread():
            raise RuntimeError('Win32 handle owner requires the Python main thread')
        self._previous = signal.getsignal(signal.SIGINT)
        self._armed = False
        self._restored = False
        self._pending = []
        signal.signal(signal.SIGINT, self._receive)

    def _receive(self, signum, frame):
        if self._armed:
            self._pending.append((signum, frame))
        elif callable(self._previous):
            self._previous(signum, frame)
        elif self._previous != signal.SIG_IGN:
            raise KeyboardInterrupt()

    def arm(self):
        # No CloseHandle has started here. A SIGINT delivered immediately
        # before the armed assignment is safe to record and retry; bound the
        # transition rather than retrying a potentially completed CloseHandle.
        for _ in range(3):
            try:
                self._armed = True
                return
            except KeyboardInterrupt:
                self._pending.append((signal.SIGINT, None))
        raise RuntimeError('Cannot attest SIGINT protection for Win32 close')

    def restore(self):
        if self._restored:
            return
        # Both handles have been attempted before this point. Even if restoring
        # the OS handler fails, disarm the forwarding shim: never leave SIGINT
        # silently deferred forever. Preserve both restoration and delivery
        # failures for the caller instead of hiding one.
        restoration_error = None
        try:
            signal.signal(signal.SIGINT, self._previous)
            self._restored = True
        except BaseException as error:
            restoration_error = error
        finally:
            self._armed = False
        pending, self._pending = self._pending, []
        if pending:
            signum, frame = pending[0]
            try:
                if callable(self._previous):
                    self._previous(signum, frame)
                elif self._previous == signal.SIG_DFL:
                    if restoration_error is None:
                        signal.raise_signal(signum)
                    else:
                        raise KeyboardInterrupt('Deferred SIGINT after failed restoration')
                # SIG_IGN retains its original ignored semantics.
            except BaseException as error:
                if restoration_error is None:
                    raise
                restoration_error.add_note(
                    f'Deferred SIGINT delivery: {type(error).__name__}: {error}')
        if restoration_error is not None:
            raise restoration_error


def _attempt_owned_win32_close(failures, process, action, state_name):
    """Bounded pre-call recovery; NEVER retry a native call with unknown outcome."""
    state = getattr(process, state_name, None)
    if not isinstance(state, str):  # Existing portable mock witnesses.
        _attempt_cleanup(failures, action)
        return
    for _ in range(3):
        if getattr(process, state_name) != 'owned':
            return
        _attempt_cleanup(failures, action)
    if getattr(process, state_name) == 'owned':
        failures.append(RuntimeError(f'{state_name}: no Win32 close call attested'))


def _error_detail(error):
    return f'{type(error).__name__}: {error}'


def _write_cleanup_diagnostic(path, evidence):
    path.write_text(json.dumps(evidence, sort_keys=True, indent=2) + '\n',
                    encoding='utf-8')


def stop(process, diagnostic_path=None, launch_snapshot=None):
    if process is None:
        return
    status = process.poll()
    if status is not None and status != 0:
        raise RuntimeError(
            f'Owned Windows PID {process.pid} exited unexpectedly: '
            f'process={status!r}'
        )
    already_exited = status == 0
    # The auxiliary Node probe is reaped by its own wait/exit contract and
    # has no Webots descendant-cleanup claim. Only the Webots path supplies
    # diagnostic_path and MUST attest its descendants, even after exit=0.
    if already_exited and diagnostic_path is None:
        return
    # Diagnostic only. Unchanged decision: taskkill failure with nonzero exit
    # must still FAIL, regardless of textual SUCCESS or a vanishing PID.
    evidence = {'schema': 'webeeblocks-windows-owned-cleanup-v1',
                'root_pid': process.pid,
                'snapshot_limitations': 'Not an exhaustive process-lifetime monitor'}
    if diagnostic_path is not None:
        # If the root already exited, a new snapshot cannot retrospectively
        # establish which processes were its descendants. Use the census
        # collected while this exact Popen handle was still live, or fail shut.
        evidence['before'] = (
            launch_snapshot if launch_snapshot is not None else
            {'available': False, 'error': 'No launch-time process identity'}
        ) if already_exited else _windows_process_snapshot(process.pid)
        if already_exited:
            evidence['root_exit_at_stop'] = 0
    failures = []
    try:
        if not already_exited:
            try:
                result = subprocess.run(
                    ['taskkill', '/PID', str(process.pid), '/T', '/F'], check=True,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=20)
                evidence['taskkill_returncode'] = result.returncode
                output = result.stdout or b''
            except subprocess.CalledProcessError as failure:
                evidence['taskkill_returncode'] = failure.returncode
                output = failure.output or b''
                evidence['taskkill_output'] = (
                    output.decode('utf-8', errors='replace') if isinstance(output, bytes)
                    else str(output))[:16384]
                evidence['taskkill_output_truncated'] = len(output) > 16384
                status_error = None
                try:
                    status = process.poll()
                    if status is None:
                        try:
                            status = process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            status = None
                except BaseException as error:
                    status_error = error
                evidence['process_after_taskkill'] = status
                # A nonzero taskkill result is ambiguous even when the root has
                # exited cleanly. Neither exit=0 nor a SUCCESS message proves
                # the owned descendants were retired.
                detail = output.decode('utf-8', errors='replace') if isinstance(
                    output, bytes) else str(output)
                error = RuntimeError(
                    f'Owned Windows PID {process.pid} cleanup unproven: '
                    f'taskkill={failure.returncode}, process={status!r}, '
                    f'output={detail[-512:]!r}'
                )
                if status_error is not None:
                    error.add_note(f'Observing Webots exit after taskkill failed: {_error_detail(status_error)}')
                raise error from failure
            if diagnostic_path is not None and 'taskkill_output' not in evidence:
                evidence['taskkill_output'] = (
                    output.decode('utf-8', errors='replace') if isinstance(output, bytes)
                    else str(output))[:16384]
                evidence['taskkill_output_truncated'] = len(output) > 16384
            evidence['wait_returncode'] = process.wait(timeout=20)
    except BaseException as error:
        failures.append(error)
    if diagnostic_path is not None:
        _attempt_cleanup(failures, _attest_windows_cleanup, process, evidence,
                         no_prior_error=not failures)
        if failures:
            evidence.setdefault('exception', _error_detail(failures[0])[:750])
            secondary = [*getattr(failures[0], '__notes__', ()),
                         *map(_error_detail, failures[1:])]
            if secondary:
                evidence['secondary_errors'] = secondary
        _attempt_cleanup(failures, _write_cleanup_diagnostic, diagnostic_path, evidence)
    if failures:
        primary, *secondary = failures
        for error in secondary:
            primary.add_note(_error_detail(error))
        raise primary


def _attest_windows_cleanup(process, evidence, *, no_prior_error):
    before = evidence.get('before', {})
    watched = [x['pid'] for x in before.get('owned', [])]
    after = _windows_process_snapshot(process.pid, watched)
    evidence['after'] = after
    if before.get('available') and after.get('available'):
        old = {(p['pid'], p['created']) for p in before['owned']
               if p['created'] is not None}
        evidence['still_present_same_pid_and_creation'] = [
            p for p in after['watched']
            if (p['pid'], p['created']) in old]
        evidence['identity_unproven'] = [
            p['pid'] for p in before['owned'] if p['created'] is None]
        # A child spawned after the initial census can survive the
        # root. The CIM ancestry traversal intentionally starts from
        # root_pid even when that root has already disappeared.
        evidence['untracked_owned_after_cleanup'] = [
            p for p in after.get('owned', [])
            if p['pid'] != process.pid and
            (p['pid'], p['created']) not in old]
    # Positive evidence of a surviving child is a veto. Missing
    # before/after CIM evidence or a missing creation identity is
    # independently inconclusive: do not report a safe retirement.
    # Neither two snapshots nor taskkill's SUCCESS text prove full
    # process-lifetime monitoring; keep that limitation explicit.
    survivors = evidence.get('still_present_same_pid_and_creation', [])
    untracked = evidence.get('untracked_owned_after_cleanup', [])
    gaps = []
    if not before.get('available'):
        gaps.append('before-snapshot-unavailable')
    else:
        # A syntactically valid CIM inventory can still omit the
        # process known live at the initial poll. Without its identity
        # we cannot attribute descendants or prove their retirement.
        # Fallback only supports older tests supplying owned rows.
        root_seen = before.get('root_present')
        if root_seen is None:
            root_seen = any(p.get('pid') == process.pid
                            for p in before.get('owned', []))
        if root_seen is not True:
            gaps.append('before-root-identity-unavailable')
    if not after.get('available'):
        gaps.append('after-snapshot-unavailable')
    if evidence.get('identity_unproven'):
        gaps.append('creation-identity-unavailable')
    if before.get('available') and after.get('available'):
        old_pids = {p['pid'] for p in before['owned']}
        if any(p['pid'] in old_pids and not p.get('created')
               for p in after['watched']):
            gaps.append('after-creation-identity-unavailable')
    evidence['cleanup_observation_gaps'] = gaps
    # Only an atomic-at-launch job can account for a late descendant
    # whose parent has already disappeared from both CIM snapshots.
    active = None
    try:
        count = process.active_job_processes()
        if type(count) is not int or count < 0:
            raise ValueError('Invalid Webots job process count')
        active = count
    except (AttributeError, OSError, ValueError) as error:
        evidence['job_accounting_error'] = str(error)[:512]
    evidence['job_active_processes'] = active
    survivor_veto = bool(survivors) and no_prior_error
    untracked_veto = bool(untracked) and no_prior_error
    observation_veto = bool(gaps) and no_prior_error
    job_veto = active != 0 and no_prior_error
    if survivor_veto:
        evidence['exception'] = (
            'RuntimeError: observed same-identity owned descendants survived cleanup')
    elif untracked_veto:
        evidence['exception'] = (
            'RuntimeError: post-census descendants still present; ancestry unproven')
    elif observation_veto:
        evidence['exception'] = (
            'RuntimeError: owned process cleanup observation unavailable')
    elif job_veto:
        evidence['exception'] = (
            f'RuntimeError: owned job cleanup unproven: active processes={active!r}')
    if survivor_veto:
        raise RuntimeError(
            f'Owned Windows PID {process.pid} cleanup unproven: '
            f'{len(survivors)} same-identity descendants survived')
    if untracked_veto:
        raise RuntimeError(
            f'Owned Windows PID {process.pid} cleanup unproven: '
            f'{len(untracked)} post-census descendants still present')
    if observation_veto:
        raise RuntimeError(
            f'Owned Windows PID {process.pid} cleanup observation unavailable: '
            + ', '.join(gaps))
    if job_veto:
        raise RuntimeError(
            f'Owned Windows PID {process.pid} job cleanup unproven: '
            f'active processes={active!r}')


if sys.platform == 'win32':
    import _winapi
    import ctypes as c
    from ctypes import wintypes as w
    import msvcrt


    class _StartupInfo(c.Structure):
        _fields_ = [
            ('cb', w.DWORD), ('lpReserved', w.LPWSTR), ('lpDesktop', w.LPWSTR),
            ('lpTitle', w.LPWSTR), ('dwX', w.DWORD), ('dwY', w.DWORD),
            ('dwXSize', w.DWORD), ('dwYSize', w.DWORD), ('dwXCountChars', w.DWORD),
            ('dwYCountChars', w.DWORD), ('dwFillAttribute', w.DWORD),
            ('dwFlags', w.DWORD), ('wShowWindow', w.WORD), ('cbReserved2', w.WORD),
            ('lpReserved2', c.c_void_p), ('hStdInput', w.HANDLE),
            ('hStdOutput', w.HANDLE), ('hStdError', w.HANDLE),
        ]


    class _StartupInfoEx(c.Structure):
        _fields_ = [('StartupInfo', _StartupInfo), ('lpAttributeList', c.c_void_p)]


    class _ProcessInformation(c.Structure):
        _fields_ = [('hProcess', w.HANDLE), ('hThread', w.HANDLE),
                    ('dwProcessId', w.DWORD), ('dwThreadId', w.DWORD)]


    class _BasicLimits(c.Structure):
        _fields_ = [
            ('PerProcessUserTimeLimit', c.c_longlong), ('PerJobUserTimeLimit', c.c_longlong),
            ('LimitFlags', w.DWORD), ('MinimumWorkingSetSize', c.c_size_t),
            ('MaximumWorkingSetSize', c.c_size_t), ('ActiveProcessLimit', w.DWORD),
            ('Affinity', c.c_size_t), ('PriorityClass', w.DWORD), ('SchedulingClass', w.DWORD),
        ]


    class _ExtendedLimits(c.Structure):
        _fields_ = [
            ('BasicLimitInformation', _BasicLimits), ('IoInfo', c.c_ulonglong * 6),
            ('ProcessMemoryLimit', c.c_size_t), ('JobMemoryLimit', c.c_size_t),
            ('PeakProcessMemoryUsed', c.c_size_t), ('PeakJobMemoryUsed', c.c_size_t),
        ]


    class _Accounting(c.Structure):
        _fields_ = [
            ('TotalUserTime', c.c_longlong), ('TotalKernelTime', c.c_longlong),
            ('ThisPeriodTotalUserTime', c.c_longlong), ('ThisPeriodTotalKernelTime', c.c_longlong),
            ('TotalPageFaultCount', w.DWORD), ('TotalProcesses', w.DWORD),
            ('ActiveProcesses', w.DWORD), ('TotalTerminatedProcesses', w.DWORD),
        ]


    _kernel = c.WinDLL('kernel32', use_last_error=True)


    def _win32(name, result, *arguments):
        function = getattr(_kernel, name)
        function.restype = result
        function.argtypes = arguments
        return function


    _create_job = _win32('CreateJobObjectW', w.HANDLE, c.c_void_p, w.LPCWSTR)
    _set_job = _win32('SetInformationJobObject', w.BOOL, w.HANDLE, c.c_int, c.c_void_p, w.DWORD)
    _query_job = _win32('QueryInformationJobObject', w.BOOL, w.HANDLE, c.c_int,
                        c.c_void_p, w.DWORD, c.POINTER(w.DWORD))
    _init_attributes = _win32('InitializeProcThreadAttributeList', w.BOOL,
                              c.c_void_p, w.DWORD, w.DWORD, c.POINTER(c.c_size_t))
    _update_attribute = _win32('UpdateProcThreadAttribute', w.BOOL, c.c_void_p,
                               w.DWORD, c.c_size_t, c.c_void_p, c.c_size_t, c.c_void_p, c.c_void_p)
    _delete_attributes = _win32('DeleteProcThreadAttributeList', None, c.c_void_p)
    _create_process = _win32('CreateProcessW', w.BOOL, w.LPCWSTR, w.LPWSTR, c.c_void_p,
                            c.c_void_p, w.BOOL, w.DWORD, c.c_void_p, w.LPCWSTR,
                            c.POINTER(_StartupInfoEx), c.POINTER(_ProcessInformation))

    _JOB_OBJECT_BASIC_ACCOUNTING_INFORMATION = 1
    _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
    _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
    _PROC_THREAD_ATTRIBUTE_HANDLE_LIST = 0x20002
    _PROC_THREAD_ATTRIBUTE_JOB_LIST = 0x2000D
    _EXTENDED_STARTUPINFO_PRESENT = 0x00080000
    _CREATE_UNICODE_ENVIRONMENT = 0x00000400
    _STARTF_USESTDHANDLES = 0x100


    def _check(result, operation):
        if not result:
            code = c.get_last_error()
            raise OSError(None, f'{operation}: {c.FormatError(code).strip()}', None, code)
        return result


    def _start(command, cwd, env, job, handles):
        # The kernel assigns the job in CreateProcessW before any Webots code can
        # run. No suspended-process or post-Popen assignment window is needed.
        job_list = (w.HANDLE * 1)(job)
        handle_list = (w.HANDLE * len(handles))(*handles)
        size = c.c_size_t()
        _init_attributes(None, 2, 0, c.byref(size))  # first call obtains the size
        attributes = c.create_string_buffer(size.value)
        _check(_init_attributes(attributes, 2, 0, c.byref(size)), 'InitializeProcThreadAttributeList')
        try:
            _check(_update_attribute(attributes, 0, _PROC_THREAD_ATTRIBUTE_JOB_LIST,
                                     job_list, c.sizeof(job_list), None, None), 'Set job list')
            _check(_update_attribute(attributes, 0, _PROC_THREAD_ATTRIBUTE_HANDLE_LIST,
                                     handle_list, c.sizeof(handle_list), None, None), 'Set pipe handle list')
            startup = _StartupInfoEx()
            startup.StartupInfo.cb = c.sizeof(startup)
            startup.StartupInfo.dwFlags = _STARTF_USESTDHANDLES
            startup.StartupInfo.hStdInput, startup.StartupInfo.hStdOutput, startup.StartupInfo.hStdError = handles
            startup.lpAttributeList = c.cast(attributes, c.c_void_p)
            info = _ProcessInformation()
            line = c.create_unicode_buffer(subprocess.list2cmdline(command))
            environment = c.create_unicode_buffer('\0'.join(
                f'{key}={env[key]}' for key in sorted(env, key=str.upper)) + '\0\0')
            _check(_create_process(command[0], line, None, None, True,
                                   _EXTENDED_STARTUPINFO_PRESENT | _CREATE_UNICODE_ENVIRONMENT,
                                   environment, str(cwd), c.byref(startup), c.byref(info)),
                   'CreateProcessW in Webots job')
            return info
        finally:
            _delete_attributes(attributes)


    class WindowsJobProcess:
        """Own the private job and the original process handle independently of PIDs."""

        def __init__(self, command, cwd, env):
            self.args = command
            self.returncode = None
            self._job = self._process = None
            self._job_close_state = self._process_close_state = 'not-owned'
            # The guard is installed BEFORE either raw handle exists; it
            # forwards ordinary SIGINT until the actual release section.
            self._close_sigint = _Win32CloseSigintGuard()
            with ExitStack() as launch, ExitStack() as writers:
                launch.callback(self._close_sigint.restore)
                # Anonymous, non-inheritable job. Neither breakaway flag is set.
                self._job = _check(_create_job(None, None), 'CreateJobObjectW')
                self._job_close_state = 'owned'
                launch.callback(self.close_job)
                limits = _ExtendedLimits()
                limits.BasicLimitInformation.LimitFlags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
                _check(_set_job(self._job, _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
                                c.byref(limits), c.sizeof(limits)), 'Set job limits')
                child_stdin = writers.enter_context(open(os.devnull, 'rb'))
                child_streams = [child_stdin]
                readers = []
                for _ in range(2):
                    read_fd, write_fd = os.pipe()
                    readers.append(launch.enter_context(os.fdopen(read_fd, 'rb')))
                    child_streams.append(writers.enter_context(os.fdopen(write_fd, 'wb')))
                handles = [msvcrt.get_osfhandle(stream.fileno()) for stream in child_streams]
                for handle in handles:
                    os.set_handle_inheritable(handle, True)
                info = _start(command, cwd, env, self._job, handles)
                self._process = info.hProcess
                self._process_close_state = 'owned'
                launch.callback(self.close_process)
                _winapi.CloseHandle(info.hThread)
                self.pid = info.dwProcessId
                self.stdout, self.stderr = readers
                writers.close()
                launch.pop_all()

        def poll(self):
            if self.returncode is None and self._process is not None:
                if _winapi.WaitForSingleObject(self._process, 0) == _winapi.WAIT_OBJECT_0:
                    self.returncode = _winapi.GetExitCodeProcess(self._process)
            return self.returncode

        def wait(self, timeout):
            if _winapi.WaitForSingleObject(self._process, int(timeout * 1000)) == _winapi.WAIT_TIMEOUT:
                raise subprocess.TimeoutExpired(self.args, timeout)
            self.returncode = _winapi.GetExitCodeProcess(self._process)
            return self.returncode

        def active_job_processes(self):
            accounting = _Accounting()
            _check(_query_job(self._job, _JOB_OBJECT_BASIC_ACCOUNTING_INFORMATION,
                              c.byref(accounting), c.sizeof(accounting), None), 'Query Webots job accounting')
            return accounting.ActiveProcesses

        def _close_once(self, attribute, state_attribute):
            state = getattr(self, state_attribute)
            if state == 'closed' or state == 'not-owned':
                return
            if state != 'owned':
                raise RuntimeError(f'{attribute} CloseHandle outcome is unverified; no retry')
            self._close_sigint.arm()
            handle = getattr(self, attribute)
            # A failure after entering the native operation cannot prove
            # whether the kernel closed this value. Do not risk double-close
            # of a recycled Windows handle; explicitly fail the attestation.
            setattr(self, state_attribute, 'in-call')
            try:
                _winapi.CloseHandle(handle)
            except BaseException as error:
                setattr(self, state_attribute, 'uncertain')
                raise RuntimeError(f'{attribute} CloseHandle outcome unverified') from error
            setattr(self, state_attribute, 'closed')
            setattr(self, attribute, None)

        def close_job(self):
            # The last Job handle terminates all remaining members.
            self._close_once('_job', '_job_close_state')

        def close_process(self):
            try:
                if self._process_close_state == 'owned':
                    self.poll()
            finally:
                self._close_once('_process', '_process_close_state')


def engine_environment(home, ambient):
    # os.environ is case-insensitive on Windows; its plain copied dict is not.
    env = {key.upper(): value for key, value in ambient.items()}
    if not env.get('SYSTEMROOT'):
        raise ValueError('Windows SYSTEMROOT is required for native DLL lookup')
    system = Path(env['SYSTEMROOT'])
    env['PATH'] = os.pathsep.join(str(p) for p in (
        home / 'msys64/mingw64/bin', home / 'msys64/mingw64/bin/cpp',
        home / 'msys64/usr/bin', system / 'System32', system))
    env['QT_ENABLE_HIGHDPI_SCALING'] = '1'
    env.pop('QT_QPA_PLATFORM_PLUGIN_PATH', None)
    return env


@contextmanager
def captured_engine(command, cwd, env, stdout_path, stderr_path):
    # R2025a gui/main.cpp RedirectIOToConsole retains redirected handles only
    # for FILE_TYPE_PIPE. A disk handle makes it reopen CONOUT$, losing logs.
    # Drain both pipes concurrently, including while waiting for READY/results.
    errors = []
    def drain(source, target):
        try:
            with source:
                while chunk := source.read1(65536):
                    target.write(chunk)
                    target.flush()
        except Exception as error:
            errors.append(error)

    windows = sys.platform == 'win32'
    diagnostic_path = stdout_path.parent / 'webots-process-cleanup.json' if windows else None
    failures = []
    with ExitStack() as logs:
        try:
            stdout = stdout_path.open('wb')
            logs.callback(_attempt_cleanup, failures, stdout.close)
            stderr = stderr_path.open('wb')
            logs.callback(_attempt_cleanup, failures, stderr.close)
            if windows:
                process = WindowsJobProcess(command, cwd, env)
            else:
                process = subprocess.Popen(command, cwd=cwd, env=env,
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            launch_snapshot = None
            started = []
            try:
                # The live root handle brackets the launch identity observation.
                if windows and process.poll() is None:
                    launch_snapshot = _windows_process_snapshot(process.pid)
                    if process.poll() is not None:
                        launch_snapshot = {'available': False,
                                           'error': 'Root exited during launch identity observation'}
                for source, target in ((process.stdout, stdout), (process.stderr, stderr)):
                    thread = threading.Thread(target=drain, args=(source, target), daemon=True)
                    thread.start()
                    started.append(thread)
                yield process
            except BaseException as error:
                failures.append(error)
            finally:
                try:
                    _attempt_cleanup(failures, stop, process, diagnostic_path=diagnostic_path,
                                     launch_snapshot=launch_snapshot)
                finally:
                    # Release BOTH handles back-to-back, before pipe joins.
                    # SIGINT is deferred only across these actual operations,
                    # then replayed with the original handler. Nested finally
                    # ensures even a failed Job close cannot skip process close.
                    if windows:
                        guard = getattr(process, '_close_sigint', None)
                        try:
                            if isinstance(guard, _Win32CloseSigintGuard):
                                # Arm before invoking either closure so an
                                # interrupt at method entry is also deferred.
                                _attempt_cleanup(failures, guard.arm)
                            _attempt_owned_win32_close(
                                failures, process, process.close_job, '_job_close_state')
                        finally:
                            try:
                                _attempt_owned_win32_close(
                                    failures, process, process.close_process,
                                    '_process_close_state')
                            finally:
                                if isinstance(guard, _Win32CloseSigintGuard):
                                    _attempt_cleanup(failures, guard.restore)
                for thread in started:
                    _attempt_cleanup(failures, thread.join, timeout=20)
                for source in (process.stdout, process.stderr)[len(started):]:
                    _attempt_cleanup(failures, source.close)
                if any(thread.is_alive() for thread in started):
                    failures.append(RuntimeError('Native output pipes did not close after process cleanup'))
                for error in errors:
                    failure = RuntimeError(f'Native output capture failed: {error}')
                    failure.__cause__ = error
                    failures.append(failure)
        except BaseException as error:
            failures.append(error)
    if failures:
        primary, *secondary = failures
        for error in secondary:
            primary.add_note(_error_detail(error))
            for note in getattr(error, '__notes__', ()):
                primary.add_note(note)
        if diagnostic_path is not None:
            try:
                record = json.loads(read(diagnostic_path) or '{}')
                record.setdefault('exception', _error_detail(primary))
                record['primary_exception'] = _error_detail(primary)
                record['secondary_errors'] = list(getattr(primary, '__notes__', ()))
                _write_cleanup_diagnostic(diagnostic_path, record)
            except BaseException as error:
                primary.add_note(f'Updating Webots cleanup diagnostic failed: {_error_detail(error)}')
        raise primary


def trial(package, home, output, seed):
    directory = output / f'seed-{seed}'
    directory.mkdir()
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    env = engine_environment(home, os.environ)
    node_exe = shutil.which('node')
    # Reproduce R2025a launcher.c's DLL environment, then start its exact
    # engine directly so redirected handles and the exit code remain ours.
    # Bound PATH as in the other Windows native probes; no ambient Python/DLL
    # installation is a dependency of the extracted project.
    env.update(WEBOTS_HOME=str(home), WEBEEBLOCKS_GP_PYTHON_DIR=str(package / 'runtime/python'),
               WEBEEBLOCKS_CI_ARTIFACT_DIR=str(directory),
               WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE='true')
    # Prove selection of the embedded interpreter, not ambient Python lookup.
    env['PYTHONHOME'] = str(directory / 'absent ambient Python')
    env['PYTHONPATH'] = env['PYTHONHOME']
    engine = str(home / 'msys64/mingw64/bin/webots-bin.exe')
    command = [engine, '--stdout', '--stderr', '--batch', '--mode=fast',
               '--no-rendering', f'--port={port}',
               str(package / f'worlds/grand_prix_u_seed{seed}.wbt')]
    metadata = dict(command=command, cwd=str(package), path=env['PATH'],
                    source_sha=(package / 'SOURCE_SHA').read_text().strip(),
                    node_executable=node_exe, webots_exit=None, node_exit=None,
                    mesa_gl_version=env.get('MESA_GL_VERSION_OVERRIDE'),
                    software_gl=env.get('LIBGL_ALWAYS_SOFTWARE'))
    webots = node = None
    try:
        try:
            diagnostic = subprocess.run([engine, '--sysinfo'], cwd=package,
                env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=20)
            metadata['sysinfo_exit'] = diagnostic.returncode
            (directory / 'sysinfo.log').write_bytes(diagnostic.stdout)
        except subprocess.TimeoutExpired as error:
            metadata['sysinfo_timeout'] = True
            (directory / 'sysinfo.log').write_bytes(error.output or b'')
        with captured_engine(command, package, env,
                directory / 'webots.stdout.log', directory / 'webots.stderr.log') as webots, \
                (directory / 'node.log').open('w', encoding='utf-8') as node_log:
            deadline = time.monotonic() + 60
            while True:
                logs = read(directory / 'webots.stdout.log') + read(directory / 'webots.stderr.log')
                if webots.poll() is not None:
                    raise RuntimeError(f'Installed Webots exited before native readiness: {webots.returncode} (0x{webots.returncode & 0xffffffff:08x})')
                if 'WEBEEBLOCKS_RUNTIME_V2 READY' in logs:
                    break
                if time.monotonic() >= deadline:
                    raise RuntimeError('Installed native readiness not established')
                time.sleep(.1)
            node = subprocess.Popen([node_exe, str(ROOT / 'tools/ci/grand_prix_u_node_probe.js'),
                str(port), 'witness', str(directory / 'events.jsonl'), str(package)],
                cwd=ROOT, env=env, stdout=node_log, stderr=subprocess.STDOUT)
            if node.wait(timeout=600) != 0:
                raise RuntimeError('Installed shared-runtime probe failed')
            deadline = time.monotonic() + 10
            while (not (directory / 'native-result-1.json').exists() or
                   'GP_U_RESULT ' not in read(directory / 'webots.stdout.log') + read(directory / 'webots.stderr.log')):
                if webots.poll() is not None or time.monotonic() >= deadline:
                    raise RuntimeError('Native evaluator did not retain its result')
                time.sleep(.1)
    finally:
        try:
            metadata['node_exit'] = node.poll() if node else None
            metadata['webots_exit'] = webots.poll() if webots else None
            stop(node)
        finally:
            # captured_engine already retired Webots once. Do not reinterpret
            # an intentional taskkill exit as a spontaneous crash on retry.
            (directory / 'launch.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
    result = validate(directory, seed)
    (directory / 'result.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--package', required=True, type=Path)
    parser.add_argument('--webots-home', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if sys.platform != 'win32' or not shutil.which('node'):
        raise RuntimeError('Real Windows Webots R2025a and Node 22+ required')
    package, home, output = (p.resolve() for p in (args.package, args.webots_home, args.output))
    if (home / 'resources/version.txt').read_text(encoding='utf-8').strip() != 'R2025a':
        raise ValueError('Wrong Webots version')
    sha = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
    if (package / 'SOURCE_SHA').read_text(encoding='utf-8').strip() != sha:
        raise ValueError('Wrong installed source SHA')
    verify(package)
    output.mkdir(parents=True, exist_ok=False)
    results = []
    try:
        for seed in (0, 1, 4):
            result = trial(package, home, output, seed)
            if results and result['ast_sha256'] != results[0]['ast_sha256']:
                raise ValueError('Student AST changed between installed configurations')
            results.append(result)
            (output / 'campaign.json').write_text(json.dumps({'source_sha': sha, 'results': results}, indent=2) + '\n', encoding='utf-8')
        print('PASS real Windows R2025a installed assembly, same Blockly AST across 1/2/3 H; GUI workflow/pedagogical acceptance not established')
    finally:
        files = {p.relative_to(output).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in output.rglob('*') if p.is_file() and p.name != 'sha256.json'}
        (output / 'sha256.json').write_text(json.dumps(files, sort_keys=True, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
