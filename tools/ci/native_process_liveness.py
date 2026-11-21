"""Read-only Linux /proc evidence for a Webots CI process family.

This is a wall-clock diagnostic, never a simulation, safety, or PASS oracle.
"""
from __future__ import annotations
from pathlib import Path

def snapshot(root_pid: int, proc_root: Path = Path('/proc')) -> dict:
    """Observe the family without signalling, attaching or pausing.

    Descendants may have different process groups. Processes may disappear
    between reads; no absence or CPU-stasis is itself a native failure proof.
    """
    processes = {}
    try:
        entries = list(proc_root.iterdir())
    except OSError as exc:
        return {'available': False, 'error': type(exc).__name__, 'processes': []}
    for entry in entries:
        if not entry.name.isdecimal():
            continue
        try:
            stat = (entry / 'stat').read_text(encoding='utf-8')
            close = stat.rfind(') ')
            if close == -1 or not stat.startswith(entry.name + ' ('):
                continue
            fields = stat[close + 2:].split()
            if len(fields) < 22:
                continue
            pid = int(entry.name)
            processes[pid] = {
                'pid': pid, 'comm': stat[len(entry.name) + 2:close],
                'state': fields[0], 'ppid': int(fields[1]),
                'pgrp': int(fields[2]), 'user_ticks': int(fields[11]),
                'system_ticks': int(fields[12]), 'rss_pages': int(fields[21]),
            }
        except (OSError, ValueError, IndexError, UnicodeError):
            continue
    selected = {root_pid}
    changed = True
    while changed:
        before = len(selected)
        selected.update(pid for pid, value in processes.items()
                        if value['ppid'] in selected or value['pgrp'] == root_pid)
        changed = len(selected) != before
    observed = []
    for pid in sorted(selected):
        if pid not in processes:
            continue
        row = processes[pid]
        try:
            row['wchan'] = (proc_root / str(pid) / 'wchan').read_text(
                encoding='utf-8').strip()[:96]
        except (OSError, UnicodeError):
            row['wchan'] = None
        observed.append(row)
    return {'available': True, 'root_seen': root_pid in processes,
            'processes': observed[:32], 'truncated': len(observed) > 32}
