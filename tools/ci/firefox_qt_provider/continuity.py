#!/usr/bin/env python3
"""Repair #301's measurement boundary with pre-shutdown controller evidence."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time

import qualify


def parse_continuity(text: str):
    if "CONTINUITY_V1 FATAL" in text:
        return None
    records = []
    for line in text.splitlines():
        match = re.fullmatch(r"CONTINUITY_V1 seq=(\d+) (.+)", line)
        if match:
            records.append((int(match[1]), match[2]))
    if len(records) < 17 or [seq for seq, _ in records[:17]] != list(range(1, 18)):
        return None
    details = [detail for _, detail in records[:17]]
    fixed = (
        r"event=CONTROLLER_STARTED pid=\d+",
        r"event=WB_INIT_RETURN time=([0-9.]+)",
        r"event=PROVIDER_CALLED",
        r"event=PROVIDER_RETURNED",
        r"event=LOOP_BEGIN time=([0-9.]+)",
    )
    captures = []
    for detail, pattern in zip(details[:5], fixed):
        match = re.fullmatch(pattern, detail)
        if not match:
            return None
        captures.append(match.groups())
    step_times = []
    for expected, detail in enumerate(details[5:13], 1):
        match = re.fullmatch(r"event=STEP n=(\d+) result=(-?\d+) time=([0-9.]+)", detail)
        if not match or int(match[1]) != expected or int(match[2]) != 0:
            return None
        step_times.append(float(match[3]))
    loop_end = re.fullmatch(r"event=LOOP_END before=([0-9.]+) after=([0-9.]+)", details[13])
    if not loop_end:
        return None
    if details[14:] != ["event=CAPABILITIES operationsReady=false", "event=PROVIDER_DESTROYED", "event=PRE_SHUTDOWN_READY"]:
        return None
    begin = float(captures[4][0])
    before, after = map(float, loop_end.groups())
    if not math.isclose(begin, before, abs_tol=1e-6) or not math.isclose(after - before, 0.256, abs_tol=0.001):
        return None
    previous = before
    for current in step_times:
        if not math.isclose(current - previous, 0.032, abs_tol=0.001):
            return None
        previous = current
    if not math.isclose(step_times[-1], after, abs_tol=1e-6):
        return None
    return {"records": details, "loop_before": before, "loop_after": after,
            "step_times": step_times, "pre_shutdown_ready": True}


def write_ack(path: Path) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(fd, b"continuity observed before shutdown\n")
        os.fsync(fd)
    finally:
        os.close(fd)
    directory = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def evaluate(log: str, witness, code: int, unchanged: bool, png_present: bool,
             continuity, shutdown_ack_observed: bool):
    if "Q87 FATAL" in log:
        return "FAIL" if "Q87 PROVIDER_CALLED" in log else "UNPROVEN"
    for marker in ("Q87 WB_INIT_RETURN", "Q87 PROVIDER_CALLED", "Q87 DIALOG_EXEC",
                   "Q87 DIALOG_EXPOSED", "Q87 DIALOG_CANCELLED result=Rejected"):
        if marker not in log:
            return "UNPROVEN"
    exposed = re.search(r"Q87 DIALOG_EXPOSED pid=(\d+) wid=(\d+)", log)
    if not witness or not exposed or witness.get("cancel") != "XTEST_ESCAPE" or not witness.get("focus_verified") or witness.get("map_state") != "IsViewable":
        return "UNPROVEN"
    if int(exposed[1]) != witness["pid"] or int(exposed[2]) != witness["window"] or not png_present:
        return "UNPROVEN"
    if continuity is None:
        return "UNPROVEN"
    if not shutdown_ack_observed or not unchanged or code != 0:
        return "FAIL"
    return "PASS"


def run(project: Path, evidence: Path, webots: Path) -> int:
    static = json.loads((evidence / "static-proof.json").read_text())
    binary = (project / "controllers/qt_provider_probe/qt_provider_probe").resolve()
    if hashlib.sha256(binary.read_bytes()).hexdigest() != static["binary_sha256"]:
        raise RuntimeError("characterized controller binary changed")
    observer = qualify.XObserver()
    before = qualify.snapshot(project / "files")
    witness = error = process_proof = continuity = pre_shutdown = None
    ack = evidence / "continuity-observed.ack"
    journal = evidence / "controller-continuity.log"
    with (evidence / "webots.log").open("w") as log:
        process = subprocess.Popen([str(webots / "webots"), "--stdout", "--stderr", "--batch", "--mode=realtime",
                                    str(project / "worlds/qualification.wbt")], stdout=log, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + 45
        try:
            while process.poll() is None and time.monotonic() < deadline:
                pid_file = evidence / "controller.pid"
                if pid_file.exists() and pid_file.read_text().strip():
                    pid = int(pid_file.read_text())
                    proc = Path(f"/proc/{pid}")
                    if proc.exists() and process_proof is None:
                        if (proc / "exe").resolve() != binary or not qualify.descendant(pid, process.pid):
                            raise RuntimeError("PID is not the exact official-Webots-launched probe")
                        process_proof = {"pid": pid, "binary": str(binary), "webots_ancestor_pid": process.pid}
                    if proc.exists() and witness is None:
                        mapped = observer.mapped_dialog(pid)
                        if mapped and (evidence / "dialog.png").exists():
                            maps = (proc / "maps").read_text()
                            (evidence / "controller-maps.txt").write_text(maps)
                            qt_paths = {line.split()[-1] for line in maps.splitlines() if "libQt6" in line or "libqxcb.so" in line}
                            if not qt_paths or not all(path.startswith(str(webots / "lib/webots") + "/") for path in qt_paths):
                                raise RuntimeError("live Qt/QPA maps differ from the pinned bundle")
                            if not any("libqxcb.so" in path for path in qt_paths):
                                raise RuntimeError("xcb plugin mapping not observed")
                            witness = observer.cancel(mapped)
                            qualify.write_json(evidence / "x11-witness.json", witness)
                if witness is not None and continuity is None and journal.exists():
                    candidate = parse_continuity(journal.read_text())
                    if candidate is not None:
                        if process.poll() is not None:
                            raise RuntimeError("continuity was not observed while Webots was alive")
                        continuity = candidate
                        payload = journal.read_bytes()
                        pre_shutdown = {
                            "observed_while_webots_alive": True,
                            "webots_pid": process.pid,
                            "host_monotonic_s": time.monotonic(),
                            "journal_sha256": hashlib.sha256(payload).hexdigest(),
                            "continuity": continuity,
                        }
                        qualify.write_json(evidence / "pre-shutdown-observation.json", pre_shutdown)
                        write_ack(ack)
                time.sleep(0.05)
            if process.poll() is None:
                error = "official Webots/probe did not complete within 45 s"
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)
    text = (evidence / "webots.log").read_text()
    unchanged = qualify.snapshot(project / "files") == before
    png = evidence / "dialog.png"
    png_present = png.exists() and png.stat().st_size > 100
    final_journal = journal.read_text() if journal.exists() else ""
    shutdown_ack_observed = "event=SHUTDOWN_ACK_OBSERVED" in final_journal
    result = evaluate(text, witness, process.returncode, unchanged, png_present,
                      continuity, shutdown_ack_observed)
    if error and result == "PASS":
        result = "UNPROVEN"
    if process_proof is None or pre_shutdown is None:
        result = "UNPROVEN"
    qualify.write_json(evidence / "result.json", {
        "result": result,
        "scope": "Qt provider display/cancel plus controller-owned pre-shutdown continuity",
        "static_proof": static,
        "process_proof": process_proof,
        "x11_witness": witness,
        "pre_shutdown_observation": pre_shutdown,
        "project_files_unchanged": unchanged,
        "webots_exit": process.returncode,
        "shutdown_ack_observed": shutdown_ack_observed,
        "error": error,
        "display": os.environ.get("DISPLAY"),
        "qpa_override": os.environ.get("QT_QPA_PLATFORM"),
        "full_firefox_parity": "UNPROVEN",
    })
    print(text)
    if journal.exists():
        print(final_journal)
    print("Q87_CONTINUITY_RESULT=" + result)
    return 0 if result == "PASS" else 1


if __name__ == "__main__":
    project, evidence, webots = map(Path, sys.argv[1:4])
    raise SystemExit(run(project, evidence, webots))
