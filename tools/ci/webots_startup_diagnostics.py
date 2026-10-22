"""Fail-only bounded Webots startup evidence. No retry or scientific oracle changes.

Never upload raw cores: process memory may contain confidential material.
"""
import json
import os
from pathlib import Path
import re
import resource
import shutil
import subprocess
import time


def read(path, maximum=8192):
    try:
        with open(path, "rb") as f:
            return f.read(maximum).decode("utf-8", "replace")
    except OSError as error:
        return "UNAVAILABLE: " + type(error).__name__


def process_group(pgid):
    """Collect all living children sharing the owned wrapper's process group."""
    rows = []
    try:
        names = os.listdir("/proc")
    except OSError:
        return rows
    for name in names:
        if not name.isdecimal():
            continue
        stat = read("/proc/" + name + "/stat", 4096)
        if ") " not in stat:
            continue
        try:
            tail = stat.rsplit(") ", 1)[1].split()
            if int(tail[2]) != pgid:
                continue
            status = read("/proc/" + name + "/status")
            rss = next((s.strip() for s in status.splitlines()
                        if s.startswith("VmRSS:")), None)
            rows.append({
                "pid": int(name), "ppid": int(tail[1]), "pgid": int(tail[2]),
                "sid": int(tail[3]), "state": tail[0],
                "comm": stat.split("(", 1)[1].rsplit(")", 1)[0][:100],
                "cmdline": read("/proc/" + name + "/cmdline", 512)
                .replace("\x00", " ").strip()[:512],
                "rss": rss,
            })
        except (ValueError, IndexError):
            continue
    return sorted(rows, key=lambda p: p["pid"])


def resources(directory):
    mem = read("/proc/meminfo")
    mem = {s.split(":", 1)[0]: s.split(":", 1)[1].strip()
           for s in mem.splitlines() if s.startswith((
               "MemTotal:", "MemAvailable:", "SwapTotal:", "SwapFree:"))}
    cgroup = {name: read("/sys/fs/cgroup/" + name).strip()[:4096] for name in (
        "memory.current", "memory.max", "memory.peak", "memory.events",
        "pids.current", "pids.max", "pids.events", "cpu.pressure")}
    try:
        disk = shutil.disk_usage(directory)
        disk_info = {"free_bytes": disk.free, "total_bytes": disk.total}
    except OSError as error:
        disk_info = {"error": type(error).__name__}
    return {
        "meminfo": mem, "cgroup_v2": cgroup, "disk": disk_info,
        "loadavg": list(os.getloadavg()),
        "rlimit_core_bytes": list(resource.getrlimit(resource.RLIMIT_CORE)),
        "core_pattern": read("/proc/sys/kernel/core_pattern").strip(),
        "core_uses_pid": read("/proc/sys/kernel/core_uses_pid").strip(),
    }


class StartupEvidence:
    """Hold cheap samples in memory; persist detailed evidence on missing READY."""

    def __init__(self, out, sequence_index, launch, env, cwd=None):
        self.out = Path(out)
        self.cwd = Path(cwd) if cwd is not None else self.out
        self.sequence_index = sequence_index
        self.launch = list(launch)
        self.env = {name: env.get(name) for name in (
            "DISPLAY", "LIBGL_ALWAYS_SOFTWARE", "XDG_RUNTIME_DIR",
            "WEBOTS_HOME", "LP_NUM_THREADS")}
        self.started = time.monotonic()
        self.wall_start = time.time()
        self.before = resources(self.out)
        self.samples = []
        self.last_sample = -1.0
        self.failed = False

    def observe(self, child, force=False):
        try:
            age = time.monotonic() - self.started
            if force or (age - self.last_sample >= 0.35 and len(self.samples) < 40):
                self.samples.append({"elapsed_s": round(age, 3),
                                     "processes": process_group(child.pid)})
                self.last_sample = age
        except Exception:
            pass  # Diagnostics must not influence READY.

    def core_details(self, home, log):
        pids = [int(pid) for pid in re.findall(
            r"line \d+:\s*(\d+)\s+Segmentation fault", log)]
        result = {"native_sigsegv_pids_in_log": pids,
                  "raw_core_retained": False,
                  "raw_core_policy": "no raw process memory in public CI artifacts"}
        candidates = []
        try:
            for path in self.cwd.glob("core*"):
                if path.is_file() and path.stat().st_mtime >= self.wall_start - 1:
                    candidates.append(path)
        except OSError:
            pass
        candidates = sorted(candidates, key=lambda p: p.stat().st_mtime,
                            reverse=True)[:3]
        result["local_cores"] = [
            {"name": p.name, "size_bytes": p.stat().st_size} for p in candidates]
        if not candidates:
            result["backtrace"] = "no local core (may be disabled or piped by core_pattern)"
            return result
        debugger = shutil.which("gdb")
        binary = Path(home) / "bin/webots-bin"
        if debugger is None or not binary.is_file():
            result["backtrace"] = "gdb or webots-bin unavailable"
            return result
        try:
            bt = subprocess.run([
                debugger, "-q", "-nx", "-batch",
                "-ex", "set debuginfod enabled off",
                "-ex", "thread apply all bt", str(binary), str(candidates[0])],
                capture_output=True, text=True, errors="replace",
                timeout=12, check=False)
            (self.out / "startup-backtrace.txt").write_text(
                (bt.stdout + "\n" + bt.stderr)[:65536])
            result["backtrace"] = {
                "file": "startup-backtrace.txt", "gdb_returncode": bt.returncode,
                "output_capped_at_chars": 65536}
        except (OSError, subprocess.TimeoutExpired) as error:
            result["backtrace"] = type(error).__name__
        return result

    def failure(self, child, home, log_path):
        self.failed = True
        try:
            self.observe(child, force=True)
            code = child.poll()
            data = {
                "schema": 1, "status": "NATIVE_READY_MISSING",
                "sequence_index": self.sequence_index,
                "prior_trials_validated": self.sequence_index - 1,
                "elapsed_s": round(time.monotonic() - self.started, 3),
                "wrapper_pid": child.pid, "wrapper_returncode": code,
                "wrapper_signal": -code if code is not None and code < 0 else None,
                "launch": self.launch, "environment": self.env,
                "resources_before": self.before,
                "resources_on_failure": resources(self.out),
                "process_samples": self.samples,
                "core": self.core_details(home, Path(log_path).read_text(errors="replace")),
                "webots_version": read(Path(home) / "resources/version.txt").strip(),
            }
            (self.out / "startup-failure.json").write_text(
                json.dumps(data, sort_keys=True, indent=2) + "\n")
        except Exception as error:
            try:
                (self.out / "startup-diagnostic-error.txt").write_text(
                    type(error).__name__ + ": " + str(error)[:500] + "\n")
            except OSError:
                pass

    def after_cleanup(self, wrapper_pid):
        if not self.failed:
            return
        try:
            path = self.out / "startup-failure.json"
            if path.is_file():
                data = json.loads(path.read_text())
                data["process_group_after_cleanup"] = process_group(wrapper_pid)
                data["resources_after_cleanup"] = resources(self.out)
                path.write_text(json.dumps(data, sort_keys=True, indent=2) + "\n")
        except Exception:
            pass  # Preserve the original startup failure.
