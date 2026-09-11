#!/usr/bin/env python3
"""Materialize and race-safely publish raw physical-test evidence.

The tool deliberately does not record a human PASS/FAIL/NOT_NEEDED verdict.
It preserves raw bytes, binds them to an exact request and tested commit, and can
publish a new Git branch without overwriting an existing publication.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
from typing import Iterable

SCHEMA_VERSION = 1
TOOL_PATH = "tools/evidence/publish_test_evidence.py"
PROFILE_ROOT = Path("tools/evidence/profiles")
ATTRIBUTES = (
    "raw/** -text "
    "whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol\n"
)
SHA_RE = re.compile(r"[0-9a-f]{40}")
SLUG_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
BRANCH_RE = re.compile(r"evidence/[A-Za-z0-9][A-Za-z0-9._/-]{0,180}")
PROFILE_KEYS = {
    "schema",
    "profile",
    "required_globs",
    "allowed_globs",
    "max_files",
    "max_total_bytes",
}


class EvidenceError(RuntimeError):
    """Fail-closed evidence preparation or publication error."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_git(
    repo_root: Path,
    *args: str,
    check: bool = True,
    text: bool = True,
) -> subprocess.CompletedProcess:
    process = subprocess.run(
        ["git", "-C", os.fspath(repo_root), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=text,
    )
    if check and process.returncode:
        stderr = process.stderr if text else process.stderr.decode("utf-8", "replace")
        raise EvidenceError(
            f"git {' '.join(args)} failed ({process.returncode}): {stderr.strip()}"
        )
    return process


def require_git_commit(repo_root: Path, sha: str) -> None:
    if not SHA_RE.fullmatch(sha):
        raise EvidenceError("target SHA must be an exact lowercase 40-character SHA")
    result = run_git(repo_root, "cat-file", "-e", f"{sha}^{{commit}}", check=False)
    if result.returncode:
        raise EvidenceError(f"target SHA is not an available Git commit: {sha}")


def profile_path(repo_root: Path, profile_id: str) -> Path:
    if not SLUG_RE.fullmatch(profile_id):
        raise EvidenceError("invalid evidence profile identifier")
    return repo_root / PROFILE_ROOT / f"{profile_id}.json"


def load_profile(repo_root: Path, profile_id: str) -> tuple[dict[str, object], str, bytes]:
    path = profile_path(repo_root, profile_id)
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise EvidenceError(f"evidence profile is unavailable: {path}") from exc
    try:
        profile = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvidenceError(f"evidence profile is not valid UTF-8 JSON: {path}") from exc
    if not isinstance(profile, dict):
        raise EvidenceError("evidence profile must be a JSON object")
    unknown = set(profile) - PROFILE_KEYS
    missing = PROFILE_KEYS - set(profile)
    if unknown or missing:
        raise EvidenceError(
            f"evidence profile fields mismatch; missing={sorted(missing)} "
            f"unknown={sorted(unknown)}"
        )
    if profile["schema"] != SCHEMA_VERSION or profile["profile"] != profile_id:
        raise EvidenceError("evidence profile schema/id mismatch")
    required = profile["required_globs"]
    allowed = profile["allowed_globs"]
    if (
        not isinstance(required, list)
        or not required
        or not all(isinstance(item, str) and item for item in required)
        or not isinstance(allowed, list)
        or not allowed
        or not all(isinstance(item, str) and item for item in allowed)
    ):
        raise EvidenceError("profile glob lists must be non-empty string arrays")
    for key in ("max_files", "max_total_bytes"):
        value = profile[key]
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise EvidenceError(f"profile {key} must be a positive integer")
    return profile, sha256_bytes(raw), raw


def _matches(relpath: str, pattern: str) -> bool:
    # PurePath.match("**/*.csv") does not consistently express "root or nested"
    # across Python versions, so "**/" is explicitly treated as zero-or-more dirs.
    path = PurePosixPath(relpath)
    if path.match(pattern) or fnmatch.fnmatchcase(relpath, pattern):
        return True
    return pattern.startswith("**/") and (
        path.match(pattern[3:]) or fnmatch.fnmatchcase(relpath, pattern[3:])
    )


def discover_source_files(source: Path, profile: dict[str, object]) -> list[Path]:
    if not source.is_dir():
        raise EvidenceError(f"source directory does not exist: {source}")
    paths: list[Path] = []
    for path in source.rglob("*"):
        if path.is_symlink():
            raise EvidenceError(f"source symlink is forbidden: {path}")
        if path.is_file():
            paths.append(path)
    paths.sort(key=lambda item: item.relative_to(source).as_posix())

    if len(paths) > int(profile["max_files"]):
        raise EvidenceError("source exceeds profile max_files")
    total = sum(path.stat().st_size for path in paths)
    if total > int(profile["max_total_bytes"]):
        raise EvidenceError("source exceeds profile max_total_bytes")

    allowed = list(profile["allowed_globs"])
    required = list(profile["required_globs"])
    relatives = [path.relative_to(source).as_posix() for path in paths]

    unexpected = [
        rel for rel in relatives if not any(_matches(rel, pattern) for pattern in allowed)
    ]
    if unexpected:
        raise EvidenceError(f"unexpected evidence files: {unexpected}")

    missing = [
        pattern
        for pattern in required
        if not any(_matches(rel, pattern) for rel in relatives)
    ]
    if missing:
        raise EvidenceError(f"required evidence patterns have no match: {missing}")
    return paths


def resolve_destination(repo_root: Path, destination: str) -> Path:
    destination_path = Path(destination)
    if destination_path.is_absolute() or not destination_path.parts:
        raise EvidenceError("destination must be a non-empty repository-relative path")
    if any(part in {"", ".", "..", ".git"} for part in destination_path.parts):
        raise EvidenceError("destination contains a forbidden path component")
    repo_real = repo_root.resolve()
    dest_real = (repo_root / destination_path).resolve()
    try:
        dest_real.relative_to(repo_real)
    except ValueError as exc:
        raise EvidenceError("destination escapes repository root") from exc
    return dest_real


def manifest_text(records: Iterable[dict[str, object]]) -> str:
    return "".join(f"{item['sha256']}  {item['path']}\n" for item in records)


def metadata_bytes(metadata: dict[str, object]) -> bytes:
    return (json.dumps(metadata, indent=2, sort_keys=True) + "\n").encode("utf-8")


def materialize(
    *,
    repo_root: Path,
    source: Path,
    destination: str,
    profile_id: str,
    target_sha: str,
    checkpoint_ref: str,
    purpose: str,
    request: str,
    provenance: str,
) -> Path:
    repo_root = repo_root.resolve()
    source = source.resolve()
    require_git_commit(repo_root, target_sha)
    if not SLUG_RE.fullmatch(checkpoint_ref):
        raise EvidenceError("checkpoint ref must be a stable slug")
    if purpose not in {"checkpoint", "release"}:
        raise EvidenceError("purpose must be checkpoint or release")
    if not request.strip() or "\n" in request or "\r" in request or len(request) > 2048:
        raise EvidenceError("request must be one non-empty durable reference line")
    if (
        not provenance.strip()
        or "\n" in provenance
        or "\r" in provenance
        or len(provenance) > 4096
    ):
        raise EvidenceError("provenance must be one non-empty capture-description line")

    profile, profile_sha, profile_raw = load_profile(repo_root, profile_id)
    source_files = discover_source_files(source, profile)
    destination_path = resolve_destination(repo_root, destination)
    if destination_path.exists():
        raise EvidenceError(f"destination already exists; refusing overwrite: {destination}")

    raw_root = destination_path / "raw"
    records: list[dict[str, object]] = []
    try:
        raw_root.mkdir(parents=True, exist_ok=False)
        for source_path in source_files:
            rel = source_path.relative_to(source)
            target = raw_root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_path, target)
            source_size = source_path.stat().st_size
            copied_size = target.stat().st_size
            source_sha = sha256_file(source_path)
            copied_sha = sha256_file(target)
            if source_size != copied_size or source_sha != copied_sha:
                raise EvidenceError(f"byte-for-byte copy verification failed: {rel.as_posix()}")
            records.append(
                {
                    "path": f"raw/{rel.as_posix()}",
                    "sha256": copied_sha,
                    "size": copied_size,
                }
            )

        (destination_path / "PROFILE.json").write_bytes(profile_raw)
        metadata = {
            "binding": {
                "checkpoint_ref": checkpoint_ref,
                "purpose": purpose,
                "request": request,
                "target_sha": target_sha,
            },
            "capture": {"provenance": provenance},
            "human_verdict": None,
            "kind": "webeeblocks-raw-test-evidence",
            "producer": {
                "format_version": SCHEMA_VERSION,
                "tool": TOOL_PATH,
            },
            "profile": {
                "id": profile_id,
                "registry_path": (PROFILE_ROOT / f"{profile_id}.json").as_posix(),
                "sha256": profile_sha,
            },
            "raw_files": records,
            "schema": SCHEMA_VERSION,
        }
        (destination_path / "EVIDENCE.json").write_bytes(metadata_bytes(metadata))
        (destination_path / "MANIFEST.sha256").write_text(
            manifest_text(records), encoding="utf-8", newline="\n"
        )
        (destination_path / ".gitattributes").write_text(
            ATTRIBUTES, encoding="utf-8", newline="\n"
        )
        verify(repo_root=repo_root, evidence_dir=destination_path)
    except BaseException:
        # A failed materialization is never durable evidence. Removing only the
        # newly-created destination is safe; the source is intentionally untouched.
        if destination_path.exists():
            shutil.rmtree(destination_path)
        raise
    return destination_path


def verify(*, repo_root: Path, evidence_dir: Path) -> dict[str, object]:
    repo_root = repo_root.resolve()
    evidence_dir = evidence_dir.resolve()
    if not evidence_dir.is_dir():
        raise EvidenceError(f"evidence directory does not exist: {evidence_dir}")
    try:
        evidence_dir.relative_to(repo_root)
    except ValueError as exc:
        raise EvidenceError("evidence directory must be inside repository root") from exc

    metadata_path = evidence_dir / "EVIDENCE.json"
    manifest_path = evidence_dir / "MANIFEST.sha256"
    attributes_path = evidence_dir / ".gitattributes"
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvidenceError("EVIDENCE.json is missing or invalid") from exc
    if not isinstance(metadata, dict):
        raise EvidenceError("EVIDENCE.json must be an object")
    if set(metadata) != {
        "binding",
        "capture",
        "human_verdict",
        "kind",
        "producer",
        "profile",
        "raw_files",
        "schema",
    }:
        raise EvidenceError("EVIDENCE.json top-level contract mismatch")
    if (
        metadata["schema"] != SCHEMA_VERSION
        or metadata["kind"] != "webeeblocks-raw-test-evidence"
        or metadata["human_verdict"] is not None
        or metadata["producer"]
        != {"format_version": SCHEMA_VERSION, "tool": TOOL_PATH}
    ):
        raise EvidenceError("EVIDENCE.json semantic contract mismatch")
    capture = metadata["capture"]
    if (
        not isinstance(capture, dict)
        or set(capture) != {"provenance"}
        or not isinstance(capture["provenance"], str)
        or not capture["provenance"].strip()
        or "\n" in capture["provenance"]
        or "\r" in capture["provenance"]
        or len(capture["provenance"]) > 4096
    ):
        raise EvidenceError("capture provenance contract mismatch")

    binding = metadata["binding"]
    if not isinstance(binding, dict) or set(binding) != {
        "checkpoint_ref",
        "purpose",
        "request",
        "target_sha",
    }:
        raise EvidenceError("evidence binding contract mismatch")
    checkpoint_ref = binding["checkpoint_ref"]
    target_sha = binding["target_sha"]
    purpose = binding["purpose"]
    request = binding["request"]
    if not isinstance(checkpoint_ref, str) or not SLUG_RE.fullmatch(checkpoint_ref):
        raise EvidenceError("invalid durable checkpoint binding")
    if purpose not in {"checkpoint", "release"}:
        raise EvidenceError("invalid durable purpose binding")
    if (
        not isinstance(request, str)
        or not request.strip()
        or "\n" in request
        or "\r" in request
        or len(request) > 2048
    ):
        raise EvidenceError("invalid durable request binding")
    if not isinstance(target_sha, str):
        raise EvidenceError("invalid durable target SHA binding")
    require_git_commit(repo_root, target_sha)

    profile_meta = metadata["profile"]
    if (
        not isinstance(profile_meta, dict)
        or set(profile_meta) != {"id", "registry_path", "sha256"}
    ):
        raise EvidenceError("profile binding contract mismatch")
    profile_id = profile_meta["id"]
    if not isinstance(profile_id, str) or not SLUG_RE.fullmatch(profile_id):
        raise EvidenceError("invalid profile identifier binding")
    expected_registry = (PROFILE_ROOT / f"{profile_id}.json").as_posix()
    if profile_meta["registry_path"] != expected_registry:
        raise EvidenceError("profile registry path binding mismatch")
    try:
        bundled_profile_raw = (evidence_dir / "PROFILE.json").read_bytes()
        bundled_profile = json.loads(bundled_profile_raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvidenceError("bundled PROFILE.json is missing or invalid") from exc
    if sha256_bytes(bundled_profile_raw) != profile_meta["sha256"]:
        raise EvidenceError("bundled PROFILE.json digest mismatch")
    if not isinstance(bundled_profile, dict):
        raise EvidenceError("bundled PROFILE.json must be an object")
    unknown = set(bundled_profile) - PROFILE_KEYS
    missing = PROFILE_KEYS - set(bundled_profile)
    if unknown or missing:
        raise EvidenceError("bundled PROFILE.json fields mismatch")
    if (
        bundled_profile["schema"] != SCHEMA_VERSION
        or bundled_profile["profile"] != profile_id
    ):
        raise EvidenceError("bundled PROFILE.json schema/id mismatch")
    required = bundled_profile["required_globs"]
    allowed = bundled_profile["allowed_globs"]
    if (
        not isinstance(required, list)
        or not required
        or not all(isinstance(item, str) and item for item in required)
        or not isinstance(allowed, list)
        or not allowed
        or not all(isinstance(item, str) and item for item in allowed)
        or not isinstance(bundled_profile["max_files"], int)
        or isinstance(bundled_profile["max_files"], bool)
        or bundled_profile["max_files"] <= 0
        or not isinstance(bundled_profile["max_total_bytes"], int)
        or isinstance(bundled_profile["max_total_bytes"], bool)
        or bundled_profile["max_total_bytes"] <= 0
    ):
        raise EvidenceError("bundled PROFILE.json contract mismatch")
    profile = bundled_profile

    try:
        attributes = attributes_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise EvidenceError("evidence .gitattributes is missing") from exc
    if attributes != ATTRIBUTES:
        raise EvidenceError("evidence .gitattributes does not preserve raw bytes")

    records = metadata["raw_files"]
    if not isinstance(records, list):
        raise EvidenceError("raw_files must be an array")
    expected_paths: list[str] = []
    for record in records:
        if (
            not isinstance(record, dict)
            or set(record) != {"path", "sha256", "size"}
            or not isinstance(record["path"], str)
            or not record["path"].startswith("raw/")
            or not isinstance(record["sha256"], str)
            or not re.fullmatch(r"[0-9a-f]{64}", record["sha256"])
            or not isinstance(record["size"], int)
            or isinstance(record["size"], bool)
            or record["size"] < 0
        ):
            raise EvidenceError("invalid raw_files record")
        rel = PurePosixPath(record["path"])
        if any(part in {"", ".", ".."} for part in rel.parts):
            raise EvidenceError("invalid raw evidence path")
        file_path = evidence_dir.joinpath(*rel.parts)
        if file_path.is_symlink() or not file_path.is_file():
            raise EvidenceError(f"raw evidence file missing or non-regular: {record['path']}")
        if file_path.stat().st_size != record["size"]:
            raise EvidenceError(f"raw evidence size mismatch: {record['path']}")
        if sha256_file(file_path) != record["sha256"]:
            raise EvidenceError(f"raw evidence digest mismatch: {record['path']}")
        expected_paths.append(record["path"])

    raw_root = evidence_dir / "raw"
    actual_paths: list[str] = []
    if not raw_root.is_dir():
        raise EvidenceError("raw evidence directory is missing")
    for path in raw_root.rglob("*"):
        if path.is_symlink():
            raise EvidenceError(f"raw evidence symlink is forbidden: {path}")
        if path.is_file():
            actual_paths.append(f"raw/{path.relative_to(raw_root).as_posix()}")
    actual_paths.sort()
    if expected_paths != sorted(expected_paths) or actual_paths != expected_paths:
        raise EvidenceError("raw evidence file set does not match EVIDENCE.json")

    relatives = [item[4:] for item in actual_paths]
    allowed = list(profile["allowed_globs"])
    required = list(profile["required_globs"])
    if any(not any(_matches(rel, pattern) for pattern in allowed) for rel in relatives):
        raise EvidenceError("raw evidence violates current profile allowed_globs")
    if any(not any(_matches(rel, pattern) for rel in relatives) for pattern in required):
        raise EvidenceError("raw evidence violates current profile required_globs")

    try:
        manifest = manifest_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise EvidenceError("MANIFEST.sha256 is missing") from exc
    if manifest != manifest_text(records):
        raise EvidenceError("MANIFEST.sha256 does not exactly match metadata")

    allowed_top = {"EVIDENCE.json", "MANIFEST.sha256", "PROFILE.json", ".gitattributes", "raw"}
    actual_top = {path.name for path in evidence_dir.iterdir()}
    if actual_top != allowed_top:
        raise EvidenceError("unexpected top-level evidence content")
    return metadata


def ensure_clean_base(repo_root: Path, base_sha: str) -> None:
    require_git_commit(repo_root, base_sha)
    head = run_git(repo_root, "rev-parse", "HEAD").stdout.strip()
    if head != base_sha:
        raise EvidenceError(f"working tree HEAD {head} is not requested base {base_sha}")
    status = run_git(
        repo_root, "status", "--porcelain=v1", "--untracked-files=all"
    ).stdout
    if status:
        raise EvidenceError("working tree must be clean before publication")


def remote_branch_sha(repo_root: Path, remote: str, branch: str) -> str | None:
    result = run_git(
        repo_root,
        "ls-remote",
        "--heads",
        remote,
        f"refs/heads/{branch}",
        check=False,
    )
    if result.returncode:
        raise EvidenceError(
            f"cannot reconstruct remote branch state for {remote}/{branch}: "
            f"{result.stderr.strip()}"
        )
    line = result.stdout.strip()
    if not line:
        return None
    fields = line.split()
    if len(fields) != 2 or fields[1] != f"refs/heads/{branch}" or not SHA_RE.fullmatch(fields[0]):
        raise EvidenceError("unexpected git ls-remote response")
    return fields[0]


def publish(
    *,
    repo_root: Path,
    source: Path,
    destination: str,
    profile_id: str,
    target_sha: str,
    checkpoint_ref: str,
    purpose: str,
    request: str,
    provenance: str,
    base_sha: str,
    base_ref: str,
    branch: str,
    remote: str,
) -> dict[str, str]:
    repo_root = repo_root.resolve()
    if not SHA_RE.fullmatch(base_sha):
        raise EvidenceError("base SHA must be an exact lowercase 40-character SHA")
    if not BRANCH_RE.fullmatch(branch) or ".." in branch or "//" in branch:
        raise EvidenceError("publication branch must be a safe evidence/... branch")
    if not remote or any(char.isspace() for char in remote):
        raise EvidenceError("invalid Git remote name")
    if not SLUG_RE.fullmatch(base_ref):
        raise EvidenceError("base ref must be a simple branch name")

    ensure_clean_base(repo_root, base_sha)
    if remote_branch_sha(repo_root, remote, base_ref) != base_sha:
        raise EvidenceError("remote base moved or does not match the exact requested base SHA")
    if remote_branch_sha(repo_root, remote, branch) is not None:
        raise EvidenceError("remote publication branch already exists; refusing overwrite")

    # Create the local branch before touching the evidence destination. This leaves
    # no untracked partial evidence if branch creation itself fails.
    run_git(repo_root, "switch", "-c", branch, base_sha)
    evidence_path: Path | None = None
    try:
        evidence_path = materialize(
            repo_root=repo_root,
            source=source,
            destination=destination,
            profile_id=profile_id,
            target_sha=target_sha,
            checkpoint_ref=checkpoint_ref,
            purpose=purpose,
            request=request,
            provenance=provenance,
        )
        rel_destination = evidence_path.relative_to(repo_root).as_posix()
        run_git(repo_root, "add", "--", rel_destination)

        staged_names = [
            line
            for line in run_git(
                repo_root, "diff", "--cached", "--name-only", "--diff-filter=ACMR"
            ).stdout.splitlines()
            if line
        ]
        prefix = rel_destination.rstrip("/") + "/"
        if not staged_names or any(
            name != rel_destination and not name.startswith(prefix)
            for name in staged_names
        ):
            raise EvidenceError("staged publication contains changes outside evidence destination")

        # The evidence-local .gitattributes makes CRLF raw files binary for Git
        # whitespace purposes without changing their bytes.
        run_git(repo_root, "diff", "--cached", "--check")
        verify(repo_root=repo_root, evidence_dir=evidence_path)

        message = f"Publish raw evidence {checkpoint_ref} for {target_sha[:12]}"
        run_git(repo_root, "commit", "-m", message)
        commit_sha = run_git(repo_root, "rev-parse", "HEAD").stdout.strip()
        if not SHA_RE.fullmatch(commit_sha):
            raise EvidenceError("publication commit did not resolve exactly")

        # Reconstruct the remote immediately before the external effect. The lease
        # below is the atomic create-if-absent check; the preceding read is only an
        # early diagnostic and is never relied on as the write authority.
        if remote_branch_sha(repo_root, remote, base_ref) != base_sha:
            raise EvidenceError(
                "remote base moved during publication; local evidence is retained"
            )
        if remote_branch_sha(repo_root, remote, branch) is not None:
            raise EvidenceError("remote publication branch appeared concurrently; refusing overwrite")

        push = run_git(
            repo_root,
            "push",
            "--porcelain",
            f"--force-with-lease=refs/heads/{branch}:",
            remote,
            f"HEAD:refs/heads/{branch}",
            check=False,
        )
        if push.returncode:
            raise EvidenceError(
                "atomic evidence branch creation failed; local evidence is retained: "
                + push.stderr.strip()
            )
        published_sha = remote_branch_sha(repo_root, remote, branch)
        if published_sha != commit_sha:
            raise EvidenceError(
                "remote publication verification is ambiguous; local evidence is retained"
            )
        return {
            "branch": branch,
            "commit_sha": commit_sha,
            "destination": rel_destination,
            "target_sha": target_sha,
        }
    except BaseException:
        # Never delete source or an already-created local evidence branch here.
        # Its durable/remote state may be unknown after a failed push.
        raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        default=".",
        help="repository working tree (default: current directory)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_evidence_args(command: argparse.ArgumentParser) -> None:
        command.add_argument("--source", required=True)
        command.add_argument("--destination", required=True)
        command.add_argument("--profile", required=True)
        command.add_argument("--target-sha", required=True)
        command.add_argument("--checkpoint-ref", required=True)
        command.add_argument("--purpose", choices=("checkpoint", "release"), required=True)
        command.add_argument("--request", required=True)
        command.add_argument("--provenance", required=True)

    materialize_parser = subparsers.add_parser(
        "materialize", help="copy, bind, hash and locally verify one evidence set"
    )
    add_evidence_args(materialize_parser)

    verify_parser = subparsers.add_parser(
        "verify", help="verify one already-materialized evidence set"
    )
    verify_parser.add_argument("--evidence-dir", required=True)

    publish_parser = subparsers.add_parser(
        "publish",
        help="materialize and atomically create a new immutable evidence branch",
    )
    add_evidence_args(publish_parser)
    publish_parser.add_argument("--base-sha", required=True)
    publish_parser.add_argument("--base-ref", default="main")
    publish_parser.add_argument("--branch", required=True)
    publish_parser.add_argument("--remote", default="origin")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = Path(args.repo_root)
    try:
        if args.command == "verify":
            metadata = verify(
                repo_root=repo_root,
                evidence_dir=repo_root / args.evidence_dir,
            )
            print(
                json.dumps(
                    {
                        "verified": True,
                        "target_sha": metadata["binding"]["target_sha"],
                        "profile": metadata["profile"]["id"],
                    },
                    sort_keys=True,
                )
            )
            return 0

        common = {
            "repo_root": repo_root,
            "source": Path(args.source),
            "destination": args.destination,
            "profile_id": args.profile,
            "target_sha": args.target_sha,
            "checkpoint_ref": args.checkpoint_ref,
            "purpose": args.purpose,
            "request": args.request,
            "provenance": args.provenance,
        }
        if args.command == "materialize":
            path = materialize(**common)
            print(
                json.dumps(
                    {
                        "materialized": path.relative_to(repo_root.resolve()).as_posix(),
                        "target_sha": args.target_sha,
                    },
                    sort_keys=True,
                )
            )
            return 0

        result = publish(
            **common,
            base_sha=args.base_sha,
            base_ref=args.base_ref,
            branch=args.branch,
            remote=args.remote,
        )
        print(json.dumps(result, sort_keys=True))
        return 0
    except EvidenceError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
