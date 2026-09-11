#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "tools" / "evidence" / "publish_test_evidence.py"
PROFILE = ROOT / "tools" / "evidence" / "profiles" / "physical-csv-text-v1.json"

spec = importlib.util.spec_from_file_location("publish_test_evidence", MODULE)
assert spec and spec.loader
evidence = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evidence)


def run(*args: str, cwd: Path | None = None, check: bool = True, text: bool = True):
    process = subprocess.run(
        list(args),
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=text,
    )
    if check and process.returncode:
        stderr = process.stderr if text else process.stderr.decode("utf-8", "replace")
        raise AssertionError(f"{' '.join(args)} failed: {stderr}")
    return process


def init_repo(root: Path, remote: Path | None = None) -> str:
    run("git", "init", "-q", "-b", "main", str(root))
    run("git", "config", "user.name", "Evidence Test", cwd=root)
    run("git", "config", "user.email", "evidence@example.invalid", cwd=root)
    profile_target = root / "tools" / "evidence" / "profiles"
    profile_target.mkdir(parents=True)
    shutil.copyfile(PROFILE, profile_target / PROFILE.name)
    (root / "README.md").write_text("fixture\n", encoding="utf-8")
    run("git", "add", ".", cwd=root)
    run("git", "commit", "-q", "-m", "fixture base", cwd=root)
    sha = run("git", "rev-parse", "HEAD", cwd=root).stdout.strip()
    if remote is not None:
        run("git", "init", "-q", "--bare", str(remote))
        run("git", "remote", "add", "origin", str(remote), cwd=root)
        run("git", "push", "-q", "-u", "origin", "main", cwd=root)
    return sha


def fixture_source(root: Path) -> tuple[Path, bytes]:
    source = root / "source"
    source.mkdir(parents=True)
    raw = b"time,value\r\n0,1\r\n1,2\r\n"
    (source / "trace.csv").write_bytes(raw)
    (source / "operator.txt").write_bytes(b"captured without verdict\r\n")
    return source, raw


def expect_error(callable_, contains: str) -> None:
    try:
        callable_()
    except evidence.EvidenceError as exc:
        assert contains in str(exc), (contains, str(exc))
        return
    raise AssertionError(f"expected EvidenceError containing {contains!r}")


def rewrite_bundled_profile_limit(path: Path, key: str, value: int) -> None:
    profile_path = path / "PROFILE.json"
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    profile[key] = value
    profile_raw = (json.dumps(profile, indent=2, sort_keys=True) + "\n").encode("utf-8")
    profile_path.write_bytes(profile_raw)
    metadata_path = path / "EVIDENCE.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["profile"]["sha256"] = evidence.sha256_bytes(profile_raw)
    metadata_path.write_bytes(evidence.metadata_bytes(metadata))


def test_materialize_and_verify_preserve_raw_bytes(tmp: Path) -> None:
    repo = tmp / "repo-materialize"
    repo.mkdir()
    base = init_repo(repo)
    source, raw = fixture_source(tmp / "materialize-source-root")

    destination = "experiments/fixture/evidence/checkpoint-123"
    path = evidence.materialize(
        repo_root=repo,
        source=source,
        destination=destination,
        profile_id="physical-csv-text-v1",
        target_sha=base,
        checkpoint_ref="issue-123",
        purpose="checkpoint",
        request="https://github.com/djibian/webeeblocks/issues/123#issuecomment-1",
        provenance="fixture logger --csv trace.csv",
    )
    assert (path / "raw" / "trace.csv").read_bytes() == raw
    metadata = evidence.verify(repo_root=repo, evidence_dir=path)
    assert metadata["binding"]["target_sha"] == base
    assert metadata["binding"]["checkpoint_ref"] == "issue-123"
    assert metadata["capture"]["provenance"] == "fixture logger --csv trace.csv"
    assert metadata["human_verdict"] is None
    assert (path / "PROFILE.json").read_bytes() == PROFILE.read_bytes()
    record = next(item for item in metadata["raw_files"] if item["path"] == "raw/trace.csv")
    assert record["size"] == len(raw)
    assert record["sha256"] == evidence.sha256_bytes(raw)
    assert (path / "MANIFEST.sha256").read_text(encoding="utf-8").count("\n") == 2

    # Raw CRLF must remain exact after Git stages it under the generated attributes.
    run("git", "add", destination, cwd=repo)
    blob = run(
        "git",
        "show",
        f":{destination}/raw/trace.csv",
        cwd=repo,
        text=False,
    ).stdout
    assert blob == raw


def test_fail_closed_inputs_and_mutation(tmp: Path) -> None:
    repo = tmp / "repo-fail"
    repo.mkdir()
    base = init_repo(repo)

    missing_source = tmp / "missing-source"
    missing_source.mkdir()
    (missing_source / "note.txt").write_bytes(b"no csv\r\n")
    expect_error(
        lambda: evidence.materialize(
            repo_root=repo,
            source=missing_source,
            destination="evidence/missing",
            profile_id="physical-csv-text-v1",
            target_sha=base,
            checkpoint_ref="issue-124",
            purpose="checkpoint",
            request="issue-124",
            provenance="fixture missing-csv capture",
        ),
        "required evidence",
    )
    assert not (repo / "evidence" / "missing").exists()

    unexpected_source = tmp / "unexpected-source"
    unexpected_source.mkdir()
    (unexpected_source / "trace.csv").write_bytes(b"x\r\n")
    (unexpected_source / "payload.bin").write_bytes(b"\x00\x01")
    expect_error(
        lambda: evidence.materialize(
            repo_root=repo,
            source=unexpected_source,
            destination="evidence/unexpected",
            profile_id="physical-csv-text-v1",
            target_sha=base,
            checkpoint_ref="issue-125",
            purpose="checkpoint",
            request="issue-125",
            provenance="fixture unexpected-file capture",
        ),
        "unexpected evidence",
    )
    assert not (repo / "evidence" / "unexpected").exists()

    source, _ = fixture_source(tmp / "mutated-source-root")
    path = evidence.materialize(
        repo_root=repo,
        source=source,
        destination="evidence/mutated",
        profile_id="physical-csv-text-v1",
        target_sha=base,
        checkpoint_ref="issue-126",
        purpose="checkpoint",
        request="issue-126",
        provenance="fixture mutation capture",
    )
    (path / "raw" / "trace.csv").write_bytes(b"tampered\n")
    expect_error(
        lambda: evidence.verify(repo_root=repo, evidence_dir=path),
        "size mismatch",
    )

    manifest_source, _ = fixture_source(tmp / "manifest-source-root")
    manifest_path = evidence.materialize(
        repo_root=repo,
        source=manifest_source,
        destination="evidence/manifest-tamper",
        profile_id="physical-csv-text-v1",
        target_sha=base,
        checkpoint_ref="issue-126b",
        purpose="checkpoint",
        request="issue-126b",
        provenance="fixture manifest-tamper capture",
    )
    (manifest_path / "MANIFEST.sha256").write_text(
        "0" * 64 + "  raw/trace.csv\n", encoding="utf-8"
    )
    expect_error(
        lambda: evidence.verify(repo_root=repo, evidence_dir=manifest_path),
        "MANIFEST.sha256",
    )

    files_source, _ = fixture_source(tmp / "max-files-source-root")
    files_path = evidence.materialize(
        repo_root=repo,
        source=files_source,
        destination="evidence/max-files",
        profile_id="physical-csv-text-v1",
        target_sha=base,
        checkpoint_ref="issue-126c",
        purpose="checkpoint",
        request="issue-126c",
        provenance="fixture max-files verifier capture",
    )
    rewrite_bundled_profile_limit(files_path, "max_files", 1)
    expect_error(
        lambda: evidence.verify(repo_root=repo, evidence_dir=files_path),
        "max_files",
    )

    bytes_source, _ = fixture_source(tmp / "max-bytes-source-root")
    bytes_path = evidence.materialize(
        repo_root=repo,
        source=bytes_source,
        destination="evidence/max-bytes",
        profile_id="physical-csv-text-v1",
        target_sha=base,
        checkpoint_ref="issue-126d",
        purpose="checkpoint",
        request="issue-126d",
        provenance="fixture max-bytes verifier capture",
    )
    bytes_metadata = json.loads((bytes_path / "EVIDENCE.json").read_text(encoding="utf-8"))
    total_bytes = sum(item["size"] for item in bytes_metadata["raw_files"])
    assert total_bytes > 1
    rewrite_bundled_profile_limit(bytes_path, "max_total_bytes", total_bytes - 1)
    expect_error(
        lambda: evidence.verify(repo_root=repo, evidence_dir=bytes_path),
        "max_total_bytes",
    )


def test_publish_creates_new_remote_branch_and_refuses_race(tmp: Path) -> None:
    remote = tmp / "remote.git"
    repo = tmp / "repo-publish"
    repo.mkdir()
    base = init_repo(repo, remote)
    source, raw = fixture_source(tmp / "publish-source-root")

    result = evidence.publish(
        repo_root=repo,
        source=source,
        destination="experiments/fixture/evidence/checkpoint-127",
        profile_id="physical-csv-text-v1",
        target_sha=base,
        checkpoint_ref="issue-127",
        purpose="checkpoint",
        request="https://github.com/djibian/webeeblocks/issues/127",
        provenance="fixture publish capture",
        base_sha=base,
        base_ref="main",
        branch="evidence/issue-127-" + base[:12],
        remote="origin",
    )
    remote_sha = run(
        "git",
        "ls-remote",
        "--heads",
        str(remote),
        "refs/heads/" + result["branch"],
    ).stdout.split()[0]
    assert remote_sha == result["commit_sha"]
    stored = run(
        "git",
        f"--git-dir={remote}",
        "show",
        f"{remote_sha}:experiments/fixture/evidence/checkpoint-127/raw/trace.csv",
        text=False,
    ).stdout
    assert stored == raw

    # A fresh clean clone observes the existing branch before any materialization
    # and refuses to overwrite it.
    racer = tmp / "repo-racer"
    run("git", "clone", "-q", "-b", "main", str(remote), str(racer))
    run("git", "config", "user.name", "Evidence Test", cwd=racer)
    run("git", "config", "user.email", "evidence@example.invalid", cwd=racer)
    racer_base = run("git", "rev-parse", "HEAD", cwd=racer).stdout.strip()
    assert racer_base == base
    race_source, _ = fixture_source(tmp / "race-source-root")
    race_destination = "experiments/fixture/evidence/checkpoint-race"
    expect_error(
        lambda: evidence.publish(
            repo_root=racer,
            source=race_source,
            destination=race_destination,
            profile_id="physical-csv-text-v1",
            target_sha=base,
            checkpoint_ref="issue-127",
            purpose="checkpoint",
            request="https://github.com/djibian/webeeblocks/issues/127",
            provenance="fixture race capture",
            base_sha=base,
            base_ref="main",
            branch=result["branch"],
            remote="origin",
        ),
        "already exists",
    )
    assert not (racer / race_destination).exists()
    assert run("git", "rev-parse", "HEAD", cwd=racer).stdout.strip() == base

    # Reproduce the actual check→push TOCTOU: create the destination ref only
    # after publish() has completed its final absence reconstruction, immediately
    # before the underlying push process starts. The empty expected lease must
    # reject even a would-be fast-forward and preserve the concurrent ref.
    toctou = tmp / "repo-toctou"
    run("git", "clone", "-q", "-b", "main", str(remote), str(toctou))
    run("git", "config", "user.name", "Evidence Test", cwd=toctou)
    run("git", "config", "user.email", "evidence@example.invalid", cwd=toctou)
    toctou_base = run("git", "rev-parse", "HEAD", cwd=toctou).stdout.strip()
    assert toctou_base == base
    toctou_source, _ = fixture_source(tmp / "toctou-source-root")
    toctou_branch = "evidence/issue-128-" + base[:12]
    original_run_git = evidence.run_git
    injected = {"done": False}

    def racing_run_git(repo_root, *args, **kwargs):
        if args and args[0] == "push" and not injected["done"]:
            injected["done"] = True
            run(
                "git",
                f"--git-dir={remote}",
                "update-ref",
                f"refs/heads/{toctou_branch}",
                base,
            )
        return original_run_git(repo_root, *args, **kwargs)

    with patch.object(evidence, "run_git", side_effect=racing_run_git):
        expect_error(
            lambda: evidence.publish(
                repo_root=toctou,
                source=toctou_source,
                destination="experiments/fixture/evidence/checkpoint-toctou",
                profile_id="physical-csv-text-v1",
                target_sha=base,
                checkpoint_ref="issue-128",
                purpose="checkpoint",
                request="https://github.com/djibian/webeeblocks/issues/128",
                provenance="fixture injected check-push race",
                base_sha=base,
                base_ref="main",
                branch=toctou_branch,
                remote="origin",
            ),
            "atomic evidence branch creation failed",
        )
    assert injected["done"]
    preserved = run(
        "git",
        "ls-remote",
        "--heads",
        str(remote),
        f"refs/heads/{toctou_branch}",
    ).stdout.split()[0]
    assert preserved == base


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="webeeblocks-evidence-test-") as temp:
        tmp = Path(temp)
        test_materialize_and_verify_preserve_raw_bytes(tmp)
        test_fail_closed_inputs_and_mutation(tmp)
        test_publish_creates_new_remote_branch_and_refuses_race(tmp)
    print(
        "PASS raw test evidence is byte-preserving, manifest-bound, "
        "fail-closed and race-safe to publish"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
