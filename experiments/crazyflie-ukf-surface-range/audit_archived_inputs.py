#!/usr/bin/env python3
"""Inventory #180/#236/#251 bytes and observed inputs; never infer flight PASS.

Run from any directory. Output is derived JSON on stdout; raw evidence is opened
read-only. Historical scripts and TOC caches are never executed or counted as
measurements. SOURCE/manifest consistency proves integrity against the retained
import, not independent authentication of the original capture or archive.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import statistics
import sys


ROOT = Path(__file__).resolve().parent / "evidence"
INPUT_GROUPS = {
    "barometer": ("baro.asl", "baro.pressure", "baro.temp"),
    "accelerometer": ("acc.x", "acc.y", "acc.z"),
    "gyroscope": ("gyro.x", "gyro.y", "gyro.z"),
    "attitude_diagnostic": ("stabilizer.roll", "stabilizer.pitch"),
}
PROBES = (
    "sensorFilter.baroHeight", "sensorFilter.surfBaroD",
    "sensorFilter.baro0", "sensorFilter.baroDec", "sensorFilter.lateElig",
)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verified_files(directory: Path) -> tuple[dict, dict[str, bytes]]:
    source = json.loads((directory / "SOURCE.json").read_bytes())
    entries = source["machine_readable_files"]
    expected = {entry["path"]: entry for entry in entries}
    if len(expected) != len(entries) or not expected:
        raise ValueError(f"{directory.name}: duplicate or empty source inventory")
    manifest = {}
    for line in (directory / "MANIFEST.sha256").read_text().splitlines():
        sha, name = line.split("  ", 1)
        if name in manifest:
            raise ValueError(f"duplicate manifest path: {name}")
        manifest[name] = sha
    actual = {str(p.relative_to(directory)) for p in (directory / "raw").rglob("*")
              if p.is_file()}
    if set(expected) != set(manifest) or set(expected) != actual:
        raise ValueError(f"{directory.name}: missing/unexpected raw files")
    files = {}
    for name, entry in sorted(expected.items()):
        path = directory / name
        if not name.startswith("raw/") or ".." in Path(name).parts:
            raise ValueError(f"invalid raw path: {name}")
        if path.is_symlink() or not path.resolve().is_relative_to(directory.resolve()):
            raise ValueError(f"non-local raw path: {name}")
        data = path.read_bytes()
        if digest(data) != manifest[name] or digest(data) != entry["sha256"]:
            raise ValueError(f"digest mismatch: {name}")
        if len(data) != entry["bytes"]:
            raise ValueError(f"size mismatch: {name}")
        files[name] = data
    return source, files


def inventory_csv(name: str, data: bytes) -> dict:
    reader = csv.DictReader(io.StringIO(data.decode("utf-8"), newline=""))
    columns = reader.fieldnames
    if not columns or len(columns) != len(set(columns)):
        raise ValueError(f"missing/duplicate CSV header: {name}")
    rows = list(reader)
    if not rows or any(None in row or None in row.values() for row in rows):
        raise ValueError(f"empty/malformed CSV: {name}")
    excluded = any("excluded" in part for part in Path(name).parts)
    result = {"path": name, "rows": len(rows), "columns": columns,
              "excluded_from_physical_verdict": excluded}
    if "event" in columns:
        result["markers"] = rows
        return result
    numeric = {col: [float(row[col]) for row in rows] for col in columns}
    result["nonfinite_cells"] = sum(not math.isfinite(v)
                                    for vals in numeric.values() for v in vals)
    stamp = "cf_timestamp_ms" if "cf_timestamp_ms" in columns else "Timestamp"
    ts = numeric[stamp]
    dt = [b - a for a, b in zip(ts, ts[1:])]
    result["log_clock"] = {
        "column": stamp, "duration_ms": ts[-1] - ts[0],
        "median_step_ms": statistics.median(dt) if dt else None,
        "max_step_ms": max(dt) if dt else None,
        "nonincreasing_steps": sum(d <= 0 for d in dt),
        "boundary": "log timestamps, not per-sensor producer timestamps",
    }
    result["diagnostic_probes"] = {}
    for col in PROBES:
        if col not in numeric:
            continue
        vals = [v for v in numeric[col] if math.isfinite(v)]
        result["diagnostic_probes"][col] = {
            "finite_samples": len(vals), "distinct_values": len(set(vals)),
            "minimum": min(vals) if vals else None,
            "maximum": max(vals) if vals else None,
        }
    return result


def audit(root: Path) -> dict:
    checkpoints = []
    for number in (180, 236, 251):
        directory = root / f"checkpoint-{number}"
        source, files = verified_files(directory)
        if source["checkpoint"] != number:
            raise ValueError(f"wrong checkpoint identity: {number}")
        csvs = [inventory_csv(name, data) for name, data in files.items()
                if name.endswith(".csv")]
        observed = {col for item in csvs if not item["excluded_from_physical_verdict"]
                    for col in item["columns"]}
        missing = {group: [col for col in names if col not in observed]
                   for group, names in INPUT_GROUPS.items()}
        checkpoints.append({
            "checkpoint": number, "verified_files": len(files),
            "csv_files": len(csvs),
            "excluded_csv_files": sum(item["excluded_from_physical_verdict"] for item in csvs),
            "source_archive_sha256": source["source_archive_sha256"],
            "source_issue_comment": source["source_issue_comment"],
            "archive_digest_previously_published": source["expected_archive_sha256"] is not None,
            "manifest_sha256": digest((directory / "MANIFEST.sha256").read_bytes()),
            "source_json_sha256": digest((directory / "SOURCE.json").read_bytes()),
            "omissions": source["skipped_files"],
            "missing_observed_columns": missing,
            "independent_displacement": "UNPROVEN" if any(
                missing[group] for group in ("barometer", "accelerometer", "gyroscope")
            ) else "REQUIRES_SCIENTIFIC_REVIEW",
            "csv_inventory": csvs,
        })
    return {
        "schema": "webeeblocks.x3.archived-input-inventory.v1",
        "scope": "retained text import from #292; original binary archives not re-fetched",
        "checkpoints": checkpoints,
        "boundary": "Header presence is not signal validity, metric ground truth or acceptance. "
                    "No imputation, estimator fitting, confidence interval or physical verdict.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-root", type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        report = audit(args.evidence_root)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"ARCHIVE_AUDIT_ERROR: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))
    return 0  # Successful inventory, never a scientific or human PASS.


if __name__ == "__main__":
    raise SystemExit(main())
