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
    ('dialog_setvalue', lambda: Entry('QProgressDialog::setValue(int)', internal=False)),
    ('bar_setvalue', lambda: BarEntry('QProgressBar::setValue(int)', internal=False)),
    ('dialog_dtor', lambda: Destruction('QProgressDialog::~QProgressDialog()', 'dialog')),
    ('bar_dtor', lambda: Destruction('QProgressBar::~QProgressBar()', 'bar')),
    ('bar_maximum', lambda: Maximum('QProgressBar::maximum() const', internal=False)),
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


# Candidate extension: attach to original, already validated lifetime breakpoints.
# A retirement belongs to a setValue frame only if the actual active dialog
# member equals the pointer of that exact frame.
_retired_objects = {}
_returned_frames = set()
_orig_maximum_stop = Maximum.stop
_orig_destruction_stop = Destruction.stop
_orig_return_stop = Returned.stop

class CandidateRetirement(gdb.Breakpoint):
    def __init__(self):
        super().__init__('WbMainWindow::deleteWorldLoadingProgressDialog()', internal=False)
        self.silent = True

    def stop(self):
        try:
            t = thread_id()
            current_dialog = int(gdb.parse_and_eval(
                '((WbMainWindow *)$rdi)->mWorldLoadingProgressDialog'))
            for f in active.get(t, []):
                if int(f['dialog'], 16) == current_dialog:
                    f['retired'] = True
                    out('candidate_retire_inside_setvalue',
                        id=f['id'], dialog=f['dialog'], bar=f['bar'],
                        thread=t, depth=len(active[t]))
                    break
        except Exception as exc:
            out('gap', where='candidate_retirement_probe', error=str(exc))
        return False

def candidate_maximum_stop(self):
    try:
        p = ptr()
        for f in active.get(thread_id(), []):
            if f.get('retired') and f.get('bar') == p:
                f['maximum_after_retire'] = True
                out('candidate_maximum_after_retire', id=f['id'], bar=p,
                    bar_alive=not f['dead_bar'],
                    dialog_alive=not f['dead_dialog'])
    except Exception as exc:
        out('gap', where='candidate_maximum_probe', error=str(exc))
    return _orig_maximum_stop(self)

def candidate_return_stop(self):
    frames = active.get(self.t, [])
    if frames and frames[-1]['id'] == self.ident:
        f = frames[-1]
        if f.get('retired'):
            _retired_objects[f['dialog']] = {
                'id': f['id'], 'bar': f['bar'],
                'maximum_after_retire': bool(f.get('maximum_after_retire')),
            }
            out('candidate_retired_frame_return', id=f['id'], dialog=f['dialog'],
                bar=f['bar'], maximum_after_retire=bool(f.get('maximum_after_retire')),
                dialog_alive=not f['dead_dialog'], bar_alive=not f['dead_bar'])
        _returned_frames.add(self.ident)
    return _orig_return_stop(self)

def candidate_destruction_stop(self):
    try:
        p = ptr()
        for dialog, detail in _retired_objects.items():
            tracked = dialog if self.target == 'dialog' else detail['bar']
            if tracked == p:
                out('candidate_retired_object_destructor',
                    id=detail['id'], kind_of_object=self.target, object=p,
                    after_setvalue_return=detail['id'] in _returned_frames)
                break
    except Exception as exc:
        out('gap', where='candidate_deferred_destructor_probe', error=str(exc))
    return _orig_destruction_stop(self)

Maximum.stop = candidate_maximum_stop
Returned.stop = candidate_return_stop
Destruction.stop = candidate_destruction_stop
try:
    candidate_retire_bp = CandidateRetirement()
    out('candidate_retirement_breakpoint', installed=True,
        pending=bool(candidate_retire_bp.pending),
        detail=gdb.execute('info breakpoints ' + str(candidate_retire_bp.number),
                           to_string=True)[:800])
except Exception as exc:
    out('gap', where='candidate_retirement_install', error=str(exc))


# Independent real-stack discriminator. The historic FinishBreakpoint tracker
# is NOT an oracle on this new ELF: it did not observe returns (GDB PLT frames).
# These checks inspect the actual native C++ stack at EACH decisive event.
_qt665_verified = {}

def _qt665_actual_setvalue(bt):
    return bool(re.search(r'QProgressDialog::setValue\(int\)', bt))

class QActualRetirement(gdb.Breakpoint):
    def __init__(self):
        super().__init__('WbMainWindow::deleteWorldLoadingProgressDialog()', internal=False)
        self.silent = True

    def stop(self):
        try:
            t=thread_id()
            dialog='0x%x' % int(gdb.parse_and_eval(
                '((WbMainWindow *)$rdi)->mWorldLoadingProgressDialog'))
            bt=stack()
            matches=[f for f in active.get(t,[]) if f['dialog']==dialog and f.get('bar')]
            bar=matches[-1]['bar'] if matches else None
            inside=_qt665_actual_setvalue(bt)
            if dialog!='0x0' and inside and bar:
                _qt665_verified[dialog]=dict(dialog=dialog,bar=bar,
                    thread=t, ret=True, maximum=False,dead_dialog=False,dead_bar=False)
                out('native_actual_retire_inside_setvalue',dialog=dialog,
                    bar=bar,thread=t,actual_stack_setvalue=inside,
                    stack=bt[-3600:])
            elif dialog!='0x0':
                out('native_actual_retire_unqualified',dialog=dialog,bar=bar,
                    actual_stack_setvalue=inside,stack=bt[-2000:])
        except Exception as exc:
            out('gap',where='native_actual_retirement_probe',error=str(exc))
        return False

_prev_maximum_stop=Maximum.stop
def _native_actual_maximum_stop(self):
    try:
        p=ptr(); t=thread_id()
        for state in _qt665_verified.values():
            if state['bar']!=p or state['thread']!=t:
                continue
            bt=stack()
            inside=_qt665_actual_setvalue(bt)
            if inside and not state['dead_dialog'] and not state['dead_bar']:
                state['maximum']=True
                out('native_actual_maximum_after_retire',
                    dialog=state['dialog'],bar=p,
                    actual_stack_setvalue=True,still_alive=True,stack=bt[-2800:])
            else:
                out('native_actual_maximum_unqualified',
                    dialog=state['dialog'],bar=p,
                    actual_stack_setvalue=inside,
                    dialog_dead=state['dead_dialog'],bar_dead=state['dead_bar'],
                    stack=bt[-2800:])
    except Exception as exc:
        out('gap',where='native_actual_maximum_probe',error=str(exc))
    return _prev_maximum_stop(self)
Maximum.stop=_native_actual_maximum_stop

_prev_destructor_stop=Destruction.stop
def _native_actual_dtor_stop(self):
    try:
        p=ptr(); t=thread_id()
        for state in _qt665_verified.values():
            target=state['dialog'] if self.target=='dialog' else state['bar']
            if target!=p or state['thread']!=t:
                continue
            bt=stack()
            inside=_qt665_actual_setvalue(bt)
            state['dead_'+self.target]=True
            out('native_actual_'+self.target+'_dtor',
                dialog=state['dialog'],bar=state['bar'],
                actual_stack_setvalue=inside,
                after_maximum=state['maximum'],
                stack=bt[-3600:])
    except Exception as exc:
        out('gap',where='native_actual_dtor_probe',error=str(exc))
    return _prev_destructor_stop(self)
Destruction.stop=_native_actual_dtor_stop
try:
    probe=QActualRetirement()
    out('native_actual_retirement_probe_ready',
        pending=bool(probe.pending),breakpoint=probe.number)
except Exception as exc:
    out('gap',where='native_actual_retirement_install',error=str(exc))
