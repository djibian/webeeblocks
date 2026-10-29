// Copyright 1996-2024 Cyberbotics Ltd.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     https://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

#include "WbApplication.hpp"
#include "WbGuiApplication.hpp"

#include <QtCore/QDir>
#include <QtCore/QFileInfo>
#include <QtCore/QLocale>
#include <QtCore/QRegularExpression>
#include <QtCore/QTextStream>
#include <QtCore/QVector>
#include <QtGui/QSurfaceFormat>
#include <QtWidgets/QApplication>

#include <csignal>

#ifndef _WIN32
#include <QtCore/QSocketNotifier>
#include <cerrno>
#include <fcntl.h>
#include <unistd.h>
#endif

#ifdef _WIN32
#include <windows.h>
#include <QtCore/QProcess>
extern "C" {
// defaults to nVidia instead of Intel graphics on Optimus architectures (commonly found on laptops)
// unfortunately, the AMD equivalent doesn't seem to exist.
__declspec(dllexport) DWORD NvOptimusEnablement = 0x00000001;
}
#ifdef NDEBUG
#include <stdio.h>
#include <wincon.h>
static void RedirectIOToConsole() {
  long int file_type = GetFileType(GetStdHandle(STD_OUTPUT_HANDLE));
  if (file_type != FILE_TYPE_PIPE) {
    if (!AttachConsole(ATTACH_PARENT_PROCESS))
      return;  // attempt to use the parent's console
    (void)freopen("CONOUT$", "w", stdout);
    (void)freopen("CONOUT$", "w", stderr);
    (void)freopen("CONIN$", "r", stdin);
  }
}
#endif
#else
#include <locale.h>
#endif

static QVector<QRegularExpression *> gQtMessageFilters;

// http://doc.qt.io/qt-5/qtglobal.html#qInstallMessageHandler
static void catchMessageOutput(QtMsgType type, const QMessageLogContext &context, const QString &msg) {
  if (!gQtMessageFilters.isEmpty()) {
    QRegularExpressionMatch match;
    foreach (QRegularExpression *re, gQtMessageFilters) {
      match = re->match(msg);
      if (match.hasMatch())
        // filter out message
        return;
    }
  }

  QString message = msg;
  if (context.file != NULL)
    message += QString("(%s:%u, %s)").arg(context.file).arg(context.line).arg(context.function);
  switch (type) {
    case QtInfoMsg:
      fprintf(stderr, "Info: %s\n", message.toUtf8().constData());
      break;
    case QtDebugMsg:
      fprintf(stderr, "Debug: %s\n", message.toUtf8().constData());
      break;
    case QtWarningMsg:
      fprintf(stderr, "Warning: %s\n", message.toUtf8().constData());
      break;
    case QtCriticalMsg:
      fprintf(stderr, "Critical: %s\n", message.toUtf8().constData());
      break;
    case QtFatalMsg:
      fprintf(stderr, "Fatal: %s\n", message.toUtf8().constData());
      abort();
  }
}

#ifndef _WIN32
// A POSIX handler must not call Qt, acquire a mutex or allocate memory.
// If the non-blocking pipe is full, it already contains a quit notification.
static volatile sig_atomic_t gQuitNotificationFd = -1;
static void quitApplication(int sig) {
  const int savedErrno = errno;
  const sig_atomic_t fd = gQuitNotificationFd;
  if (fd >= 0) {
    const unsigned char notification = static_cast<unsigned char>(sig);
    (void)write(static_cast<int>(fd), &notification, sizeof(notification));
  }
  errno = savedErrno;
}

static bool configureQuitPipeFd(int fd) {
  const int flags = fcntl(fd, F_GETFL);
  const int descriptorFlags = fcntl(fd, F_GETFD);
  return flags != -1 && descriptorFlags != -1 &&
         fcntl(fd, F_SETFL, flags | O_NONBLOCK) != -1 &&
         fcntl(fd, F_SETFD, descriptorFlags | FD_CLOEXEC) != -1;
}
#else
// Preserve the original Windows Ctrl+C behavior in this POSIX-only experiment.
static void quitApplication(int sig) {
  WbApplication::instance()->simulationQuit(EXIT_SUCCESS);
}
#endif

int main(int argc, char *argv[]) {
#ifdef _WIN32
  // on Windows, the webots binary is located in $WEBOTS_HOME/msys64/mingw64/bin/webots
  // we need to use GetModuleFileName as argv[0] doesn't always provide an absolute path
  const int BUFFER_SIZE = 4096;
  wchar_t *tmp = new wchar_t[BUFFER_SIZE];
  GetModuleFileNameW(NULL, tmp, BUFFER_SIZE);
  const QString modulePath = QString::fromWCharArray(tmp);
  delete[] tmp;
  const QString webotsDirPath = QDir(QFileInfo(modulePath).absolutePath() + "/../../..").canonicalPath();
#ifdef NDEBUG
  const char *MSYSCON = getenv("MSYSCON");
  if (MSYSCON && strncmp("mintty.exe", MSYSCON, 10) == 0)
    // if webots was started from a MINGW mintty console
    // we need to unbuffer the stderr as _IOLBF is not working in the msys console
    setvbuf(stderr, NULL, _IONBF, 0);
  else                      // started from a DOS console or from Windows (double click on Webots icon)
    RedirectIOToConsole();  // the release version is built with the -mwindows flag
                            // which drops stdout/stderr, so we need to redirect
                            // them to the parent console in case Webots was started
                            // from a DOS console
#else
  // we need to unbuffer the stderr as _IOLBF is not working in the msys console
  setvbuf(stderr, NULL, _IONBF, 0);
#endif  // NDEBUG
#elif defined(__linux__)
  // on Linux, the webots binary is located in $WEBOTS_HOME/bin/webots-bin
  const QString webotsDirPath = QDir(QFileInfo(argv[0]).absolutePath() + "/..").canonicalPath();
#elif defined(__APPLE__)
  // on macOS, the webots binary is located in $WEBOTS_HOME/Contents/MacOS/webots
  const QString webotsDirPath = QDir(QFileInfo(argv[0]).absolutePath() + "/../..").canonicalPath();
#endif
  QLocale::setDefault(QLocale::c());

#ifdef _WIN32
  const QString MSYS2_HOME = QDir::fromNativeSeparators(getenv("MSYS2_HOME"));
  if (MSYS2_HOME.isEmpty())                                              // Webots was not started from a MSYS2 console
    qputenv("MSYS2_HOME", QString(webotsDirPath + "/msys64").toUtf8());  // useful to Python >= 3.8 controllers
  const QString relativeQtPluginsPath("/mingw64/share/qt6/plugins");
  const QString webotsQtPluginsPath(webotsDirPath + "/msys64" + relativeQtPluginsPath);
  const QString qtPluginsPath = QDir(webotsQtPluginsPath).exists() ? webotsQtPluginsPath : MSYS2_HOME + relativeQtPluginsPath;
#endif

  const QString QT_QPA_PLATFORM_PLUGIN_PATH = qEnvironmentVariable("QT_QPA_PLATFORM_PLUGIN_PATH");
  if (QT_QPA_PLATFORM_PLUGIN_PATH.isEmpty())
    QCoreApplication::addLibraryPath(
#ifdef _WIN32
      qtPluginsPath
#elif defined(__APPLE__)
      webotsDirPath + "/Contents/lib/webots/qt/plugins"
#else
      webotsDirPath + "/lib/webots/qt/plugins"
#endif
    );

#ifdef __APPLE__
  QString qtFiltersFilePath = QDir::fromNativeSeparators(webotsDirPath + "/Contents/Resources/qt_warning_filters.conf");
#else
  QString qtFiltersFilePath = QDir::fromNativeSeparators(webotsDirPath + "/resources/qt_warning_filters.conf");
#endif
  // load qt warning filters from file
  QFile qtFiltersFile(qtFiltersFilePath);
  if (qtFiltersFile.open(QIODevice::ReadOnly)) {
    QTextStream in(&qtFiltersFile);
    QString line;
    while (!in.atEnd()) {
      line = in.readLine();
      line = line.trimmed();
      if (line.startsWith("#") || line.isEmpty())
        continue;
      QRegularExpression *re = new QRegularExpression(
        line, QRegularExpression::ExtendedPatternSyntaxOption | QRegularExpression::UseUnicodePropertiesOption);
      if (re->isValid())
        gQtMessageFilters.append(re);
      else {
        QString message = QString("regular expression '%1' in file '%2' is invalid: %3")
                            .arg(line)
                            .arg(qtFiltersFilePath)
                            .arg(re->errorString());
        fprintf(stderr, "%s\n", message.toUtf8().constData());
      }
    }
  } else {
    QString message = QString("File not found: '%1'.").arg(qtFiltersFilePath);
    fprintf(stderr, "%s\n", message.toUtf8().constData());
  }

  // Putting break points in the catchMessageOutput and getting the stack allows to determine
  // efficiently what Webots statement is responsible to generate some Qt output
  qInstallMessageHandler(catchMessageOutput);

  QApplication::setAttribute(Qt::AA_Use96Dpi);

#ifdef _WIN32
  // fixes truncated menus on some screen configurations: https://bugreports.qt.io/browse/QTBUG-98347
  QGuiApplication::setHighDpiScaleFactorRoundingPolicy(Qt::HighDpiScaleFactorRoundingPolicy::Floor);
#endif

  WbGuiApplication app(argc, argv);
#ifdef _WIN32
  signal(SIGINT, quitApplication);  // Preserve Ctrl+C from cmd.exe.
#else
  // Configure the self-pipe before enabling any process signal callbacks.
  int quitPipe[2] = {-1, -1};
  if (pipe(quitPipe) != 0 || !configureQuitPipeFd(quitPipe[0]) || !configureQuitPipeFd(quitPipe[1])) {
    fprintf(stderr, "Fatal: cannot initialize Webots POSIX quit notifier.\n");
    if (quitPipe[0] >= 0)
      close(quitPipe[0]);
    if (quitPipe[1] >= 0)
      close(quitPipe[1]);
    return EXIT_FAILURE;
  }
  QSocketNotifier quitNotifier(quitPipe[0], QSocketNotifier::Read, &app);
  bool quitRequested = false;
  QObject::connect(&quitNotifier, &QSocketNotifier::activated, &app, [&]() {
    unsigned char pending[64];
    while (read(quitPipe[0], pending, sizeof(pending)) > 0) {
    }
    if (!quitRequested) {
      quitRequested = true;
      WbApplication::instance()->simulationQuit(EXIT_SUCCESS);
    }
  });
  gQuitNotificationFd = quitPipe[1];
  signal(SIGINT, quitApplication);
  signal(SIGTERM, quitApplication);
  signal(SIGQUIT, quitApplication);
  signal(SIGHUP, quitApplication);
  // Symptom: locale is wrong in dynamic libraries (i.e. physics plugin)
  // From http://qt-project.org/doc/qt-4.8/qcoreapplication.html :
  //   On Unix/Linux Qt is configured to use the system locale settings by default.
  //   This can cause a conflict when using POSIX functions, for instance, when
  //   converting between data types such as floats and strings, since the
  //   notation may differ between locales. To get around this problem, call
  //   the POSIX function setlocale(LC_NUMERIC,"C") right after initializing
  //   QApplication or QCoreApplication to reset the locale that is used for
  //   number formatting to "C"-locale.
  setlocale(LC_NUMERIC, "C");
#ifdef __APPLE__
  // 'LANG' can be set in the terminal.
  // - "fr_CH.UTF-8" may cause issues in procedural PROTO nodes.
  // - If "UTF-8" is not set, UTF-8 characters are not handled properly in some libraries, such as FreeType.
  setenv("LANG", "UTF-8", true);
#endif
#endif

#ifdef _WIN32
  return app.exec();
#else
  const int result = app.exec();
  gQuitNotificationFd = -1;
  signal(SIGINT, SIG_DFL);
  signal(SIGTERM, SIG_DFL);
  signal(SIGQUIT, SIG_DFL);
  signal(SIGHUP, SIG_DFL);
  quitNotifier.setEnabled(false);
  close(quitPipe[0]);
  close(quitPipe[1]);
  return result;
#endif
}
