"""Bounded Webots startup and cleanup evidence. No retry or oracle changes.

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

def cgroup_processes(limit=256, task_limit=1024):
    """Bounded exact-cgroup process and Linux task identities, not a leak verdict.

    cgroup pids.current counts threads and can include descendant cgroups;
    exact membership here cannot be equated with that counter. Never include
    argv, environments or raw process memory in public CI artifacts.
    """
    membership = read("/proc/self/cgroup", 4096)
    if not membership.strip() or membership.startswith("UNAVAILABLE:"):
        return {"status": "unavailable", "reason": membership[:128],
                "processes": [], "tasks": []}
    try:
        candidates = sorted((int(name) for name in os.listdir("/proc")
                             if name.isdecimal()))
    except OSError as error:
        return {"status": "unavailable", "reason": type(error).__name__,
                "processes": [], "tasks": []}
    try:
        namespace = os.readlink("/proc/self/ns/pid")
    except OSError:
        namespace = "UNAVAILABLE"
    result = {
        "status": "ok", "membership": membership.strip(),
        "pid_namespace": namespace, "scanned_visible": len(candidates),
        "matching_visible": 0, "matching_visible_tasks": 0,
        "truncated": False, "task_truncated": False,
        "scan_errors": 0, "processes": [], "tasks": [],
        "scope_limitation": "exact cgroup members only; pids.current may include descendant cgroups",
    }
    for pid in candidates:
        other = read("/proc/%d/cgroup" % pid, 4096)
        if other != membership:
            if other.startswith("UNAVAILABLE:"):
                result["scan_errors"] += 1
            continue
        stat = read("/proc/%d/stat" % pid, 4096)
        if ") " not in stat:
            result["scan_errors"] += 1
            continue
        try:
            tail = stat.rsplit(") ", 1)[1].split()
            identity = {
                "pid": pid, "ppid": int(tail[1]), "pgid": int(tail[2]),
                "sid": int(tail[3]), "state": tail[0],
                "start_ticks": int(tail[19]),
                "comm": stat.split("(", 1)[1].rsplit(")", 1)[0][:100],
            }
            try:
                identity["pid_namespace"] = os.readlink("/proc/%d/ns/pid" % pid)
            except OSError:
                identity["pid_namespace"] = "UNAVAILABLE"
                result["scan_errors"] += 1
        except (ValueError, IndexError):
            result["scan_errors"] += 1
            continue
        result["matching_visible"] += 1
        if len(result["processes"]) < limit:
            result["processes"].append(identity)
        else:
            result["truncated"] = True
        try:
            tids = sorted(int(tid) for tid in os.listdir("/proc/%d/task" % pid)
                          if tid.isdecimal())
        except OSError:
            result["scan_errors"] += 1
            continue
        for tid in tids:
            task_cgroup = read("/proc/%d/task/%d/cgroup" % (pid, tid), 4096)
            if task_cgroup != membership:
                if task_cgroup.startswith("UNAVAILABLE:"):
                    result["scan_errors"] += 1
                continue
            result["matching_visible_tasks"] += 1
            if len(result["tasks"]) >= task_limit:
                result["task_truncated"] = True
                continue
            task_stat = read("/proc/%d/task/%d/stat" % (pid, tid), 4096)
            if ") " not in task_stat:
                result["scan_errors"] += 1
                continue
            try:
                task_tail = task_stat.rsplit(") ", 1)[1].split()
                result["tasks"].append({
                    "pid": pid, "tid": tid,
                    "pid_start_ticks": identity["start_ticks"],
                    "tid_start_ticks": int(task_tail[19]),
                    "pid_namespace": identity["pid_namespace"],
                })
            except (ValueError, IndexError):
                result["scan_errors"] += 1
    if result["scan_errors"] or result["truncated"] or result["task_truncated"]:
        result["status"] = "partial"
    return result


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
        self.cgroup_before = cgroup_processes()
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

    def ready(self, child, stage):
        """Tiny comparison witness, including healthy isolated and later launches."""
        try:
            self.observe(child, force=True)
            code = child.poll()
            data = {
                "schema": 1, "status": stage,
                "sequence_index": self.sequence_index,
                "prior_trials_validated": self.sequence_index - 1,
                "elapsed_s": round(time.monotonic() - self.started, 3),
                "wrapper_pid": child.pid, "wrapper_returncode": code,
                "resources_before": self.before,
                "resources_at_readiness": resources(self.out),
                "cgroup_before": self.cgroup_before,
                "cgroup_at_readiness": cgroup_processes(),
                "process_samples": self.samples[:3] + self.samples[-1:],
            }
            (self.out / "startup-ready.json").write_text(
                json.dumps(data, sort_keys=True, indent=2) + "\n")
        except Exception:
            pass  # Observability may not change the native acceptance oracle.

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
                "cgroup_before": self.cgroup_before,
                "cgroup_on_failure": cgroup_processes(),
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
        """Capture task identity *after* the existing owned-group cleanup.

        A changed cgroup counter alone never assigns a survivor to Webots.
        """
        try:
            group = process_group(wrapper_pid)
            task_snapshot = cgroup_processes()
            post = resources(self.out)
            if self.failed:
                path = self.out / "startup-failure.json"
                if path.is_file():
                    data = json.loads(path.read_text())
                    data["process_group_after_cleanup"] = group
                    data["resources_after_cleanup"] = post
                    data["cgroup_after_cleanup"] = task_snapshot
                    path.write_text(json.dumps(data, sort_keys=True, indent=2) + "\n")
            else:
                (self.out / "startup-cleanup.json").write_text(
                    json.dumps({"schema": 1, "sequence_index": self.sequence_index,
                                "wrapper_pid": wrapper_pid,
                                "process_group_after_cleanup": group,
                                "resources_after_cleanup": post,
                                "cgroup_after_cleanup": task_snapshot},
                               sort_keys=True, indent=2) + "\n")
        except Exception:
            pass  # Diagnostics may not change the native oracle.
