#!/usr/bin/env python3
"""Regression oracle for the packaged physical-qualification artifact."""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
VERIFIER = ROOT / "tools" / "physical" / "verify_physical_qualification_package.py"
PACKAGER = ROOT / "tools" / "physical" / "package_physical_qualification.py"
RUNNER = ROOT / "tools" / "physical" / "run_packaged_physical_qualification.sh"
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
HUMAN_WORKFLOW = ROOT / ".github" / "workflows" / "human-checkpoint.yml"
WEBOTS_IMAGE_DIGEST = "sha256:f0023e30daf38b172e4e6ad24ed345909bcd9551df34d63d824e121a7cebf099"
WEBOTS_IMAGE = f"cyberbotics/webots@{WEBOTS_IMAGE_DIGEST}"
PACKAGED_RUNTIME_READY = "WEBEEBLOCKS_RUNTIME_V2 READY"
CANONICAL_CI_WORKFLOW = "CI Gate"

sys.path.insert(0, str(ROOT / "tools" / "physical"))
import package_physical_qualification as packager  # noqa: E402

sys.path.insert(0, str(ROOT / "tools" / "ci"))
import select_qualification_runtime_support as selector  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def run_verify(bundle: Path, *, success: bool) -> None:
    result = subprocess.run(
        [sys.executable, str(VERIFIER), str(bundle), "--manifest-only"],
        text=True,
        capture_output=True,
    )
    if success and result.returncode != 0:
        raise AssertionError("package verifier unexpectedly failed\n" + result.stdout + result.stderr)
    if not success and result.returncode == 0:
        raise AssertionError("package verifier accepted a mutated package")


def run_perspective_self_test(bundle: Path) -> None:
    helper = bundle / "tools" / "physical" / "qualification_perspective.py"
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONNOUSERSITE"] = "1"
    env.pop("PYTHONPATH", None)
    result = subprocess.run(
        [sys.executable, str(helper), "--self-test"],
        cwd=bundle,
        text=True,
        capture_output=True,
        env=env,
    )
    expected = "PASS: exact R2025a ephemeral qualification perspective lifecycle verified"
    require(
        result.returncode == 0,
        "packaged perspective self-test failed\n" + result.stdout + result.stderr,
    )
    require(
        result.stdout.strip() == expected and not result.stderr,
        "packaged perspective self-test did not produce the exact causal PASS",
    )


def _canonical_ci_runtime_smoke_enabled() -> bool:
    return (
        os.environ.get("GITHUB_ACTIONS") == "true"
        and os.environ.get("GITHUB_WORKFLOW") == CANONICAL_CI_WORKFLOW
    )


def run_packaged_runtime_smoke(bundle: Path) -> None:
    """Prove the exact package controller reaches the R2025a runtime without hardware."""

    if not _canonical_ci_runtime_smoke_enabled():
        return

    source_sha = (bundle / "SOURCE_SHA").read_text(encoding="utf-8").strip()
    manifest_bytes = (bundle / "SHA256SUMS.json").read_bytes()
    fingerprint = f"{source_sha} {hashlib.sha256(manifest_bytes).hexdigest()}\n"

    evidence = ROOT / "ci-artifacts" / "physical-qualification-runtime-smoke"
    evidence.mkdir(parents=True, exist_ok=True)
    stamp = evidence / "PASS.fingerprint"
    webots_log = evidence / "webots.log"

    if stamp.is_file() and webots_log.is_file():
        require(
            stamp.read_text(encoding="utf-8") == fingerprint,
            "packaged Runtime smoke evidence fingerprint does not match the exact bundle",
        )
        require(
            PACKAGED_RUNTIME_READY in webots_log.read_text(encoding="utf-8", errors="replace"),
            "packaged Runtime smoke reuse lacks the exact READY evidence",
        )
        print("PASS: exact packaged Runtime v2 R2025a startup smoke already proven in this canonical CI job")
        return

    inner = r"""
set -euo pipefail
work=/tmp/webeeblocks-physical-qualification-smoke
home=/tmp/webeeblocks-physical-qualification-home
rm -rf "$work" "$home"
cp -a /bundle "$work"
world="$work/worlds/.webeeblocks-qualification-ci-smoke.wbt"
cp "$work/tools/physical/qualification_world.wbt" "$world"
mkdir -p "$home/.config/Cyberbotics"
printf '%s\n' \
  '[RobotWindow]' \
  'browser=/bin/true' \
  'newBrowserWindow=false' \
  > "$home/.config/Cyberbotics/Webots-R2025a.conf"

set +e
env -u LD_LIBRARY_PATH -u WEBOTS_LIBRARY_PATH -u QT_PLUGIN_PATH \
  HOME="$home" \
  LIBGL_ALWAYS_SOFTWARE=true \
  WEBOTS_DISABLE_SAVE_SCREEN_PERSPECTIVE_ON_CLOSE=true \
  timeout -k 5s 20s xvfb-run -a webots --stdout --stderr --batch --mode=fast "$world" \
  > /evidence/webots.log 2>&1
code=$?
set -e
printf '%s\n' "$code" > /evidence/exit-code.txt
cat /evidence/webots.log
case "$code" in
  0|124) ;;
  *) exit "$code" ;;
esac
grep -Fq 'WEBEEBLOCKS_RUNTIME_V2 READY' /evidence/webots.log
"""

    command = [
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "-v",
        f"{bundle}:/bundle:ro",
        "-v",
        f"{evidence}:/evidence",
        WEBOTS_IMAGE,
        "bash",
        "-lc",
        inner,
    ]
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=120,
        )
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout or ""
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        (evidence / "driver.log").write_text(output, encoding="utf-8")
        raise AssertionError("packaged Runtime smoke timed out before a bounded result\n" + output[-8000:]) from exc

    (evidence / "driver.log").write_text(result.stdout, encoding="utf-8")
    require(
        result.returncode == 0,
        "packaged Runtime smoke failed\n" + result.stdout[-8000:],
    )
    require(webots_log.is_file(), "packaged Runtime smoke did not retain the Webots log")
    log_text = webots_log.read_text(encoding="utf-8", errors="replace")
    require(PACKAGED_RUNTIME_READY in log_text, "packaged Runtime v2 never reached READY")
    for forbidden in (
        "WEBEEBLOCKS_RUNTIME_V2 FATAL",
        "error while loading shared libraries",
        "Qt_6.5' not found",
        "Qt_6.5` not found",
    ):
        require(forbidden not in log_text, f"packaged Runtime startup contains loader/runtime failure: {forbidden}")
    stamp.write_text(fingerprint, encoding="utf-8")
    print("PASS: exact packaged Runtime v2 entered the pinned R2025a controller runtime without hardware")


def verify_static_contract() -> None:
    runner = RUNNER.read_text(encoding="utf-8")
    for required in (
        "--no-index",
        "--no-deps",
        "PYTHONNOUSERSITE=1",
        "PYTHONDONTWRITEBYTECODE=1",
        "verify_physical_qualification_package.py",
        "launch_physical_qualification.py",
        "chmod u+x",
        "WEBOTS_HOME",
        "--version",
        "R2025a",
        '--webots "$WEBOTS_BIN"',
    ):
        require(required in runner, f"offline runner missing contract: {required}")
    for forbidden in ("curl ", "wget ", "http://", "https://"):
        require(forbidden not in runner, f"offline runner must not use network: {forbidden}")

    verifier = VERIFIER.read_text(encoding="utf-8")
    for required in (
        'env["PYTHONDONTWRITEBYTECODE"] = "1"',
        "_git_tree_oid(cflib_root).hex() != EXPECTED_CFLIB_TREE",
        "runtime.verify_isolated_imports(cflib, locked)",
        '"controllers/crazyflie_runtime_v2/runtime.ini"',
        '"WEBOTS_LIBRARY_PATH = $(WEBOTS_HOME)/lib/webots"',
        '"QT_PLUGIN_PATH = $(WEBOTS_HOME)/lib/webots/qt/plugins"',
    ):
        require(required in verifier, f"package verifier missing canonical read-only contract: {required}")

    packager_source = PACKAGER.read_text(encoding="utf-8")
    for required in (
        '"status", "--porcelain", "--untracked-files=no"',
        '"--untracked-files=all"',
        '"--ignored"',
        '"-z"',
        "PACKAGED_SOURCE_PATHS",
        "GENERATED_VENDOR_PREFIX",
        "_unexpected_untracked_package_paths",
        '"archive",',
        "EXPECTED_CFLIB_COMMIT",
        "WEBOTS_BUILD_IMAGE_DIGEST",
        '"runtime.ini"',
    ):
        require(required in packager_source, f"packager missing exact provenance contract: {required}")

    untracked = packager._unexpected_untracked_package_paths(
        "?? tools/physical/rogue.py\n"
        "?? plugins/robot_windows/blockly_v2/rogue.js\n"
        "?? controllers/crazyflie_runtime_v2/rogue.cpp\n"
        "?? controllers/crazyflie_runtime_v2/runtime.ini\n"
        "?? controllers/crazyflie_runtime_v2/crazyflie_runtime_v2\n"
        "?? controllers/crazyflie_runtime_v2/build-state.d\n"
    )
    require(
        untracked
        == (
            "controllers/crazyflie_runtime_v2/rogue.cpp",
            "controllers/crazyflie_runtime_v2/runtime.ini",
            "plugins/robot_windows/blockly_v2/rogue.js",
            "tools/physical/rogue.py",
        ),
        "packager must reject every non-ignored untracked path that would enter the artifact while allowing generated non-copied/controller outputs",
    )

    unusual_untracked = packager._unexpected_untracked_package_paths(
        "?? tools/physical/rogue file.py\0"
        "?? tools/physical/ligne\nétrange.py\0"
        "?? plugins/robot_windows/blockly_v2/élève.js\0"
        "?? controllers/crazyflie_runtime_v2/crazyflie_runtime_v2\0"
        "?? controllers/crazyflie_runtime_v2/build-state.d\0"
    )
    require(
        unusual_untracked
        == tuple(
            sorted(
                (
                    "plugins/robot_windows/blockly_v2/élève.js",
                    "tools/physical/ligne\nétrange.py",
                    "tools/physical/rogue file.py",
                )
            )
        ),
        "NUL-delimited porcelain must preserve spaces, non-ASCII and embedded newlines in packaged untracked paths",
    )

    ignored = packager._unexpected_untracked_package_paths(
        "!! tools/physical/rogue.so\0"
        "!! plugins/robot_windows/blockly/webeeblocks/.probe.swp\0"
        "!! plugins/robot_windows/blockly_v2/.DS_Store\0"
        "!! plugins/robot_windows/blockly_v2/vendor/blockly_compressed.js\0"
        "!! controllers/crazyflie_runtime_v2/runtime.ini\0"
        "!! controllers/crazyflie_runtime_v2/crazyflie_runtime_v2\0"
        "!! controllers/crazyflie_runtime_v2/build-state.d\0"
    )
    require(
        ignored
        == tuple(
            sorted(
                (
                    "controllers/crazyflie_runtime_v2/runtime.ini",
                    "plugins/robot_windows/blockly/webeeblocks/.probe.swp",
                    "plugins/robot_windows/blockly_v2/.DS_Store",
                    "tools/physical/rogue.so",
                )
            )
        ),
        "ignored copied bytes must fail exact-source packaging while deterministic vendor/controller outputs remain allowed",
    )

    representative_inputs = (
        "tools/physical/physical_execution_domain.py",
        "tools/physical/qualification_generated_lock.json",
        "tools/physical/verify_qualification_generated_inputs.py",
        "tools/prepare_runtime_v2.sh",
        "plugins/robot_windows/blockly_v2/main.js",
        "plugins/robot_windows/blockly/webeeblocks/interpreter.js",
        "plugins/robot_windows/blockly/google-blockly-31ee4ea/blocks/crazyflie_v2.js",
        "plugins/robot_windows/blockly/google-blockly-31ee4ea/media/sprites.svg",
        "worlds/crazyflie_runtime_v2.wbt",
        "controllers/crazyflie_runtime_v2/crazyflie_runtime_v2.cpp",
        "controllers/crazyflie_runtime_v2/runtime.ini",
        "controllers/crazyflie_square/pid_controller.c",
    )
    for path in representative_inputs:
        require(selector.relevant_path(path), f"packaged input must select qualification proof: {path}")
    require(not selector.relevant_path("docs/ROADMAP.md"), "unrelated docs must not select package proof")

    workflow = WORKFLOW.read_text(encoding="utf-8")
    for required in (
        "name: CI Gate",
        "# BEGIN PHYSICAL_QUALIFICATION_RUNTIME_SUPPORT",
        "qualification-runtime-ubuntu22-cp310-cflib-45fdb784",
        "qualification-package-inputs-r2025a-",
        WEBOTS_IMAGE_DIGEST,
        "qualification_generated_lock.json",
        "python3 tools/physical/verify_qualification_generated_inputs.py",
        "python3 tools/physical/package_physical_qualification.py",
        "python3 tools/physical/verify_physical_qualification_package.py",
        "python3 tools/ci/test_physical_qualification_package.py",
        "name: WebeeBlocks-Physical-Qualification",
        "path: ci-artifacts/physical-qualification/WebeeBlocks-Physical-Qualification/",
        "include-hidden-files: true",
    ):
        require(required in workflow, f"canonical workflow missing package contract: {required}")
    require(
        workflow.count("python3 tools/physical/verify_qualification_generated_inputs.py") >= 2,
        "generated inputs must be verified after Draft generation and after every cache restore",
    )
    restore_cache = workflow.split(
        "- name: Restore exact prepared qualification package inputs", 1
    )[1].split("- uses: actions/setup-node@v4", 1)[0]
    save_cache = workflow.split(
        "- name: Save exact prepared qualification package inputs for maintenance runs", 1
    )[1].split("- name: Fail closed unless exact qualification package inputs are restored", 1)[0]
    for cache_block in (restore_cache, save_cache):
        require(
            "plugins/robot_windows/blockly_v2/webots" not in cache_block,
            "prepared-input cache must never restore tracked candidate Webots bridge bytes",
        )
        for required in (
            "plugins/robot_windows/blockly_v2/prepare_blockly_vendor.js",
            "plugins/robot_windows/blockly/google-blockly-31ee4ea/media/sprites.svg",
            "plugins/robot_windows/blockly/google-blockly-31ee4ea/media/sprites.png",
            "tools/physical/qualification_generated_lock.json",
        ):
            require(required in cache_block, f"generated cache key missing bound input: {required}")
    require(
        "ci-artifacts/physical-qualification/WebeeBlocks-Physical-Qualification.zip"
        not in workflow,
        "package workflow must not create/upload a nested ZIP",
    )
    require(
        "CHECKPOINT_REQUEST" not in workflow and "TEST_REQUIRED" not in workflow,
        "machine-only package path must not open a human checkpoint",
    )
    require(
        workflow.count("github.event.pull_request.draft == true") >= 4,
        "network/cache priming must stay Draft/maintenance-only",
    )
    require("restore-keys:" not in workflow, "package caches must be exact-key only")

    human = HUMAN_WORKFLOW.read_text(encoding="utf-8")
    for required in (
        "'physical-capabilities-representative': 'WebeeBlocks-Physical-Qualification',",
        "'physical-capabilities-representative': {'checkpoint'},",
        "needs.validate.outputs.test_profile == 'physical-capabilities-representative'",
        "id: representative-runtime-cache",
        "id: representative-package-input-cache",
        "qualification-runtime-ubuntu22-cp310-cflib-45fdb784c9d13074c42835f3b5ac1d12133bf873-${{ hashFiles('tools/physical/qualification_runtime_lock.txt') }}",
        "qualification-package-inputs-r2025a-f0023e30daf38b17-",
        'test "${{ steps.representative-runtime-cache.outputs.cache-hit }}" = "true"',
        'test "${{ steps.representative-package-input-cache.outputs.cache-hit }}" = "true"',
        'target_sha="${{ needs.validate.outputs.target_sha }}"',
        'test "$(git rev-parse HEAD)" = "$target_sha"',
        'python3 tools/physical/verify_qualification_runtime.py "$source" "$wheelhouse"',
        "python3 tools/physical/verify_qualification_generated_inputs.py",
        "python3 tools/physical/package_physical_qualification.py",
        "python3 tools/physical/verify_physical_qualification_package.py",
        "python3 tools/ci/test_physical_qualification_package.py",
        "name: WebeeBlocks-Physical-Qualification",
        "path: ci-artifacts/physical-qualification/WebeeBlocks-Physical-Qualification/",
        "include-hidden-files: true",
    ):
        require(required in human, f"representative checkpoint missing exact package contract: {required}")
    representative = human.split(
        "- name: Restore exact physical qualification runtime support", 1
    )[1].split("\n  publish:", 1)[0]
    for forbidden in (
        "actions/setup-node",
        "actions/cache/save",
        "pip download",
        "docker pull",
        "docker run",
        "repository: bitcraze/crazyflie-lib-python",
        "restore-keys:",
        ".zip",
    ):
        require(forbidden not in representative, f"representative checkpoint must restore-and-verify only: {forbidden}")
    publish = human.split("\n  publish:\n", 1)[1]
    require(
        "needs.validate.outputs.test_profile != 'physical-capabilities-representative'" in publish
        and "needs.physical.result == 'success'" in publish,
        "representative checkpoint publication must require successful deterministic physical artifact preparation",
    )


def verify_built_bundle(bundle: Path) -> None:
    run_verify(bundle, success=True)
    run_perspective_self_test(bundle)

    source_sha = bundle / "SOURCE_SHA"
    original = source_sha.read_bytes()
    try:
        source_sha.write_bytes(original + b"x")
        run_verify(bundle, success=False)
    finally:
        source_sha.write_bytes(original)

    extra = bundle / "unexpected-controller-or-dependency.txt"
    try:
        extra.write_text("unexpected\n", encoding="utf-8")
        run_verify(bundle, success=False)
    finally:
        extra.unlink(missing_ok=True)

    run_verify(bundle, success=True)

    manifest = (bundle / "SHA256SUMS.json").read_text(encoding="utf-8")
    require(
        manifest.count(".whl") == 7,
        "package manifest must contain exactly seven locked wheels",
    )
    require(
        '"path": "controllers/crazyflie_runtime_v2/runtime.ini"' in manifest,
        "package manifest must bind the Runtime v2 Linux environment contract",
    )
    require("/.git/" not in manifest and "/.git\"" not in manifest, "package must omit checkout Git metadata")
    require(not (bundle / "support" / "cflib-source" / ".git").exists(), "canonical cflib source must omit .git")

    provenance = (bundle / "PROVENANCE.json").read_text(encoding="utf-8")
    require(
        '"preparation_execution_authority": false' in provenance,
        "package preparation must remain non-authority",
    )
    require(
        '"execution_requires_teacher_authorization": true' in provenance,
        "packaged execution must retain teacher authorization",
    )
    require(WEBOTS_IMAGE_DIGEST in provenance, "package provenance must bind exact Webots build image")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args(argv)
    bundle = args.bundle.resolve()

    verify_static_contract()
    if bundle.is_dir():
        verify_built_bundle(bundle)
        run_packaged_runtime_smoke(bundle)
        print(
            "PASS: exact offline physical qualification package, canonical provenance, mutation rejection and no-checkpoint CI contract"
        )
    else:
        print("PASS: physical qualification package static CI contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
