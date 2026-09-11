// Added only to a hash-checked temporary copy of the preserved C10 provider.
#include <QtCore/QTimer>
#include <QtGui/QScreen>
#include <QtGui/QWindow>
#include <QtGui/QPixmap>
#include <cstdlib>
#include <unistd.h>

static void qualify_dialog(QFileDialog &dialog) {
  const QString title = QString("WebeeBlocks Q87 qualification %1").arg(::getpid());
  dialog.setWindowTitle(title);
  dialog.setFileMode(QFileDialog::ExistingFile);
  dialog.setDirectory(QString::fromUtf8(std::getenv("Q87_FILES")));
  // No QPA/platform option or native-dialog substitution is introduced.
  bool exposed = false;
  QTimer witness;
  QObject::connect(&witness, &QTimer::timeout, [&]() {
    QWindow *window = dialog.windowHandle();
    if (!exposed && dialog.isVisible() && window && window->isExposed()) {
      const QPixmap pixels = window->screen()->grabWindow(dialog.winId());
      const QString output = QString::fromUtf8(std::getenv("Q87_EVIDENCE")) + "/dialog.png";
      if (pixels.isNull() || !pixels.save(output, "PNG")) _exit(125);
      exposed = true;
      std::printf("Q87 DIALOG_EXPOSED pid=%ld wid=%lu width=%d height=%d\n",
                  static_cast<long>(::getpid()), static_cast<unsigned long>(dialog.winId()),
                  pixels.width(), pixels.height());
      std::fflush(stdout);
    }
  });
  QTimer deadline;
  deadline.setSingleShot(true);
  QObject::connect(&deadline, &QTimer::timeout, []() {
    std::fputs("Q87 DIALOG_TIMEOUT\n", stderr);
    std::fflush(stderr);
    _exit(126);
  });
  witness.start(50);
  deadline.start(15000);
  std::puts("Q87 DIALOG_EXEC");
  std::fflush(stdout);
  const int result = dialog.exec();
  witness.stop();
  deadline.stop();
  if (!exposed || result != QDialog::Rejected) throw std::runtime_error("dialog did not complete through observed cancellation");
  std::puts("Q87 DIALOG_CANCELLED result=Rejected");
  std::fflush(stdout);
}
