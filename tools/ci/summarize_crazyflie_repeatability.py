#!/usr/bin/env python3
import argparse
import json
import math
import statistics
from pathlib import Path

METRICS = (
    "error_xy",
    "yaw_error_deg",
    "altitude_min",
    "altitude_max",
    "total_s",
)


def parse_result(path: Path):
    line = path.read_text(encoding="utf-8").strip().splitlines()[-1]
    tokens = line.split()
    if not tokens or tokens[0] != "WEBEEBLOCKS_CF_SQUARE_RESULT":
        raise ValueError(f"{path}: invalid result prefix")

    values = {}
    for token in tokens[1:]:
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        values[key] = value

    if values.get("status") != "success":
        raise ValueError(f"{path}: status is not success")
    if values.get("legs") != "4":
        raise ValueError(f"{path}: legs is not 4")

    parsed = {"file": str(path), "status": "success", "legs": 4}
    for metric in METRICS:
        if metric not in values:
            raise ValueError(f"{path}: missing metric {metric}")
        number = float(values[metric])
        if not math.isfinite(number):
            raise ValueError(f"{path}: non-finite metric {metric}")
        parsed[metric] = number
    return parsed


def stats(values):
    return {
        "mean": statistics.fmean(values),
        "min": min(values),
        "max": max(values),
        "stdev": statistics.pstdev(values),
    }


def summarize(paths):
    runs = [parse_result(path) for path in paths]
    if len(runs) != 10:
        raise ValueError(f"expected exactly 10 results, got {len(runs)}")

    aggregate = {
        metric: stats([run[metric] for run in runs])
        for metric in METRICS
    }
    return {
        "success_count": len(runs),
        "run_count": len(runs),
        "runs": runs,
        "aggregate": aggregate,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("results", nargs="+")
    parser.add_argument("--json", required=True, dest="json_path")
    parser.add_argument("--text", required=True, dest="text_path")
    args = parser.parse_args()

    paths = [Path(p) for p in args.results]
    summary = summarize(paths)

    Path(args.json_path).write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    lines = [f"success_count={summary['success_count']} run_count={summary['run_count']}"]
    for metric in METRICS:
        item = summary["aggregate"][metric]
        lines.append(
            f"{metric} mean={item['mean']:.6f} min={item['min']:.6f} "
            f"max={item['max']:.6f} stdev={item['stdev']:.6f}"
        )
    Path(args.text_path).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
