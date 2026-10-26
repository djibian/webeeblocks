#include <QtWidgets/QApplication>
#include <QtWidgets/QProgressDialog>
#include <QtWidgets/QProgressBar>
#include <QtCore/QPointer>
#include <QtCore/QTimer>
#include <QtCore/QEvent>
#include <QtCore/QThread>
#include <execinfo.h>
#include <cstdio>
#include <cstring>

static void record(const char *event, const void *pointer=nullptr) {
  std::printf("EVENT %s pointer=%p\n",event,pointer); std::fflush(stdout);
}
int main(int argc,char **argv) {
  QApplication app(argc,argv);
  const char *mode=argc>1?argv[1]:"modal-direct";
  std::printf("QT_VERSION %s mode=%s\n",qVersion(),mode);std::fflush(stdout);
  auto *dialog=new QProgressDialog();
  auto *bar=dialog->findChild<QProgressBar*>();
  QObject::connect(dialog,&QObject::destroyed,[](QObject *p){record("DIALOG_DESTROYED",p);});
  QObject::connect(bar,&QObject::destroyed,[](QObject *p){record("BAR_DESTROYED",p);});
  dialog->setModal(std::strcmp(mode,"nonmodal-direct")!=0);
  dialog->setAutoClose(false);dialog->setMinimumDuration(0);dialog->show();dialog->setValue(0);
  dialog->setValue(1);
  QMetaObject::invokeMethod(dialog,"forceShow",Qt::DirectConnection);
  QApplication::processEvents();
  std::printf("STATE modal=%d visible=%d minimumDuration=%d\n",dialog->isModal(),dialog->isVisible(),dialog->minimumDuration()); std::fflush(stdout);
  record("CREATED",dialog);record("BAR",bar);
  QPointer<QProgressDialog> observed(dialog);
  QTimer::singleShot(0,[&]{
    record("DELETE_EVENT",dialog);
    void *frames[32]; int count=backtrace(frames,32);
    backtrace_symbols_fd(frames,count,2);
    if(std::strcmp(mode,"modal-deferred")==0) dialog->deleteLater();
    else {delete dialog;dialog=nullptr;}
  });
  record("SET_VALUE_ENTER",dialog);
  dialog->setValue(2);
  record("SET_VALUE_RETURN",observed.data());
  QApplication::processEvents();
  QApplication::sendPostedEvents(nullptr,QEvent::DeferredDelete);
  record("END",observed.data());
  if(observed) delete observed.data();
  return 0;
}
