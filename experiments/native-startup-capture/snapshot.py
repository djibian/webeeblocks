#!/usr/bin/env python3
"""Snapshot a debugger-identified, stopped process using procfs identity."""
import argparse
from pathlib import Path
from support import read, snapshot_process

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--proc-pid', required=True, type=int)
p.add_argument('--start-ticks', required=True, type=int)
p.add_argument('--boot-id', required=True)
p.add_argument('--exe-sha256', required=True)
p.add_argument('--output', required=True, type=Path)
a = p.parse_args()
if read('/proc/sys/kernel/random/boot_id').strip() != a.boot_id:
    raise SystemExit('boot identity mismatch')
snapshot_process(a.proc_pid, a.start_ticks, a.exe_sha256, a.output)
