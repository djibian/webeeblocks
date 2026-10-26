"""GDB-only diagnostic: exact-object Qt progress lifetime in native Webots #665.

Linux x86_64 System V ABI. Run only in an isolated diagnostic container.
No product oracles, mission scenarios, or Qt binaries are modified.
"""
import gdb
import itertools
import json

serial = itertools.count(1)
active = {}
probes = {}
coverage_reported = False

def out(kind, **kw):
    data = dict(schema=1, n=next(serial), kind=kind, **kw)
    gdb.write('WBB_QT665 ' + json.dumps(data, sort_keys=True) + '\n')

def report_live_coverage():
    """Pending symbols do not count as a resolved native probe."""
    global coverage_reported
    if coverage_reported:
        return
    coverage_reported = True
    resolved = {}
    for name, bp in probes.items():
        try:
            resolved[name] = bool(bp.enabled and not bp.pending and bp.locations)
        except Exception as exc:
            resolved[name] = False
            out('gap', where='coverage_resolution', symbol=name, error=str(exc))
    out('coverage_live', resolved=resolved,
        all_resolved=len(resolved) == 5 and all(resolved.values()))

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
                destroyed_bar=frame['dead_bar'])
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
        super().__init__(symbol, internal=True)
        self.silent = True

    def stop(self):
        try:
            t, p = thread_id(), ptr()
            ids = []
            for f in active.get(t, []):
                if f[self.target] == p:
                    f['dead_' + self.target] = True
                    ids.append(f['id'])
            if ids:
                out(self.target + '_destroyed_within_setvalue',
                    thread=t, object=p, ids=ids, backtrace=stack())
        except Exception as exc:
            out('gap', where='destruction_failed', error=str(exc))
        return False

class Maximum(gdb.Breakpoint):
    def stop(self):
        try:
            t, p = thread_id(), ptr()
            ids = [f['id'] for f in active.get(t, []) if f['bar'] == p]
            if ids:
                out('bar_maximum_within_setvalue',
                    thread=t, object=p, ids=ids)
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
    ('dialog_setvalue', lambda: Entry('QProgressDialog::setValue(int)', internal=True)),
    ('bar_setvalue', lambda: BarEntry('QProgressBar::setValue(int)', internal=True)),
    ('dialog_dtor', lambda: Destruction('QProgressDialog::~QProgressDialog()', 'dialog')),
    ('bar_dtor', lambda: Destruction('QProgressBar::~QProgressBar()', 'bar')),
    ('bar_maximum', lambda: Maximum('QProgressBar::maximum() const', internal=True)),
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
