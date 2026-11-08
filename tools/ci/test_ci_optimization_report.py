#!/usr/bin/env python3
"""Adversarial tests for the strictly non-decision CI metrics analyzer."""

import importlib.util
from datetime import datetime, timezone
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import patch

SCRIPT = Path(__file__).with_name("ci_optimization_report.py")
spec = importlib.util.spec_from_file_location("ci_optimization_report", SCRIPT)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def job(name, *, conclusion="success", started="2026-10-23T10:00:00Z",
        finished="2026-10-23T10:05:00Z", status="completed"):
    return {"name": name, "status": status, "conclusion": conclusion,
            "started_at": started, "completed_at": finished}


def run(*, result="success", ident=42):
    return {"id": ident, "head_sha": "f" * 40, "event": "pull_request",
            "status": "completed", "conclusion": result, "run_attempt": 1,
            "html_url": f"https://github.com/example/repo/actions/runs/{ident}",
            "run_started_at": "2026-10-23T09:55:00Z", "updated_at": "2026-10-23T10:20:00Z"}


def full_jobs():
    return [job("CI Gate"), job("Select suites"),
            job("Runtime suite / runtime-v2-core"),
            job("Webots suite / webots-smoke"),
            *[job(name) for name in audit.SHARDS]]


class MetricsTests(TestCase):
    def test_strict_complete_candidate(self):
        r = audit.summarize_run(run(), full_jobs())
        self.assertTrue(r["full_success"])
        self.assertTrue(r["seven_shards_proven"])
        self.assertEqual(r["runner_minutes_estimate"], 55)
        self.assertEqual(r["wall_minutes"], 25)
        self.assertEqual(r["gate_elapsed_minutes"], 10)
        self.assertTrue(r["timing_complete"])

    def test_false_green_selector_skips_runtime(self):
        jobs = [job("CI Gate"), job("Select suites"), job("Webots suite / webots-smoke"),
                job("Runtime suite", conclusion="skipped")]
        r = audit.summarize_run(run(), jobs)
        self.assertFalse(r["full_success"])
        self.assertFalse(r["seven_shards_proven"])

    def test_draft_gate_cannot_count_as_true_gate(self):
        jobs = [job("CI Gate (Draft)")] + full_jobs()[1:]
        self.assertFalse(audit.summarize_run(run(), jobs)["full_success"])

    def test_partial_proof_or_failed_shard_not_comparable(self):
        for jobs in [full_jobs()[:-1], [job("CI Gate")] + [job(j["name"], conclusion="failure")
                  if j["name"] == audit.SHARDS[3] else j for j in full_jobs()[1:]]]:
            r = audit.summarize_run(run(), jobs)
            self.assertFalse(r["seven_shards_proven"])
            self.assertFalse(r["full_success"])

    def test_failed_gate_not_comparable_with_successful_jobs(self):
        jobs = full_jobs()
        jobs[0] = job("CI Gate", conclusion="failure")
        self.assertFalse(audit.summarize_run(run(result="failure"), jobs)["full_success"])

    def test_old_unsharded_green_not_pooled(self):
        old = audit.summarize_run(run(), [job("CI Gate"), job("Runtime suite / runtime-v2-core"),
                                              job("Webots suite / webots-smoke")])
        self.assertTrue(old["full_success"])
        self.assertFalse(old["seven_shards_proven"])
        new = audit.summarize_run(run(ident=43), full_jobs())
        result, text = audit.build_report("example/repo", [old, new], {}, days=21,
                                          now=datetime(2026, 10, 23, tzinfo=timezone.utc))
        self.assertEqual(result["full_successful_sharded_runs"], 1)
        self.assertIn("Full evidence", text)

    def test_comparison_cohort_requires_same_event_and_exact_jobs(self):
        # Every run has the seven shards and a true successful CI Gate, but
        # comparing 11 selected jobs with 12 conflates coverage and speed.
        base = audit.summarize_run(run(ident=51), full_jobs())
        extra = audit.summarize_run(run(ident=52), full_jobs() +
                                    [job("Webots suite / additional-native-case")])
        identical = audit.summarize_run(run(ident=53), full_jobs())
        scheduled = audit.summarize_run(dict(run(ident=54), event="schedule"), full_jobs())
        self.assertTrue(all(r["full_success"] and r["seven_shards_proven"]
                            for r in (base, extra, identical, scheduled)))
        data, text = audit.build_report(
            "example/repo", [base, extra, identical, scheduled], {},
            days=21, now=datetime(2026, 10, 23, tzinfo=timezone.utc))
        self.assertEqual(data["eligible_before_cohort_filter"], 4)
        self.assertEqual(data["full_successful_sharded_runs"], 2)
        self.assertEqual(data["cohort_reference_run_id"], 51)
        self.assertEqual(data["cohort_event"], "pull_request")
        self.assertEqual(data["cohort_job_count"], len(full_jobs()))
        self.assertEqual(data["runner_median_minutes_estimate"], 55)
        self.assertEqual([r["cohort_comparable"] for r in data["runs"]],
                         [True, False, True, False])
        self.assertIn("same-workload sharded runs: 2 (of 4 eligible", text)

    def test_cancelled_not_success_and_no_blind_retry_proposal(self):
        candidate = audit.summarize_run(run(result="cancelled"), full_jobs())
        self.assertFalse(candidate["full_success"])
        self.assertNotIn("rerun", str(audit.discover([candidate], {})).lower())

    def test_historical_only_proposal_no_deletion(self):
        variants = []
        for idx in range(3):
            jobs = full_jobs() + [job("Webots suite / encoders-historical")]
            variants.append(audit.summarize_run(run(ident=idx), jobs))
        p = audit.discover(variants, {"ci-webots.yml": {"explicit_docker_pull": 20}})
        self.assertTrue(any(x["kind"] == "historical_audit" for x in p))
        self.assertFalse(any(x["kind"] == "repeated_setup" for x in p))
        self.assertIn("no automatic deletion", str(p).lower())

    def test_static_inventory_never_creates_an_optimization_candidate(self):
        inventory = {"ci-webots.yml": {"explicit_docker_pull": 100}}
        self.assertEqual(audit.discover([], inventory), [])
        data, report = audit.build_report(
            "example/repo", [], inventory, days=21,
            now=datetime(2026, 10, 23, tzinfo=timezone.utc))
        self.assertEqual(data["candidates"], [])
        self.assertEqual(data["counts"], inventory)
        self.assertEqual(data["qualification"]["verdict"], "INSUFFICIENT_EVIDENCE")
        self.assertIn("CI setup inventory", report)
        self.assertNotIn("repeated_setup", report)

    def test_measured_named_setup_is_independently_visible(self):
        jobs = full_jobs()
        jobs[3]["steps"] = [
            {"name": "Pull official Webots R2025a image", "conclusion": "success",
             "started_at": "2026-10-23T10:00:00Z", "completed_at": "2026-10-23T10:00:30Z"},
            {"name": "Prepare pinned Blockly 13.2.1 browser assets", "conclusion": "success",
             "started_at": "2026-10-23T10:00:30Z", "completed_at": "2026-10-23T10:00:36Z"},
            {"name": "Pull official Webots R2025a image", "conclusion": "skipped"},
            {"name": "Run tests", "conclusion": "success",
             "started_at": "2026-10-23T10:00:36Z", "completed_at": "2026-10-23T10:05:00Z"},
        ]
        records = [audit.summarize_run(run(ident=100 + n), jobs) for n in range(3)]
        pull = records[0]["setup"]["webots_pull"]
        self.assertEqual(pull, {"steps": 1, "missing_timing": 0, "minutes": 0.5})
        self.assertEqual(records[0]["setup"]["blockly_assets"]["minutes"], 0.1)
        data, report = audit.build_report(
            "example/repo", records, {}, days=21,
            now=datetime(2026, 10, 23, tzinfo=timezone.utc))
        self.assertEqual(data["observed_setup_median_runner_minutes"],
                         {"webots_pull": 0.5, "blockly_assets": 0.1})
        self.assertIn("Pull steps", report)
        self.assertIn("not proof that caching", report)

    def test_missing_step_timing_fails_closed_instead_of_zero(self):
        jobs = full_jobs()
        jobs[3]["steps"] = [
            {"name": "Pull official Webots R2025a image", "conclusion": "success",
             "started_at": None, "completed_at": "2026-10-23T10:00:30Z"},
        ]
        records = [audit.summarize_run(run(ident=200 + n), jobs) for n in range(3)]
        item = records[0]["setup"]["webots_pull"]
        self.assertEqual(item["steps"], 1)
        self.assertEqual(item["missing_timing"], 1)
        self.assertIsNone(item["minutes"])
        data, _ = audit.build_report(
            "example/repo", records, {}, days=21,
            now=datetime(2026, 10, 23, tzinfo=timezone.utc))
        self.assertIsNone(data["observed_setup_median_runner_minutes"]["webots_pull"])
        self.assertIsNone(data["observed_setup_median_runner_minutes"]["blockly_assets"])

    def test_missing_time_never_yields_negative_or_forged_duration(self):
        self.assertIsNone(audit.minutes(None, "2026-10-23T10:01:00Z"))
        self.assertIsNone(audit.minutes("2026-10-23T10:05:00Z", "2026-10-23T10:01:00Z"))
        self.assertIsNone(audit.minutes("bad-timestamp", "2026-10-23T10:01:00Z"))

    def test_pagination_fails_closed(self):
        with patch.object(audit, "get_json", side_effect=[{"total_count": 101, "jobs": [{"name": "x"}]},
                                                         {"total_count": 101, "jobs": []}]):
            with self.assertRaisesRegex(ValueError, "Incomplete job pagination"):
                audit.fetch_jobs("https://api.github.com", "example/repo", 7, "fake")

    def test_bounded_run_query_and_exclude_non_decision_event(self):
        payload = {"workflow_runs": [dict(run(ident=1), event="push"), run(ident=2)]}
        with patch.object(audit, "get_json", return_value=payload) as request:
            got = audit.fetch_runs("https://api.github.com", "example/repo", "fake",
                                   days=7, limit=10, now=datetime(2026, 10, 23, tzinfo=timezone.utc))
            self.assertEqual([r["id"] for r in got], [2])
            self.assertIn("/actions/workflows/ci.yml/runs?", request.call_args.args[0])

    def test_no_success_discloses_insufficient_proof(self):
        data, text = audit.build_report("example/repo", [], {}, days=21,
                                        now=datetime(2026, 10, 23, tzinfo=timezone.utc))
        self.assertIsNone(data["wall_median_minutes"])
        self.assertIn("Not enough fully successful", text)
        self.assertEqual(data["qualification"]["verdict"], "INSUFFICIENT_EVIDENCE")


    def test_gate_finish_is_distinct_from_updated_at(self):
        r = run()
        r["updated_at"] = "2026-10-23T11:00:00Z"
        jobs = full_jobs()
        jobs[0]["completed_at"] = "2026-10-23T10:07:00Z"
        record = audit.summarize_run(r, jobs)
        self.assertEqual(record["gate_elapsed_minutes"], 12)
        self.assertEqual(record["wall_minutes"], 65)
        data, text = audit.build_report("example/repo",
            [record, audit.summarize_run(run(ident=43), full_jobs())], {},
            days=21, now=datetime(2026, 10, 23, tzinfo=timezone.utc))
        self.assertEqual(data["gate_median_minutes"], 11)
        self.assertIn("Legacy run-start to updated_at span", text)

    def test_long_job_and_static_pull_not_promoted(self):
        jobs = full_jobs()
        jobs[2]["completed_at"] = "2026-10-23T10:14:00Z"
        records = [audit.summarize_run(run(ident=n), jobs) for n in (101, 102, 103)]
        data, _ = audit.build_report("example/repo", records,
            {"ci-webots.yml": {"explicit_docker_pull": 12}},
            days=21, now=datetime(2026, 10, 23, tzinfo=timezone.utc))
        self.assertTrue(any(p["kind"] == "long_job_observation" for p in data["candidates"]))
        self.assertFalse(any(p["kind"] == "repeated_setup" for p in data["candidates"]))
        self.assertFalse(any(p["kind"] == "critical_path" for p in data["candidates"]))
        self.assertEqual(data["qualification"]["verdict"], "NO_ACTION")
        self.assertIsNone(data["qualification"]["candidate"])

    def test_one_or_incomparable_cohort_is_insufficient(self):
        first = audit.summarize_run(run(ident=101), full_jobs())
        other = audit.summarize_run(run(ident=102), full_jobs() +
                                    [job("Webots suite / different-job")])
        data, _ = audit.build_report("example/repo", [first, other], {},
            days=21, now=datetime(2026, 10, 23, tzinfo=timezone.utc))
        self.assertEqual(data["qualification"]["verdict"], "INSUFFICIENT_EVIDENCE")
        self.assertEqual(data["qualification"]["evidence"]["run_ids"], [101])

    def test_incoherent_timing_excludes_measurement(self):
        jobs = full_jobs()
        jobs[0]["completed_at"] = "2026-10-23T09:00:00Z"
        bad_gate = audit.summarize_run(run(ident=101), jobs)
        self.assertIsNone(bad_gate["gate_elapsed_minutes"])
        jobs = full_jobs()
        jobs[2]["completed_at"] = "2026-10-23T09:00:00Z"
        bad_job = audit.summarize_run(run(ident=102), jobs)
        self.assertIsNone(bad_job["runner_minutes_estimate"])
        data, _ = audit.build_report("example/repo", [bad_gate, bad_job], {},
            days=21, now=datetime(2026, 10, 23, tzinfo=timezone.utc))
        self.assertIsNone(data["gate_median_minutes"])
        self.assertEqual(data["qualification"]["verdict"], "INSUFFICIENT_EVIDENCE")

    def test_repeated_failure_only_proposes_investigation(self):
        successes = [audit.summarize_run(run(ident=n), full_jobs()) for n in (101, 102)]
        jobs = full_jobs()
        jobs[1] = job("Select suites", conclusion="failure")
        failures = [audit.summarize_run(run(ident=n, result="failure"), jobs)
                    for n in (103, 104)]
        data, text = audit.build_report("example/repo", successes + failures, {},
            days=21, now=datetime(2026, 10, 23, tzinfo=timezone.utc))
        self.assertEqual(data["qualification"]["verdict"], "EXPERIMENT_CANDIDATE")
        self.assertEqual(data["qualification"]["candidate"]["job"], "Select suites")
        self.assertIn("no speedup or cause established", text)


    def test_duplicate_failed_jobs_and_duplicate_run_do_not_imply_recurrence(self):
        successes = [audit.summarize_run(run(ident=n), full_jobs()) for n in (101, 102)]
        jobs = full_jobs()
        jobs[1] = job("Select suites", conclusion="failure")
        jobs.append(job("Select suites", conclusion="failure"))
        failed = audit.summarize_run(run(ident=103, result="failure"), jobs)
        data, report = audit.build_report(
            "example/repo", successes + [failed, failed], {},
            days=21, now=datetime(2026, 10, 23, tzinfo=timezone.utc))
        signal = [p for p in data["candidates"] if p["kind"] == "reliability"]
        self.assertEqual(signal, [])
        # The independent historical-audit observation may still appear;
        # only a one-run *reliability* investigation is forbidden.
        self.assertTrue(any(p["kind"] == "historical_audit" for p in data["candidates"]))
        self.assertEqual(data["qualification"]["verdict"], "NO_ACTION")
        self.assertIsNone(data["qualification"]["candidate"])
        self.assertNotIn("**reliability**", report)
        self.assertIn("Evidence verdict: **NO_ACTION**", report)

    def test_two_distinct_failed_runs_are_counted_once_each(self):
        successes = [audit.summarize_run(run(ident=n), full_jobs()) for n in (101, 102)]
        jobs = full_jobs()
        jobs[1] = job("Select suites", conclusion="failure")
        first = audit.summarize_run(
            run(ident=103, result="failure"),
            jobs + [job("Select suites", conclusion="failure")])
        second = audit.summarize_run(run(ident=104, result="failure"), jobs)
        data, report = audit.build_report(
            "example/repo", successes + [first, second], {},
            days=21, now=datetime(2026, 10, 23, tzinfo=timezone.utc))
        signal = [p for p in data["candidates"] if p["kind"] == "reliability"]
        self.assertEqual(len(signal), 1)
        self.assertEqual(signal[0]["failed_runs"], 2)
        self.assertEqual(data["qualification"]["verdict"], "EXPERIMENT_CANDIDATE")
        self.assertEqual(data["qualification"]["candidate"]["failed_runs"], 2)
        self.assertIn("Evidence verdict: **EXPERIMENT_CANDIDATE**", report)


if __name__ == "__main__":
    main()
