"""GDB-only diagnostic: exact-object Qt progress lifetime in native Webots #665.

Linux x86_64 System V ABI. Run only in an isolated diagnostic container.
No product oracles, mission scenarios, or Qt binaries are modified.
"""
import gdb
import itertools
import json
import re

serial = itertools.count(1)
active = {}
probes = {}
coverage_reported = False

def out(kind, **kw):
    data = dict(schema=1, n=next(serial), kind=kind, **kw)
    gdb.write('WBB_QT665 ' + json.dumps(data, sort_keys=True) + '\n')

def report_live_coverage():
    """Qualify enabled, non-pending numeric breakpoints in GDB 12.1."""
    global coverage_reported
    if coverage_reported:
        return
    coverage_reported = True
    resolved = {}
    for name, bp in probes.items():
        try:
            rows = gdb.execute('info breakpoints ' + str(bp.number),
                               to_string=True)
            # The installed GDB 12.1 Breakpoint has no .locations attribute.
            # Require an actual numeric address rather than a pending symbol.
            resolved[name] = bool(bp.enabled and not bp.pending and
                                  re.search(r'0x[0-9a-fA-F]{10,}', rows))
            if not resolved[name]:
                out('gap', where='coverage_unresolved', symbol=name,
                    breakpoint_number=bp.number,
                    info=rows[:900])
        except Exception as exc:
            resolved[name] = False
            out('gap', where='coverage_resolution', symbol=name,
                error=str(exc))
    out('coverage_live', resolved=resolved,
        all_resolved=len(resolved) == 6 and all(resolved.values()))

def thread_id():
    t = gdb.selected_thread()
    return str(t.ptid) if t else 'none'

def ptr():
    return '0x%x' % int(gdb.parse_and_eval('$rdi'))

def stack():
    try:
        return gdb.execute('bt 24', to_string=True)
    except gdb.error as exc:
        return 'unavailable:' + str(exc)

def iter_native_frames():
    frame = gdb.newest_frame()
    while frame is not None:
        yield frame
        try:
            frame = frame.older()
        except gdb.error:
            return

class Returned(gdb.FinishBreakpoint):
    def __init__(self, frame, t, ident):
        self.t, self.ident = t, ident
        super().__init__(frame, internal=True)
        self.silent = True

    def stop(self):
        frames = active.get(self.t, [])
        if frames and frames[-1]['id'] == self.ident:
            frame = frames.pop()
            out('return', thread=self.t, dialog=frame['dialog'], bar=frame['bar'],
                id=self.ident, destroyed_dialog=frame['dead_dialog'],
                destroyed_bar=frame['dead_bar'], retired=frame.get('retired', False))
        else:
            out('gap', where='non_lifo_return', id=self.ident)
        return False

    def out_of_scope(self):
        out('gap', where='frame_out_of_scope', id=self.ident)
        active[self.t] = [f for f in active.get(self.t, [])
                          if f['id'] != self.ident]

class Entry(gdb.Breakpoint):
    def stop(self):
        try:
            report_live_coverage()
            t, p, ident = thread_id(), ptr(), next(serial)
            f = dict(id=ident, dialog=p, bar=None, dead_dialog=False,
                     dead_bar=False)
            active.setdefault(t, []).append(f)
            out('enter', id=ident, thread=t, dialog=p, depth=len(active[t]))
            # Distinguish truly nested Qt stacks from stale GDB FinishBreakpoint
            # book-keeping. The first few boundaries and upper depths are
            # enough to prove the failure mode without dumping all process
            # memory or overwhelming the log.
            if len(active[t]) in (2, 8, 32, 128, 256):
                out('native_depth_snapshot', recorded_depth=len(active[t]),
                    actual_setvalue_frames=sum(
                        'QProgressDialog::setValue' in name for name in
                        [frame.name() or '' for frame in
                         iter_native_frames()]), backtrace=stack())
            try:
                Returned(gdb.newest_frame(), t, ident)
            except Exception as exc:
                out('gap', where='finish_unavailable', id=ident, error=str(exc))
        except Exception as exc:
            out('gap', where='enter_failed', error=str(exc))
        return False

class BarEntry(gdb.Breakpoint):
    def stop(self):
        try:
            frames = active.get(thread_id(), [])
            if frames and frames[-1]['bar'] is None:
                frames[-1]['bar'] = ptr()
                out('bar_bound', id=frames[-1]['id'], bar=frames[-1]['bar'],
                    dialog=frames[-1]['dialog'])
        except Exception as exc:
            out('gap', where='bar_bind_failed', error=str(exc))
        return False

class Destruction(gdb.Breakpoint):
    def __init__(self, symbol, target):
        self.target = target
        super().__init__(symbol, internal=False)
        self.silent = True

    def stop(self):
        try:
            t, p = thread_id(), ptr()
            ids = []
            for f in active.get(t, []):
                if f[self.target] == p:
                    f['dead_' + self.target] = True
                    ids.append(f['id'])
            if ids and 'QProgressDialog::setValue' in stack():
                out(self.target + '_destroyed_within_setvalue',
                    thread=t, object=p, ids=ids, backtrace=stack())
        except Exception as exc:
            out('gap', where='destruction_failed', error=str(exc))
        return False

class Retire(gdb.Breakpoint):
    """Only match a true retirement of the dialog in the active Qt frame."""
    def stop(self):
        try:
            target = int(gdb.parse_and_eval("this->mWorldLoadingProgressDialog"))
            true_stack = stack()
            out('retire_seen', target=target,
                genuine_in_setvalue=('QProgressDialog::setValue' in true_stack),
                backtrace=true_stack)
            for frame in active.get(thread_id(), []):
                if target and frame['dialog'] == target and frame['bar']:
                    frame['retired'] = True
                    out('retire_within_setvalue', id=frame['id'],
                        dialog=target, bar=frame['bar'], backtrace=stack())
        except Exception as exc:
            out('gap', where='retire_failed', error=str(exc))
        return False

class Maximum(gdb.Breakpoint):
    def stop(self):
        try:
            t, p = thread_id(), ptr()
            ids = [f['id'] for f in active.get(t, []) if f['bar'] == p]
            if ids and 'QProgressDialog::setValue' in stack():
                out('bar_maximum_within_setvalue',
                    thread=t, object=p, ids=ids)
                for frame in active.get(t, []):
                    if frame['id'] in ids and frame.get('retired'):
                        out('bar_maximum_after_retire', id=frame['id'],
                            bar=p, dialog=frame['dialog'])
        except Exception as exc:
            out('gap', where='maximum_failed', error=str(exc))
        return False

def stopped(ev):
    if isinstance(ev, gdb.SignalEvent):
        out('signal', name=ev.stop_signal, thread=thread_id(),
            active=active.get(thread_id(), []), backtrace=stack())

def exited(ev):
    out('inferior_exit', exit_code=getattr(ev, 'exit_code', None),
        unreturned=active)

gdb.execute('set pagination off')
gdb.execute('set multiple-symbols all')
gdb.execute('set breakpoint pending on')
specs = (
    ('dialog_setvalue', lambda: Entry('QProgressDialog::setValue(int)', internal=False)),
    ('bar_setvalue', lambda: BarEntry('QProgressBar::setValue(int)', internal=False)),
    ('dialog_dtor', lambda: Destruction('QProgressDialog::~QProgressDialog()', 'dialog')),
    ('bar_dtor', lambda: Destruction('QProgressBar::~QProgressBar()', 'bar')),
    ('bar_maximum', lambda: Maximum('QProgressBar::maximum() const', internal=False)),
    ('window_retire', lambda: Retire('WbMainWindow::deleteWorldLoadingProgressDialog()', internal=False)),
)
coverage = {}
for name, create in specs:
    try:
        bp = create()
        bp.silent = True
        probes[name] = bp
        coverage[name] = {'installed': True, 'pending_initially': bool(bp.pending)}
    except Exception as exc:
        coverage[name] = {'installed': False, 'error': str(exc)}
        out('gap', where='install', symbol=name, error=str(exc))
out('setup', coverage=coverage, abi='linux-x86_64')
gdb.events.stop.connect(stopped)
gdb.events.exited.connect(exited)
