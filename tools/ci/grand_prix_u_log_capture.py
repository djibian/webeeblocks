"""Bounded single-writer Webots log capture for native trial evidence.

Webots and its descendants inherit only a pipe, not the durable log file.
After cleanup, pipe EOF proves those process handles are closed before seal.
This is not a generic descendant-lifetime or other-file guarantee (#656).
"""
import os
from pathlib import Path
import signal
import threading


class NativeLogCapture:
    def __init__(self, path):
        self.path = Path(path)
        self._target = self.path.open('xb')
        try:
            read_fd, write_fd = os.pipe()
        except BaseException:
            self._target.close()
            raise
        self._read_fd = read_fd
        self._write = os.fdopen(write_fd, 'wb', buffering=0)
        self._thread = None
        self._error = None

    def fileno(self):
        return self._write.fileno()

    def __enter__(self):
        if self._thread is not None:
            raise RuntimeError('native stdout capture already started')
        self._thread = threading.Thread(target=self._collect, name='webots-stdout', daemon=True)
        self._thread.start()
        return self

    def __exit__(self, _type, _value, _traceback):
        self._write.close()  # Parent relinquishes its pipe; descendants may still hold it.

    def _collect(self):
        try:
            while True:
                block = os.read(self._read_fd, 65536)
                if not block:
                    break
                self._target.write(block)
                self._target.flush()  # READY/result readers see incremental bytes.
        except Exception as error:
            self._error = error
        finally:
            os.close(self._read_fd)
            self._target.close()

    def finish(self, timeout=8):
        if self._thread is None or not self._write.closed:
            raise RuntimeError('native stdout capture not closed; refuse seal')
        self._thread.join(timeout)
        if self._thread.is_alive():
            raise RuntimeError('native stdout descendants still hold pipe; refuse seal')
        if self._error is not None:
            raise RuntimeError('native stdout capture failed; refuse seal') from self._error


# A native test may have emitted its required result *before* teardown.
# Recognize allocator/abort diagnostics too; a result alone is not a healthy exit.
# Do not classify Webots' ambiguous "controller crashed" warning as fatal: an
# intentionally SIGTERM'd internal evaluator can produce that message (#665).
_FATAL_OUTPUT = (
    'Segmentation fault',
    'Traceback (most recent call last)',
    'Aborted (core dumped)',
    'double free or corruption',
    'corrupted size vs. prev_size',
    'corrupted double-linked list',
    'stack smashing detected',
    'AddressSanitizer:DEADLYSIGNAL',
    'terminate called after throwing an instance',
    'Fatal Python error:',
    'Fatal glibc error:',
    'malloc():',
    'free():',
    'munmap_chunk():',
)
_FATAL_SIGNAL_NUMBERS = frozenset(
    int(getattr(signal, name)) for name in
    ('SIGABRT', 'SIGBUS', 'SIGFPE', 'SIGILL', 'SIGSEGV')
    if hasattr(signal, name)
)


def require_no_terminal_crash(path):
    """Refuse a native fatal marker even after the mission result was recorded."""
    text = Path(path).read_text(errors='replace')
    if any(marker in text for marker in _FATAL_OUTPUT):
        raise RuntimeError('native crash reported at stdout retirement; refuse seal')


def require_no_fatal_exit_statuses(children):
    """Refuse fatal direct-child exits, including 128+signal from shell wrappers.

    SIGTERM/SIGKILL may be requested by stop_groups and are NOT proof of
    spontaneous native failure. Internal Webots controller exits still need
    separate evidence; a clean direct-child status does not prove their health.
    """
    for index, child in enumerate(children):
        code = child.returncode
        if code is None:
            raise RuntimeError('native child retirement status missing: ' + str(index))
        if any(code == -number or code == 128 + number
               for number in _FATAL_SIGNAL_NUMBERS):
            raise RuntimeError(
                'fatal native direct-child exit at retirement: index=' +
                str(index) + ' code=' + str(code))
