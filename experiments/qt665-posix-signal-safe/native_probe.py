#!/usr/bin/env python3
"""Run the actual patched main.cpp POSIX fragments in a small Qt6.5.3 process.

This does NOT replace a full Webots binary. Fail closed on missing source
anchors; do not rewrite the signal handler or the socket notifier logic.
"""
import argparse
import json
from pathlib import Path
import struct

MAGIC=0x5154363635534947
def unique_segment(source, start, end):
    assert source.count(start)==1 and source.count(end)==1, (start,end)
    return source.split(start,1)[1].split(end,1)[0]

def generate(src:Path,dest:Path):
    text=src.read_text()
    assert text.count('WbApplication::instance()->simulationQuit(EXIT_SUCCESS)')==2
    handler=unique_segment(text,
        '#ifndef _WIN32\n// A POSIX handler',
        '\n#else\n// Preserve the original Windows')
    handler='// A POSIX handler'+handler
    setup_start='  // Configure the self-pipe before enabling any process signal callbacks.\n'
    setup_end='  signal(SIGHUP, quitApplication);\n'
    assert text.count(setup_start)==1 and text.count(setup_end)==1
    setup=setup_start+text.split(setup_start,1)[1].split(setup_end,1)[0]+setup_end
    cleanup=unique_segment(text, '#else\n  const int result = app.exec();',
                           '\n#endif\n}')
    cleanup='  const int result = app.exec();'+cleanup
    assert cleanup.endswith('  return result;')
    cleanup=cleanup.replace('  return result;', '  return result == 0 && quitCount == 1 ? 0 : 46;')
    for fragment in (handler,setup,cleanup):
        assert fragment and 'QSocketNotifier' not in handler
    harness=r"""
#include <QApplication>
#include <QCoreApplication>
#include <QSocketNotifier>
#include <QTimer>
#include <QThread>
#include <cerrno>
#include <csignal>
#include <cstdio>
#include <cstdlib>
#include <fcntl.h>
#include <unistd.h>
static int quitCount=0;
class WbApplication {
 public:
  static WbApplication *instance() { static WbApplication a; return &a; }
  void simulationQuit(int status) {
    if (status != EXIT_SUCCESS || QThread::currentThread() !=
        QCoreApplication::instance()->thread()) std::_Exit(55);
    if (++quitCount != 1) std::_Exit(56);
    std::puts("QT665_QT_GUI_DISPATCH=PASS");
    std::fflush(stdout);
    QTimer::singleShot(80, QCoreApplication::instance(),
       [] { QCoreApplication::quit(); });
  }
};
""" + '\n' +handler+'\n'+r"""
int main(int argc, char **argv) {
  QApplication app(argc, argv);
""" +setup+r"""
  QTimer::singleShot(0, &app, [] {
    if (raise(SIGTERM) != 0 || raise(SIGTERM) != 0) std::_Exit(57);
  });
  QTimer::singleShot(5000, &app, [] { QCoreApplication::exit(58); });
""" +cleanup+'\n}\n'
    dest.write_text(harness)
    print('QT665_GENERATED_ACTUAL_POSIX_SOURCE=PASS',flush=True)

def verify(trace:Path, log:Path, output:Path):
    content=trace.read_bytes()
    assert content and len(content)%48==0, "missing or partial trace"
    raw=list(struct.iter_unpack('<6Q',content))
    assert len(raw)>7 and all(row[0]==MAGIC for row in raw)
    assert len({r[1] for r in raw})==1,"not single Webots harness process"
    signals=[r for r in raw if r[3]==ord('S') and r[5]==15]
    assert len(signals)==1, "SIGTERM handler not interposed"
    active=0; entries=exits=0; alloc=[]
    for r in raw:
        event=chr(r[3])
        if event=='E':
            assert r[5]==15 and r[4]==active+1
            active+=1;entries+=1
        elif event=='L':
            assert active>0 and r[4]==active
            active-=1;exits+=1
        elif event in 'MCAmcaF':
            alloc.append(dict(event=event,tid=r[2],depth=r[4],value=r[5]))
            assert r[4]==0, "allocator activity inside POSIX handler"
    assert active==0 and entries==exits==2,(entries,exits,active)
    assert not alloc,alloc
    logtext=log.read_text()
    assert logtext.count('QT665_QT_GUI_DISPATCH=PASS')==1
    result={'kind':'Qt6.5.3 source-extracted signal path, not full Webots',
            'signal':'SIGTERM','entries':entries,'exits':exits,
            'allocator_events_inside_handler':len(alloc),
            'qt_gui_dispatches':1,
            'outcome':'PASS_BOUND_NATIVE_HARNESS',
            'limitations':['full Webots linking and real installed executable NOT_TESTED',
              'underlying historical QRawFont/malloc SIGSEGV causality UNPROVEN',
              'Windows Ctrl+C NOT_TESTED']}
    output.write_text(json.dumps(result,indent=2)+'\n')
    print('QT665_POSIX_SIGNAL_NATIVE_HARNESS=PASS',flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--generate',action='store_true')
    group.add_argument('--verify',action='store_true')
    parser.add_argument('--patched-source',type=Path)
    parser.add_argument('--harness-out',type=Path)
    parser.add_argument('--trace',type=Path)
    parser.add_argument('--log',type=Path)
    parser.add_argument('--result-out',type=Path)
    a=parser.parse_args()
    if a.generate:
        assert a.patched_source and a.harness_out
        generate(a.patched_source,a.harness_out)
    else:
        assert a.trace and a.log and a.result_out
        verify(a.trace,a.log,a.result_out)
