"""Controlled full-process Webots #665 GDB intervention, NOT a natural download."""
import gdb, json, itertools, re
counter=itertools.count(1)
state={'dialog':0,'bar':0,'selected':None,'dead_dialog':False,'dead_bar':False}
breakpoints={}
def event(kind,**data):
    gdb.write('WBB_QT665 '+json.dumps(dict(kind=kind,n=next(counter),**data),sort_keys=True)+'\n')
def ptr():return int(gdb.parse_and_eval('$rdi'))
def stack():return gdb.execute('bt 28',to_string=True)
def frames():
    frame=gdb.newest_frame()
    while frame:
        yield frame
        try:frame=frame.older()
        except gdb.error:return
def coverage():
    if 'checked' in state:return
    resolved={}
    for name,bp in breakpoints.items():
        try:
            info=gdb.execute('info breakpoints '+str(bp.number),to_string=True)
            resolved[name]=bool(bp.enabled and not bp.pending and re.search(r'0x[0-9a-fA-F]{10,}',info))
        except Exception:resolved[name]=False
    state['checked']=True
    state['coverage_pass']=(len(resolved)==5 and all(resolved.values()))
    event('coverage_live',resolved=resolved,all_resolved=state['coverage_pass'])
class Dialog(gdb.Breakpoint):
    def stop(self):
        state['dialog']=ptr();state['bar']=0
        coverage()
        event('enter',dialog=state['dialog'])
        return False
class Bar(gdb.Breakpoint):
    def stop(self):
        if state['dialog'] and 'QProgressDialog::setValue' in stack():
            state['bar']=ptr()
        return False
class Dtor(gdb.Breakpoint):
    def __init__(self,sym,typ):
        self.typ=typ
        super().__init__(sym,internal=False)
        self.silent=True
    def stop(self):
        p=ptr()
        if state['selected'] and state['selected'][self.typ]==p:
            state['dead_'+self.typ]=True
            trace=stack()
            event('destroy',target=self.typ,object=p,
                  inside_setvalue=('QProgressDialog::setValue' in trace),backtrace=trace)
        return False
class AfterMax(gdb.FinishBreakpoint):
    def __init__(self):
        super().__init__(gdb.newest_frame(),internal=True)
        self.silent=True
    def stop(self):
        event('maximum_returned',bar=state['selected']['bar'],
              dead_bar=state['dead_bar'],dead_dialog=state['dead_dialog'],
              inside_setvalue='QProgressDialog::setValue' in stack())
        return False
    def out_of_scope(self):
        event('maximum_finish_out_of_scope')
class Maximum(gdb.Breakpoint):
    def stop(self):
        if state['selected'] or not state.get('coverage_pass'):return False
        bar=ptr()
        if not state['dialog'] or bar!=state['bar']:return False
        trace=stack()
        if 'QProgressDialog::setValue' not in trace:return False
        target=None
        for f in frames():
            if 'WbMainWindow::setWorldLoadingProgress' in str(f.name() or ''):
                target=f
                break
        if target is None:return False
        try:
            win=int(target.read_var('this'))
            obj=target.read_var('this').dereference()
            dialog=int(obj['mWorldLoadingProgressDialog'])
            depth=int(obj['mWorldLoadingProgressOperationDepth'])
        except Exception as exc:
            event('eligibility_gap',reason=str(exc))
            return False
        if dialog!=state['dialog'] or depth<1:return False
        self.enabled=False
        state['selected']=dict(window=win,dialog=dialog,bar=bar,depth=depth)
        event('selected_maximum',**state['selected'],backtrace=trace)
        return True
gdb.execute('set pagination off')
gdb.execute('set confirm off')
gdb.execute('set breakpoint pending on')
gdb.execute('set print thread-events off')
gdb.execute('set disable-randomization off')
for name,factory in (
 ('dialog',lambda:Dialog('QProgressDialog::setValue(int)',internal=False)),
 ('bar',lambda:Bar('QProgressBar::setValue(int)',internal=False)),
 ('maximum',lambda:Maximum('QProgressBar::maximum() const',internal=False)),
 ('dialog_dtor',lambda:Dtor('QProgressDialog::~QProgressDialog()','dialog')),
 ('bar_dtor',lambda:Dtor('QProgressBar::~QProgressBar()','bar'))
):
    bp=factory();bp.silent=True;breakpoints[name]=bp
event('setup',mode='ONE_SHOT_NATIVE_INTERVENTION_NOT_NATURAL_NETWORK_CALLBACK')
try:
    gdb.execute('run')
    if state['selected']:
        try:
            old=state['selected']
            expression='((WbMainWindow*)0x%x)->deleteWorldLoadingProgressDialog()' % old['window']
            gdb.execute('call '+expression)
            obj=gdb.parse_and_eval('(WbMainWindow*)0x%x' % old['window']).dereference()
            inactive=int(obj['mWorldLoadingProgressDialog'])==0
            guarded=int(obj['mWorldLoadingProgressOperationDepth'])>0
            trace=stack()
            event('injected_native_retirement',inactive=inactive,guarded=guarded,
                  dialog=old['dialog'],bar=old['bar'],
                  dead_dialog=state['dead_dialog'],dead_bar=state['dead_bar'],
                  inside_setvalue='QProgressDialog::setValue' in trace,
                  backtrace=trace)
            if not inactive or not guarded or state['dead_dialog'] or state['dead_bar']:
                event('injection_gap',reason='retire_invalid')
            try:AfterMax()
            except Exception as exc:event('injection_gap',reason='finish:'+str(exc))
            gdb.execute('continue')
        except Exception as exc:event('injection_gap',reason='inferior_call:'+str(exc))
    else:event('injection_gap',reason='no_eligible_native_maximum')
except Exception as exc:event('injection_gap',reason='gdb:'+str(exc))
