"""NON-GATE: extract actual Webots SIGTERM/notifier source into Qt6 veto harness."""
import sys
from pathlib import Path

src=Path(sys.argv[1]).read_text()
window=Path(sys.argv[2]).read_text()
assert "if (!proposeToSaveWorld()) {\n    event->ignore();\n    return;" in window
assert "if (result == QMessageBox::Cancel)\n      return false;" in window
def section(start,end):
    assert src.count(start)==src.count(end)==1, "ambiguous source"
    return src.split(start,1)[1].split(end,1)[0]
handler="// A POSIX handler"+section("#ifndef _WIN32\n// A POSIX handler","\n#else\n// Preserve the original Windows")
start="  // Configure the self-pipe before enabling any process signal callbacks.\n"
end="  signal(SIGHUP, quitApplication);\n"
setup=start+section(start,end)+end
assert "quitNotifier.setEnabled(false);" in setup
assert setup.count("WbApplication::instance()->simulationQuit(EXIT_SUCCESS)") == 1
header=r"""
#include <QtWidgets/QApplication>
#include <QtWidgets/QWidget>
#include <QtGui/QCloseEvent>
#include <QtCore/QCoreApplication>
#include <QtCore/QMetaObject>
#include <QtCore/QSocketNotifier>
#include <QtCore/QTimer>
#include <csignal>
#include <cerrno>
#include <cstdlib>
#include <cstdio>
#include <fcntl.h>
#include <unistd.h>
static QWidget *w=nullptr;
static int requests=0,attempts=0,sent=0;
static bool veto=false;
struct Window : QWidget {
 void closeEvent(QCloseEvent *e) override {
   ++attempts;
   if(veto && attempts==1) e->ignore();
   else e->accept();
 }
};
class WbApplication {
public:
 static WbApplication *instance() { static WbApplication a; return &a; }
 void simulationQuit(int status) {
   if(status!=EXIT_SUCCESS) std::_Exit(51);
   ++requests;
   QMetaObject::invokeMethod(w,[] {w->close();},Qt::QueuedConnection);
 }
};
"""
main=r"""
int main(int argc,char **argv) {
 QApplication app(argc,argv);
 veto=argc>1 && argv[1][0]=='v';
 Window window; w=&window; window.show();
"""
endmain=r"""
 QTimer::singleShot(0,&app,[]{++sent; if(raise(SIGTERM))std::_Exit(52);});
 if(veto)QTimer::singleShot(120,&app,[]{++sent; if(raise(SIGTERM))std::_Exit(53);});
 QTimer::singleShot(650,&app,[]{QCoreApplication::quit();});
 int rc=app.exec();
 std::printf("MODE=%s SENT=%d REQUESTS=%d CLOSES=%d VISIBLE=%d RC=%d\n",
     veto?"veto":"normal",sent,requests,attempts,(int)window.isVisible(),rc);
 bool positive=!veto&&sent==1&&requests==1&&attempts==1&&!window.isVisible();
 bool lost=veto&&sent==2&&requests==1&&attempts==1&&window.isVisible();
 if(positive){std::puts("NORMAL_QUIT=PASS");return 0;}
 if(lost){std::puts("CANCEL_SECOND_SIGTERM_SWALLOWED=OBSERVED");return 0;}
 return 54;
}
"""
Path(sys.argv[3]).write_text(header+handler+main+setup+endmain)
print("SOURCE_EXACT_HANDLER_AND_NOTIFIER=PASS")
