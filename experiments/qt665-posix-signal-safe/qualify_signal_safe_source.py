"""Fail closed on upstream provenance; static only, NOT native qualification."""
import argparse
from pathlib import Path
import re
import subprocess
import tempfile
import shutil

UPSTREAM = "c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b"
SOURCE_BLOB = "d578afa7cbd27ea13fd9ca0583f5e12170c6fba3"

def cmd(*args, cwd=None):
    return subprocess.run(args, check=True, capture_output=True, text=True, cwd=cwd).stdout.strip()

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--upstream-tree", type=Path, required=True)
    args=parser.parse_args()
    upstream=args.upstream_tree.resolve()
    assert cmd("git","rev-parse","HEAD",cwd=upstream)==UPSTREAM, "wrong upstream HEAD"
    assert cmd("git","status","--porcelain",cwd=upstream)=="", "upstream checkout dirty"
    source=upstream/"src/webots/gui/main.cpp"
    assert cmd("git","hash-object",str(source),cwd=upstream)==SOURCE_BLOB, "unexpected upstream source"
    patch=Path(__file__).with_name("webots-r2025a-posix-quit-selfpipe.patch")
    text=patch.read_text()
    assert text.startswith("--- a/src/webots/gui/main.cpp\n+++ b/src/webots/gui/main.cpp\n")
    assert text.count("--- a/")==1 and text.count("+++ b/")==1, "patch changed additional paths"
    cmd("git","apply","--check",str(patch),cwd=upstream)
    with tempfile.TemporaryDirectory() as directory:
        dst=Path(directory)
        (dst/"src/webots/gui").mkdir(parents=True)
        shutil.copy2(source,dst/"src/webots/gui/main.cpp")
        cmd("git","apply",str(patch),cwd=dst)
        result=(dst/"src/webots/gui/main.cpp").read_text()
        unix=result.split("#ifndef _WIN32\n// A POSIX handler",1)
        assert len(unix)==2, "POSIX branch unavailable"
        handler=unix[1].split("static bool configureQuitPipeFd",1)[0]
        assert "write(" in handler and "savedErrno" in handler
        assert not re.search(r"malloc|calloc|free\(|new |WbApplication|QObject|emit |printf|fprintf",handler)
        assert "O_NONBLOCK" in result and "FD_CLOEXEC" in result
        assert "QSocketNotifier quitNotifier" in result
        assert "QObject::connect(&quitNotifier, &QSocketNotifier::activated" in result
        assert result.count("WbApplication::instance()->simulationQuit(EXIT_SUCCESS)") == 2
        assert "if (!quitRequested)" in result
        assert "#ifdef _WIN32\n  signal(SIGINT, quitApplication);" in result
        # The native FD-reuse counterexample refutes close/reset on app.exec exit.
        # Retain both ends for process lifetime: also avoids late-writer SIGPIPE.
        publication = "gQuitNotificationFd = quitPipe[1];"
        assert result.count(publication) == 1
        after_publication = result.split(publication, 1)[1]
        assert not re.search(r"\bclose\s*\(|\bSIG_DFL\b|gQuitNotificationFd\s*=", after_publication)
        assert result.rstrip().endswith("return app.exec();\n}")
        notification = result.split("QObject::connect(&quitNotifier", 1)[1].split(publication, 1)[0]
        assert "quitNotifier.setEnabled(false);" in notification
        assert notification.count("read(") == 1 and "while (" not in notification
        assert notification.index("quitRequested = true;") < notification.index("quitNotifier.setEnabled(false);")
        assert notification.index("quitNotifier.setEnabled(false);") < notification.index("WbApplication::instance()->simulationQuit")
    print("QT665_POSIX_QUIT_SOURCE_ONLY=PASS upstream="+UPSTREAM)
    print("NATIVE_COMPILE=NOT_TESTED QT_SIGNAL_DELIVERY=NOT_TESTED WEBOTS_BINARY=NOT_TESTED")
if __name__ == "__main__":
    main()
