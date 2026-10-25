#!/usr/bin/env python3
"""Read-only CI performance / historical-evidence audit. Never grants a CI GO.

The canonical CI Gate remains the sole automated merge check. This script uses
public GitHub Actions run/job metadata, not billable-minute or coverage claims.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import statistics
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

WORKFLOW = "ci.yml"
SHARDS = tuple(f"Runtime suite / runtime-v2-progression (shard {n})" for n in range(7))
HISTORICAL_NAMES = ("historical", "webots-smoke")
SETUP_KINDS = ("webots_pull", "blockly_assets")


def timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def minutes(start: str | None, end: str | None) -> float | None:
    if not start or not end:
        return None
    return max(0.0, (timestamp(end) - timestamp(start)).total_seconds() / 60)


def observed_setup(jobs: list[dict]) -> dict:
    """Measure named setup steps, not total setup cost or billing.

    Missing timing is unknown rather than zero; skipped steps consume no
    observed setup time. Only completed successful CI runs enter the cohort.
    """
    result = {kind: {"steps": 0, "missing_timing": 0, "minutes": 0.0}
              for kind in SETUP_KINDS}
    for job in jobs:
        for step in job.get("steps") or ():
            name = step.get("name") or ""
            if name == "Pull official Webots R2025a image":
                kind = "webots_pull"
            elif name.startswith("Prepare ") and "Blockly 13.2.1" in name:
                kind = "blockly_assets"
            else:
                continue
            if step.get("conclusion") == "skipped":
                continue
            observed = result[kind]
            observed["steps"] += 1
            duration = minutes(step.get("started_at"), step.get("completed_at"))
            if duration is None:
                observed["missing_timing"] += 1
            else:
                observed["minutes"] += duration
    for observed in result.values():
        observed["minutes"] = (None if observed["missing_timing"] else
                               round(observed["minutes"], 3))
    return result


def get_json(url: str, token: str) -> dict:
    request = Request(url, headers={
        "Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "webeeblocks-ci-optimization/1",
    })
    with urlopen(request, timeout=20) as response:
        data = json.load(response)
    if not isinstance(data, dict):
        raise ValueError(f"Unexpected GitHub API JSON at {url}")
    return data


def fetch_jobs(api: str, repo: str, run_id: int, token: str, *, max_pages: int = 5) -> list[dict]:
    jobs: list[dict] = []
    total = None
    for page in range(1, max_pages + 1):
        url = f"{api}/repos/{repo}/actions/runs/{run_id}/jobs?" + urlencode({"per_page": 100, "page": page})
        payload = get_json(url, token)
        if total is None:
            total = payload.get("total_count")
            if not isinstance(total, int) or total < 0:
                raise ValueError(f"Missing job count for run {run_id}")
        batch = payload.get("jobs")
        if not isinstance(batch, list):
            raise ValueError(f"Missing job array for run {run_id}")
        jobs.extend(batch)
        if len(jobs) >= total:
            if len(jobs) != total:
                raise ValueError(f"Inconsistent job pagination for {run_id}")
            return jobs
        if not batch:
            break
    raise ValueError(f"Incomplete job pagination for run {run_id} ({len(jobs)}/{total})")


def fetch_runs(api: str, repo: str, token: str, *, days: int, limit: int, now: datetime) -> list[dict]:
    since = (now - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    found: list[dict] = []
    # Fixed upper bound: 2*limit API records; reports are samples, not exhaustive history.
    max_pages = min(5, (2 * limit + 99) // 100 + 1)
    for page in range(1, max_pages + 1):
        query = urlencode({"per_page": 100, "page": page, "status": "completed", "created": f">={since}"})
        payload = get_json(f"{api}/repos/{repo}/actions/workflows/{WORKFLOW}/runs?{query}", token)
        batch = payload.get("workflow_runs")
        if not isinstance(batch, list):
            raise ValueError("Missing canonical workflow_runs array")
        for run in batch:
            if run.get("event") not in {"pull_request", "schedule", "workflow_dispatch"}:
                continue
            if not isinstance(run.get("id"), int) or not run.get("head_sha"):
                continue
            found.append(run)
            if len(found) >= limit:
                return found
        if len(batch) < 100:
            break
    return found


def summarize_run(run: dict, jobs: list[dict]) -> dict:
    names = {j.get("name"): j for j in jobs}
    gate = names.get("CI Gate")
    selected_runtime = any(str(n).startswith("Runtime suite / ") for n in names)
    selected_webots = any(str(n).startswith("Webots suite / ") for n in names)
    all_success = bool(jobs) and all(j.get("status") == "completed" and j.get("conclusion") == "success" for j in jobs)
    # The presence of both complete suite job sets matters; a selected suite
    # skipped because of a selector bug must not become a 'full' observation.
    has_shards = all(name in names and names[name].get("conclusion") == "success" for name in SHARDS)
    any_shards = any(name in names for name in SHARDS)
    full_success = (run.get("status") == "completed" and run.get("conclusion") == "success"
                    and gate is not None and gate.get("conclusion") == "success"
                    and selected_runtime and selected_webots and all_success
                    and (not any_shards or has_shards))
    job_minutes = [minutes(j.get("started_at"), j.get("completed_at")) for j in jobs]
    job_minutes = [v for v in job_minutes if v is not None]
    active = {j["name"]: round(minutes(j.get("started_at"), j.get("completed_at")), 3)
              for j in jobs if j.get("name") and minutes(j.get("started_at"), j.get("completed_at")) is not None}
    return {
        "id": run["id"], "head_sha": run.get("head_sha"), "event": run.get("event"),
        "run_attempt": run.get("run_attempt"), "status": run.get("status"),
        "conclusion": run.get("conclusion"), "url": run.get("html_url"),
        "wall_minutes": minutes(run.get("run_started_at"), run.get("updated_at")),
        "runner_minutes_estimate": round(sum(job_minutes), 3),
        "job_count": len(jobs), "job_set": sorted(str(j.get("name")) for j in jobs),
        "all_jobs_success": all_success,
        "full_success": full_success, "seven_shards_proven": has_shards,
        "gate": gate.get("conclusion") if gate else None,
        "jobs": active, "setup": observed_setup(jobs),
        "non_success": [{"name": j.get("name"), "result": j.get("conclusion")}
                        for j in jobs if j.get("conclusion") != "success"],
    }


def inventory(root: Path) -> dict:
    paths = (root / ".github/workflows/ci-runtime.yml", root / ".github/workflows/ci-webots.yml")
    result: dict[str, dict] = {}
    for path in paths:
        text = path.read_text(encoding="utf-8")
        result[path.name] = {
            "lines": len(text.splitlines()),
            "explicit_docker_pull": text.count("docker pull cyberbotics/webots:R2025a-ubuntu22.04"),
            "apt_get_update": text.count("apt-get update"),
            "runtime_asset_preparation_refs": text.count("prepare_runtime_v2"),
        }
    return result


def discover(runs: list[dict], counts: dict, *, comparable_successes: list[dict] | None = None) -> list[dict]:
    # Only compare job durations within the same selected workload and trigger.
    successes = (comparable_successes if comparable_successes is not None else
                 [r for r in runs if r["full_success"] and r["seven_shards_proven"]])
    proposals = []
    if successes:
        grouped: dict[str, list[float]] = {}
        for run in successes:
            for name, duration in run["jobs"].items():
                grouped.setdefault(name, []).append(duration)
        for name, durations in grouped.items():
            if len(durations) >= 3 and statistics.median(durations) >= 12:
                proposals.append({"kind": "critical_path", "candidate": name,
                                  "median_minutes": round(statistics.median(durations), 2),
                                  "sample": len(durations),
                                  "proposal": "Investigate bounded partitioning or setup cost without dropping native evidence."})
        historical = [(name, d) for name, d in grouped.items() if any(tag in name.lower() for tag in HISTORICAL_NAMES)]
        if historical:
            costs = [sum(run["jobs"].get(name, 0) for name, _ in historical) for run in successes]
            proposals.append({"kind": "historical_audit", "jobs": sorted(name for name, _ in historical),
                              "median_runner_minutes": round(statistics.median(costs), 2),
                              "proposal": "Review active product dependencies before considering any retirement; no automatic deletion."})
    repeated = sum(v["explicit_docker_pull"] for v in counts.values())
    if repeated >= 5:
        proposals.append({"kind": "repeated_setup", "explicit_docker_pull_sites": repeated,
                          "proposal": "Compare content-addressed, verified image provisioning to cold pulls; preserve pinned Webots."})
    errors = [r for r in runs if r["conclusion"] == "failure"]
    if errors:
        names = Counter(j["name"] for r in errors for j in r["non_success"]
                        if j["name"] != "CI Gate" and j["result"] == "failure")
        for name, count in names.most_common(3):
            proposals.append({"kind": "reliability", "candidate": name, "failed_runs": count,
                              "proposal": "Investigate original failing evidence; do not blindly retry or weaken oracle."})
    return proposals


def build_report(repo: str, runs: list[dict], counts: dict, *, days: int, now: datetime) -> tuple[dict, str]:
    eligible = [r for r in runs if r["full_success"] and r["seven_shards_proven"]]
    # The most recent eligible run defines the comparison cohort. Mixing selected
    # job sets (or event types) confounds runner-minute and duration medians.
    anchor = eligible[0] if eligible else None
    complete = ([r for r in eligible
                 if r["event"] == anchor["event"] and r["job_set"] == anchor["job_set"]][:12]
                if anchor else [])
    comparable_ids = {r["id"] for r in complete}
    def median(key: str) -> float | None:
        values = [r[key] for r in complete if r[key] is not None]
        return round(statistics.median(values), 2) if values else None
    # Avoid an apparently precise zero when an expected step has no timing.
    # A category not observed in every cohort run has no comparable median.
    setup_medians = {
        kind: (round(statistics.median(r["setup"][kind]["minutes"] for r in complete), 2)
               if complete and all(r["setup"][kind]["steps"] > 0 and
                                   r["setup"][kind]["minutes"] is not None for r in complete)
               else None)
        for kind in SETUP_KINDS
    }
    data = {
        "schema": "webeeblocks-ci-optimization-v1", "generated_at": now.isoformat(),
        "repository": repo, "window_days": days, "inspected_runs": len(runs),
        "full_successful_sharded_runs": len(complete),
        "eligible_before_cohort_filter": len(eligible),
        "cohort_reference_run_id": anchor["id"] if anchor else None,
        "cohort_event": anchor["event"] if anchor else None,
        "cohort_job_count": len(anchor["job_set"]) if anchor else None,
        "coverage_disclaimer": "Gate/job metadata is NOT proof of test coverage or product correctness.",
        "wall_median_minutes": median("wall_minutes"),
        "runner_median_minutes_estimate": median("runner_minutes_estimate"),
        "observed_setup_median_runner_minutes": setup_medians,
        "counts": counts,
        "candidates": discover(runs, counts, comparable_successes=complete),
        "runs": [{**{k: v for k, v in r.items() if k not in ("jobs", "job_set")},
                  "cohort_comparable": r["id"] in comparable_ids} for r in runs],
    }
    lines = [f"# CI optimization — {repo}", "", f"Generated UTC: {now.isoformat()}",
             f"Window: {days} days; completed canonical CI runs inspected: {len(runs)}.",
             f"Comparable successful same-workload sharded runs: {len(complete)} "
             f"(of {len(eligible)} eligible; same event and exact job set; at most 12).",
             f"Reference run: {anchor['id'] if anchor else 'none'}; "
             f"job count: {len(anchor['job_set']) if anchor else 'n/a'}.", "",
             "**Advisory only.** This report does not change CI Gate, selection, safety oracles or repository contents.",
             "A green Gate and job list cannot alone prove that the selector ran every affected oracle.", "",
             f"Median elapsed (min): **{data['wall_median_minutes']}**; "
             f"median summed runner minutes (not billing): **{data['runner_median_minutes_estimate']}**.", "",
             "## Measured repeated preparation (same-workload cohort)", "",
             f"Median observed Webots image pull steps (runner min): "
             f"**{setup_medians['webots_pull']}**.",
             f"Median observed Blockly asset preparation steps (runner min): "
             f"**{setup_medians['blockly_assets']}**.",
             "Only explicitly named steps are measured: this is NOT all setup time, "
             "billing, or proof that caching would reduce elapsed time.",
             "None means insufficient comparable step timing or no matching step; "
             "it never means a free operation.", "",
             "## Proposals requiring dedicated CI and independent V5 review", ""]
    if not complete:
        lines.append("Not enough fully successful sharded evidence; no performance claim.")
    if not data["candidates"]:
        lines.append("No candidates meet the current reporting rules.")
    for item in data["candidates"]:
        lines.append(f"- **{item['kind']}** — {item.get('candidate', 'relevant CI area')}: {item['proposal']}")
    lines += ["", "## Provenance (latest inspected runs)", "",
              "| Run | Event | Result | Full evidence | Wall min | Runner min* | Pull steps | Pull runner min* |", "|---|---|---|---|---:|---:|---:|---:|"]
    for r in runs[:25]:
        lines.append(f"| [{r['id']}]({r['url']}) | {r['event']} | {r['conclusion']} | "
                     f"{'yes' if r['id'] in comparable_ids else 'no'} | "
                     f"{r['wall_minutes']} | {r['runner_minutes_estimate']} | "
                     f"{r['setup']['webots_pull']['steps']} | "
                     f"{r['setup']['webots_pull']['minutes']} |")
    lines += ["", "*Full evidence in this table means same-workload comparability; "
              "it does not prove selection of every scientifically applicable oracle.",
              "*Sum of job occupied minutes, **not** invoiced GitHub usage.",
              "This is a bounded sample, not an exhaustive history or a causal before/after experiment.",
              "Same event and job names do not prove identical workloads, changed source, cache state or runner conditions.", "",
              "## CI setup inventory", "", "~~~json", json.dumps(counts, indent=2, sort_keys=True), "~~~", ""]
    return data, "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--days", type=int, default=21)
    parser.add_argument("--max-runs", type=int, default=60)
    parser.add_argument("--out-dir", type=Path, default=Path("ci-artifacts/ci-optimization"))
    args = parser.parse_args()
    token = os.environ.get("GITHUB_TOKEN")
    if not token or args.repository.count("/") != 1:
        parser.error("GITHUB_TOKEN and a repository in owner/name format are required")
    if not 1 <= args.days <= 90 or not 1 <= args.max_runs <= 100:
        parser.error("bounded ranges: days 1..90 and max-runs 1..100")
    now = datetime.now(timezone.utc)
    api = os.environ.get("GITHUB_API_URL", "https://api.github.com").rstrip("/")
    # Treat incomplete API evidence as error rather than silently reporting 0 runs.
    try:
        raw = fetch_runs(api, args.repository, token, days=args.days, limit=args.max_runs, now=now)
        records = [summarize_run(r, fetch_jobs(api, args.repository, r["id"], token)) for r in raw]
        data, report = build_report(args.repository, records, inventory(Path.cwd()), days=args.days, now=now)
    except (HTTPError, URLError, ValueError, KeyError, OSError) as exc:
        print(f"CI optimization: INCOMPLETE INPUT: {exc}", file=sys.stderr)
        return 1
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "report.json").write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (args.out_dir / "report.md").write_text(report, encoding="utf-8")
    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(summary, "a", encoding="utf-8") as stream:
            stream.write(report)
    print(report)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
