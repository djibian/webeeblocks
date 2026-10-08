#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "tools" / "physical" / "package_x3_characterization.py"
VERIFIER_PATH = ROOT / "tools" / "physical" / "verify_x3_characterization_bundle.py"
PREPARE = ROOT / "tools" / "physical" / "prepare_x3_independent_capture.py"
NO_COMMANDER_LINK = ROOT / "tools" / "physical" / "x3_no_commander_link.py"
RESET_FIRMWARE_TEST = ROOT / "tools" / "ci" / "test_x3_reset_firmware_semantics.py"
PREPARE_RUNNER = ROOT / "tools" / "physical" / "prepare_x3_independent_capture.sh"
RUNNER = ROOT / "tools" / "physical" / "run_x3_independent_capture.sh"
EXPERIMENT = ROOT / "experiments" / "crazyflie-ukf-surface-range"
CAPTURE = EXPERIMENT / "capture_independent_inputs.py"
METRIC_REFERENCE_TEST = EXPERIMENT / "test_metric_reference.py"
METRIC_REFERENCE_EXACT_JSON_TEST = EXPERIMENT / "test_metric_reference_exact_json.py"
HUMAN_WORKFLOW = ROOT / ".github" / "workflows" / "human-checkpoint.yml"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
QUALIFICATION_SUPPORT = ROOT / ".ci-support" / "qualification-runtime"
FIRMWARE_FIXTURE = QUALIFICATION_SUPPORT / "x3-firmware" / "cf2.bin"
RESET_PROVENANCE_251 = EXPERIMENT / "evidence" / "checkpoint-251" / "raw" / "README.txt"
RESET_PROVENANCE_236 = (
    EXPERIMENT / "evidence" / "checkpoint-236" / "raw"
    / "S3-8561ec3-checkpoint-236-evidence" / "README.txt"
)
RESET_SESSION = (
    EXPERIMENT / "evidence" / "checkpoint-180" / "raw"
    / "S3-173b7c5-bundle" / "s3_session.py"
)
RESET_TOC = (
    EXPERIMENT / "evidence" / "checkpoint-180" / "raw"
    / "S3-173b7c5-bundle" / "results-20ms" / "cache" / "E5446F4B.json"
)

REAL_BUNDLE_PROOF_PATHS = frozenset(
    {
        ".github/workflows/human-checkpoint.yml",
        "tools/ci/test_x3_characterization_package.py",
        "tools/physical/package_x3_characterization.py",
        "tools/physical/prepare_x3_independent_capture.py",
        "tools/physical/x3_no_commander_link.py",
        "tools/ci/test_x3_reset_firmware_semantics.py",
        "tools/physical/prepare_x3_independent_capture.sh",
        "tools/physical/run_x3_independent_capture.sh",
        "tools/physical/verify_x3_characterization_bundle.py",
        "tools/physical/prepare_x3_firmware_fixture.py",
        "tools/physical/x3_runtime_lock.txt",
        "tools/physical/qualification_runtime_lock.txt",
        "experiments/crazyflie-ukf-surface-range/capture_independent_inputs.py",
        "experiments/crazyflie-ukf-surface-range/metric_reference.py",
        "experiments/crazyflie-ukf-surface-range/X3_CHARACTERIZATION_PROCEDURE.md",
        "experiments/crazyflie-ukf-surface-range/X3_REFERENCE_WITNESS.md",
        "experiments/crazyflie-ukf-surface-range/X3_REFERENCE_WITNESS_TEMPLATE.csv",
        "experiments/crazyflie-ukf-surface-range/run_s3_build_oracle.sh",
        "experiments/crazyflie-ukf-surface-range/apply_surface_offset_s3.py",
        "experiments/crazyflie-ukf-surface-range/apply_surface_offset_s3_veto_discriminator.py",
        "experiments/crazyflie-ukf-surface-range/apply_surface_offset_s3_timing_observer.py",
    }
)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


package = load_module("package_x3_characterization", MODULE_PATH)
manifest = load_module("verify_x3_characterization_bundle", VERIFIER_PATH)
no_commander_link = load_module("x3_no_commander_link_test", NO_COMMANDER_LINK)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def expect_package_error(callable_, contains: str) -> None:
    try:
        callable_()
    except package.PackageError as exc:
        require(contains in str(exc), f"expected {contains!r} in {exc!r}")
        return
    raise AssertionError(f"expected PackageError containing {contains!r}")


def expect_manifest_error(callable_, contains: str) -> None:
    try:
        callable_()
    except manifest.ManifestError as exc:
        require(contains in str(exc), f"expected {contains!r} in {exc!r}")
        return
    raise AssertionError(f"expected ManifestError containing {contains!r}")


def file_snapshot(root: Path) -> tuple[tuple[str, int, str], ...]:
    rows = []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        rows.append((path.relative_to(root).as_posix(), path.stat().st_size, digest))
    return tuple(rows)


def verify_manifest_oracles() -> None:
    with tempfile.TemporaryDirectory(prefix="webeeblocks-x3-manifest-test-") as temp_text:
        bundle = Path(temp_text) / "bundle"
        bundle.mkdir()
        (bundle / "alpha.txt").write_text("alpha\n", encoding="utf-8")
        (bundle / "nested").mkdir()
        (bundle / "nested" / "beta.bin").write_bytes(b"beta\x00")
        shutil.copy2(VERIFIER_PATH, bundle / "verify_x3_characterization_bundle.py")
        package.write_manifest(bundle)

        before = file_snapshot(bundle)
        manifest.verify_bundle(bundle)
        subprocess.run(
            [sys.executable, "-B", str(bundle / "verify_x3_characterization_bundle.py"), str(bundle)],
            check=True,
            text=True,
            capture_output=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        require(file_snapshot(bundle) == before, "manifest verification must be observational")

        extra = bundle / "unexpected.py"
        extra.write_text("raise RuntimeError('must never enter bundle')\n", encoding="utf-8")
        expect_manifest_error(lambda: manifest.verify_bundle(bundle), "file set mismatch")
        extra.unlink()

        beta = bundle / "nested" / "beta.bin"
        original_beta = beta.read_bytes()
        beta.unlink()
        expect_manifest_error(lambda: manifest.verify_bundle(bundle), "file set mismatch")
        beta.write_bytes(original_beta)

        alpha = bundle / "alpha.txt"
        original_alpha = alpha.read_bytes()
        alpha.write_bytes(original_alpha + b"x")
        expect_manifest_error(lambda: manifest.verify_bundle(bundle), "size mismatch")
        alpha.write_bytes(original_alpha)
        manifest.verify_bundle(bundle)


def verify_capture_retention_oracles() -> None:
    # Execute the production acquisition/retention tail with a synthetic
    # collector. Earlier exact-bundle/record/live-health admission is outside
    # this shell-boundary test; no hardware module is imported here.
    runner = RUNNER.read_text(encoding="utf-8")
    capture_at = runner.rindex('python3 -B -S "$HERE/capture_independent_inputs.py"')
    tail = runner[runner.rfind("\n\n", 0, capture_at) + 2:]
    collector = '''import os, pathlib, sys
output = pathlib.Path(sys.argv[sys.argv.index("--output") + 1])
if os.environ["TEST_CREATE_OUTPUT"] == "1":
    output.mkdir()
    (output / "pose.csv").write_bytes(b"SYNTHETIC retained raw row\\n")
    (output / "capture-result.json").write_bytes(b'{"synthetic":true}\\n')
    if os.environ["TEST_CONFLICT"] == "1":
        (output / "preparation-record.json").write_bytes(b"existing evidence\\n")
    elif os.environ["TEST_CONFLICT"] == "2":
        (output / "preparation-record.sha256").write_bytes(b"existing digest\\n")
sys.exit(int(os.environ["TEST_CAPTURE_STATUS"]))
'''
    harness = '''set -euo pipefail
python3() { command "$TEST_PYTHON" "$@"; }
verify_bundle() { touch "$TEST_VERIFIED"; }
''' + tail
    for status, create_output, conflict in (
        (0, True, False), (13, True, False), (13, False, False),
        (0, False, False), (13, True, True), (13, True, 2),
    ):
        with tempfile.TemporaryDirectory(prefix="webeeblocks-x3-retention-") as temp_text:
            root = Path(temp_text)
            here = root / "bundle with spaces"
            here.mkdir()
            (here / "capture_independent_inputs.py").write_text(collector, encoding="utf-8")
            record = root / "prepared.json"
            record.write_bytes(b'{"synthetic_preparation":"retain exact bytes"}\n')
            output = root / "capture"
            verified = root / "verified"
            result = subprocess.run(
                ["bash", "-c", harness], text=True, capture_output=True,
                env={**os.environ, "HERE": str(here), "ISOLATED_SITE": str(root / "site"),
                     "URI": "radio://0/80/2M", "CHECKPOINT_URL": "https://github.com/djibian/webeeblocks/issues/561",
                     "REQUEST_SHA": "a" * 40, "OUTPUT": str(output), "DURATION_SECONDS": "30",
                     "PREPARATION_RECORD": str(record), "TEST_PYTHON": sys.executable,
                     "TEST_VERIFIED": str(verified), "TEST_CAPTURE_STATUS": str(status),
                     "TEST_CREATE_OUTPUT": str(int(create_output)), "TEST_CONFLICT": str(int(conflict))},
            )
            if conflict:
                require(result.returncode != 0, "existing preparation evidence must reject retention")
                if conflict == 1:
                    require((output / "preparation-record.json").read_bytes() == b"existing evidence\n",
                            "retention overwrote existing preparation evidence")
                else:
                    require((output / "preparation-record.sha256").read_bytes() == b"existing digest\n",
                            "retention overwrote existing preparation digest")
                continue
            require(result.returncode == (2 if status == 0 and not create_output else status),
                    f"collector outcome changed: {result.returncode}, {result.stderr}")
            if not create_output:
                require(not output.exists(), "runner manufactured a capture that never started")
                continue
            require((output / "pose.csv").read_bytes() == b"SYNTHETIC retained raw row\n",
                    "retention changed partial raw evidence")
            require((output / "capture-result.json").read_bytes() == b'{"synthetic":true}\n',
                    "retention changed the collector result")
            require((output / "preparation-record.json").read_bytes() == record.read_bytes(),
                    "successful/incomplete acquisition lost its exact preparation binding")
            digest = (output / "preparation-record.sha256").read_text().split()[0]
            require(digest == hashlib.sha256(record.read_bytes()).hexdigest(),
                    "retained preparation digest does not match its bytes")
            require(verified.is_file(), "post-capture bundle verification was skipped")
    print("PASS: production X3 runner retains preparation on incomplete capture without masking failure")


def verify_metric_reference_oracles() -> None:
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    for test in (METRIC_REFERENCE_TEST, METRIC_REFERENCE_EXACT_JSON_TEST):
        subprocess.run(
            [sys.executable, "-B", str(test)],
            cwd=EXPERIMENT,
            env=env,
            check=True,
        )
    print("PASS: X3 metric-reference interval and exact-JSON regressions")


def verify_reset_provenance_oracles() -> None:
    checkpoint_251 = RESET_PROVENANCE_251.read_text(encoding="utf-8")
    checkpoint_236 = RESET_PROVENANCE_236.read_text(encoding="utf-8")
    session = RESET_SESSION.read_text(encoding="utf-8")
    toc = json.loads(RESET_TOC.read_text(encoding="utf-8"))

    reset = ((toc.get("ukf") or {}).get("resetEstimation") or {})
    require(reset.get("ctype") == "uint8_t", "retained UKF reset TOC type must be uint8_t")

    on = 'set_param_and_wait(cf, "ukf.resetEstimation", 1)'
    hold = "time.sleep(0.25)"
    off = 'set_param_and_wait(cf, "ukf.resetEstimation", 0)'
    settle = "for remaining in range(5, 0, -1):"
    for required in (on, hold, off, settle):
        require(required in session, f"retained reset procedure missing: {required}")
    require(
        session.index(on) < session.index(hold) < session.index(off) < session.index(settle),
        "retained reset pulse/settle order changed",
    )

    require(
        "fresh-reset stationary validation" in checkpoint_251
        and "first stationary precheck, excluded because estimator had already drifted" in checkpoint_251,
        "#251 must retain fresh-reset healthy vs pre-reset divergent provenance",
    )
    require(
        "resetEstimation pulsed before valid scenarios" in checkpoint_236
        and "estimator was already divergent/NaN" in checkpoint_236,
        "#236 must retain reset-vs-divergence provenance",
    )
    print("PASS: retained X3 reset type, pulse, settle and valid-run provenance verified")


def verify_no_commander_teardown_oracle() -> None:
    no_commander_link.self_test()
    helper = NO_COMMANDER_LINK.read_text(encoding="utf-8")
    require("def close_link_without_commander" in helper, "X3 no-Commander teardown helper missing")
    print("PASS: X3 no-Commander teardown regression verified")


def _pr_changed_paths() -> tuple[str, ...]:
    if os.environ.get("GITHUB_EVENT_NAME") != "pull_request":
        return ()
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        return ()
    event = json.loads(Path(event_path).read_text(encoding="utf-8"))
    pull_request = event.get("pull_request") or {}
    base = ((pull_request.get("base") or {}).get("sha") or "").strip()
    head = ((pull_request.get("head") or {}).get("sha") or "").strip()
    if not base or not head:
        raise AssertionError("exact pull-request base/head are required for X3 real-bundle proof")
    result = subprocess.run(
        ["git", "-C", str(ROOT), "diff", "--name-only", "--no-renames", f"{base}...{head}"],
        check=True,
        text=True,
        capture_output=True,
    )
    return tuple(line for line in result.stdout.splitlines() if line)


def _real_bundle_proof_required() -> bool:
    return bool(REAL_BUNDLE_PROOF_PATHS.intersection(_pr_changed_paths()))


def verify_real_bundle_execution(head: str, rows: tuple[tuple[str, str, str], ...]) -> None:
    if not _real_bundle_proof_required():
        return

    cflib_root = QUALIFICATION_SUPPORT / "cflib-source"
    support_wheels = QUALIFICATION_SUPPORT / "wheels"
    require((cflib_root / ".git").is_dir(), "exact qualification cflib support was not restored")
    require(support_wheels.is_dir(), "exact qualification wheel support was not restored")
    require(FIRMWARE_FIXTURE.is_file(), "exact cached #251 X3 firmware fixture was not restored")
    require(
        package.sha256(FIRMWARE_FIXTURE) == package.EXPECTED_FIRMWARE_SHA256,
        "cached X3 firmware fixture does not match exact #251 cf2.bin",
    )
    pinned_cflib = (cflib_root / "cflib" / "crazyflie" / "__init__.py").read_text(
        encoding="utf-8"
    )
    require(
        "self.commander.send_setpoint(0, 0, 0, 0)" in pinned_cflib,
        "pinned cflib close semantics changed; X3 no-Commander bypass must be re-reviewed",
    )

    with tempfile.TemporaryDirectory(prefix="webeeblocks-x3-real-bundle-") as temp_text:
        temp = Path(temp_text)
        wheelhouse = temp / "wheels"
        wheelhouse.mkdir()
        for _spec, filename, digest in rows:
            source = support_wheels / filename
            require(source.is_file(), f"restored qualification support is missing {filename}")
            require(package.sha256(source) == digest, f"restored qualification wheel changed: {filename}")
            shutil.copy2(source, wheelhouse / filename)
        package.verify_wheels(wheelhouse)

        output_root = temp / "output"
        output_root.mkdir()
        bundle = package.build(
            source_sha=head,
            firmware_bin=FIRMWARE_FIXTURE,
            cflib_root=cflib_root,
            wheelhouse=wheelhouse,
            output_root=output_root,
        )

        for required_name in (
            "X3_CHARACTERIZATION_PROCEDURE.md",
            "X3_REFERENCE_WITNESS.md",
            "X3_REFERENCE_WITNESS_TEMPLATE.csv",
            "x3_no_commander_link.py",
        ):
            require((bundle / required_name).is_file(), f"assembled X3 bundle missing {required_name}")
        provenance = (bundle / "PROVENANCE.txt").read_text(encoding="utf-8")
        for required in (
            f"upstream_firmware_commit={package.UPSTREAM_FIRMWARE_COMMIT}\n",
            "preparation=exact-flash-readback-firmware-autoclear-health-v3\n",
            "acquisition=no-commander-parameter-and-health-gates-v3\n",
            "reference_witness=measured-guide-csv-v1\n",
            "trial_rule=fixed-three-cycle-v1\n",
            "post_transition_z_reference=continuous-hold-required-v1\n",
            "evidence_profile=physical-csv-text-v1\n",
            "human_checkpoint=request-not-issued\n",
        ):
            require(required in provenance, f"assembled X3 bundle provenance missing {required.strip()}")

        verifier = bundle / "verify_x3_characterization_bundle.py"
        prepare_runner = bundle / "prepare_x3_independent_capture.sh"
        runner = bundle / "run_x3_independent_capture.sh"
        verification_env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}

        subprocess.run(
            [sys.executable, "-B", str(verifier), str(bundle)],
            cwd=bundle,
            env=verification_env,
            check=True,
        )
        before = file_snapshot(bundle)
        subprocess.run(
            ["bash", str(prepare_runner), "--verify-environment"],
            cwd=bundle,
            env=verification_env,
            check=True,
        )
        subprocess.run(
            ["bash", str(runner), "--verify-environment"],
            cwd=bundle,
            env=verification_env,
            check=True,
        )
        after = file_snapshot(bundle)
        require(after == before, "complete X3 --verify-environment paths mutated exact bundle bytes/file set")

        subprocess.run(
            [sys.executable, "-B", str(verifier), str(bundle)],
            cwd=bundle,
            env=verification_env,
            check=True,
        )

    print("PASS: assembled exact X3 bundle completed observational hardware-free verification from cached #251 fixture")


def main() -> int:
    rows = package.locked_wheels()
    require(len(rows) == 5, "X3 runtime must retain exactly five locked wheels")
    require(
        {row[1] for row in rows}
        == {
            "pyusb-1.2.1-py3-none-any.whl",
            "libusb_package-1.0.26.3-cp310-cp310-manylinux_2_17_x86_64.manylinux2014_x86_64.whl",
            "importlib_resources-6.5.2-py3-none-any.whl",
            "numpy-2.2.6-cp310-cp310-manylinux_2_17_x86_64.manylinux2014_x86_64.whl",
            "packaging-25.0-py3-none-any.whl",
        },
        "X3 package wheel identity changed",
    )

    head = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()
    require(package.require_source(head) == head, "clean exact repository HEAD must validate")
    expect_package_error(lambda: package.require_source("0" * 40), "does not match")
    expect_package_error(lambda: package.require_source("main"), "40-character")

    with tempfile.TemporaryDirectory(prefix="webeeblocks-x3-wheel-test-") as temp_text:
        wheelhouse = Path(temp_text)
        expect_package_error(lambda: package.verify_wheels(wheelhouse), "exactly locked wheels")
        for _spec, filename, _digest in rows:
            (wheelhouse / filename).write_bytes(b"not-the-locked-wheel")
        expect_package_error(lambda: package.verify_wheels(wheelhouse), "wheel digest mismatch")
        (wheelhouse / "unexpected.whl").write_bytes(b"x")
        expect_package_error(lambda: package.verify_wheels(wheelhouse), "exactly locked wheels")

    verify_manifest_oracles()
    verify_capture_retention_oracles()
    verify_metric_reference_oracles()
    verify_reset_provenance_oracles()
    verify_no_commander_teardown_oracle()
    subprocess.run(
        [sys.executable, "-B", str(ROOT / "tools/ci/test_x3_health_evidence.py")],
        check=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )

    source = MODULE_PATH.read_text(encoding="utf-8")
    for required in (
        package.EXPECTED_FIRMWARE_SHA256,
        package.EXPECTED_CFLIB_COMMIT,
        package.EXPECTED_CFLIB_TREE,
        package.EXPECTED_CFLIB_SUBTREE,
        '"status", "--porcelain", "--untracked-files=no"',
        '"archive", "--format=tar", EXPECTED_CFLIB_COMMIT, "cflib"',
        'MANIFEST_NAME = "MANIFEST.json"',
        'LOCK = ROOT / "tools" / "physical" / "x3_runtime_lock.txt"',
        'NO_COMMANDER_LINK = ROOT / "tools" / "physical" / "x3_no_commander_link.py"',
        'VERIFIER = ROOT / "tools" / "physical" / "verify_x3_characterization_bundle.py"',
        'PROCEDURE = EXPERIMENT / "X3_CHARACTERIZATION_PROCEDURE.md"',
        'REFERENCE_WITNESS = EXPERIMENT / "X3_REFERENCE_WITNESS.md"',
        'REFERENCE_WITNESS_TEMPLATE = EXPERIMENT / "X3_REFERENCE_WITNESS_TEMPLATE.csv"',
        'copy_file(PROCEDURE, bundle / "X3_CHARACTERIZATION_PROCEDURE.md")',
        'copy_file(REFERENCE_WITNESS, bundle / "X3_REFERENCE_WITNESS.md")',
        'copy_file(REFERENCE_WITNESS_TEMPLATE, bundle / "X3_REFERENCE_WITNESS_TEMPLATE.csv")',
        'copy_file(LOCK, bundle / "x3_runtime_lock.txt")',
        'copy_file(NO_COMMANDER_LINK, bundle / "x3_no_commander_link.py", executable=True)',
        '"preparation=exact-flash-readback-firmware-autoclear-health-v3"',
        '"acquisition=no-commander-parameter-and-health-gates-v3"',
        '"reference_witness=measured-guide-csv-v1"',
        '"trial_rule=fixed-three-cycle-v1"',
        '"post_transition_z_reference=continuous-hold-required-v1"',
        '"evidence_profile=physical-csv-text-v1"',
        '"human_checkpoint=request-not-issued"',
        "physical_effect=none-during-packaging",
        "firmware_flash=not-performed",
        "execution_authority=none",
    ):
        require(required in source, f"X3 package contract missing: {required}")
    require("shutil.copytree(cflib_root" not in source, "cflib checkout metadata must not be copied")

    human = HUMAN_WORKFLOW.read_text(encoding="utf-8")
    for required in (
        "'x3-independent-props-off': 'WebeeBlocks-X3-Characterization',",
        "'x3-independent-props-off': {'checkpoint'},",
        "id: x3-runtime-cache",
        "steps.x3-runtime-cache.outputs.cache-hit",
        "python3 tools/physical/prepare_x3_firmware_fixture.py",
        "done < tools/physical/x3_runtime_lock.txt",
        "python3 tools/physical/package_x3_characterization.py",
        'bash "$bundle/prepare_x3_independent_capture.sh" --verify-environment',
        "name: WebeeBlocks-X3-Characterization",
        "needs.validate.outputs.test_profile != 'x3-independent-props-off'",
    ):
        require(required in human, f"trusted X3 checkpoint preparation missing: {required}")

    prepare_source = PREPARE.read_text(encoding="utf-8")
    for required in (
        'SCHEMA = "webeeblocks.x3.preparation.v2"',
        'RESET_PARAMETER = "ukf.resetEstimation"',
        'RESET_CTYPE = "uint8_t"',
        'UPSTREAM_FIRMWARE_COMMIT = "54f31e243a0b28b67efef5ba20dbb6d9890a5478"',
        "RESET_AUTOCLEAR_TIMEOUT_SECONDS = 0.25",
        "RESET_CLIENT_RELEASE_DELAY_SECONDS = 0.25",
        "RESET_SETTLE_SECONDS = 5.0",
        '"stateEstimate.z": (-1.0, 5.0)',
        '"stateEstimate.vz": (-1.0, 1.0)',
        "wait_for_firmware_reset_autoclear",
        "pulse_estimator_reset",
        "firmware_autoclear_observed",
        "evaluate_health_samples",
        "--health-check",
        '"estimator_reset": "ukf.resetEstimation:uint8_t:request1->firmware-autoclear0;client0@0.25s"',
        "close_link_without_commander(cf)",
    ):
        require(required in prepare_source, f"X3 fresh-reset preparation contract missing: {required}")
    require("SyncCrazyflie" not in prepare_source, "X3 preparation must not use cflib close_link wrapper")
    require("cf.close_link()" not in prepare_source, "X3 preparation must not call cflib Commander-emitting close")

    prepare_runner = PREPARE_RUNNER.read_text(encoding="utf-8")
    for required in (
        'test -f "$HERE/x3_runtime_lock.txt"',
        "packaging",
        "from cflib.bootloader import Bootloader, Target",
        "--verify-environment",
        "ukf.resetEstimation",
        "0.25 s",
        "fixed 5 s",
        'test -f "$HERE/x3_no_commander_link.py"',
        'python3 -B -S "$HERE/x3_no_commander_link.py"',
    ):
        require(required in prepare_runner, f"X3 preparation runner contract missing: {required}")

    runner = RUNNER.read_text(encoding="utf-8")
    verifier_call = 'python3 -B "$HERE/verify_x3_characterization_bundle.py" "$HERE"'
    for required in (
        package.EXPECTED_FIRMWARE_SHA256,
        package.EXPECTED_CFLIB_COMMIT,
        package.EXPECTED_CFLIB_TREE,
        package.EXPECTED_CFLIB_SUBTREE,
        'EXPECTED_TEST_PROFILE="x3-independent-props-off"',
        'test -s "$HERE/x3_runtime_lock.txt"',
        "packaging",
        "from cflib.bootloader import Bootloader, Target",
        "--verify-environment",
        "--props-removed",
        "--installed-bin-confirmed",
        "--health-check",
        "export PYTHONDONTWRITEBYTECODE=1",
        verifier_call,
        'test -s "$HERE/x3_no_commander_link.py"',
        'python3 -B -S "$HERE/x3_no_commander_link.py"',
    ):
        require(required in runner, f"X3 runner contract missing: {required}")
    require(
        runner.count("\nverify_bundle\n") >= 3,
        "runner must verify exact bundle before and after environment probing and after capture",
    )
    require("sha256sum -c" not in runner, "runner must not accept manifest-listed files while ignoring extras")
    for forbidden in ("set_value", "send_position_setpoint", "send_hover_setpoint"):
        require(forbidden not in runner, f"X3 runner unexpectedly exposes effect surface: {forbidden}")

    ci_workflow = CI_WORKFLOW.read_text(encoding="utf-8")
    for required in (
        "tools/physical/prepare_x3_independent_capture.py",
        "tools/physical/x3_no_commander_link.py",
        "tools/ci/test_x3_reset_firmware_semantics.py",
        "python3 tools/ci/test_x3_reset_firmware_semantics.py .x3-crazyflie-firmware",
    ):
        require(required in ci_workflow, f"canonical CI missing X3 reset-semantics wiring: {required}")

    capture = CAPTURE.read_text(encoding="utf-8")
    for required in (
        'TEST_PROFILE = "x3-independent-props-off"',
        '"barometer": (20, ("baro.asl", "baro.pressure", "baro.temp"))',
        '"imu": (10, ("acc.x", "acc.y", "acc.z", "gyro.x", "gyro.y", "gyro.z"))',
        "--props-removed",
        "--installed-bin-confirmed",
        "close_link_without_commander(cf)",
    ):
        require(required in capture, f"collector contract missing: {required}")
    require("cf.close_link()" not in capture, "X3 collector must not call cflib Commander-emitting close")

    reset_test = RESET_FIRMWARE_TEST.read_text(encoding="utf-8")
    for required in (
        'EXPECTED_COMMIT = "54f31e243a0b28b67efef5ba20dbb6d9890a5478"',
        'EXPECTED_ESTIMATOR_BLOB = "57c0e8405c07b63a29538019895ed17d0a379440"',
        'PARAM_ADD(PARAM_UINT8, resetEstimation, &resetNavigation)',
        'paramSetInt(paramGetVarId("ukf", "resetEstimation"), 0);',
    ):
        require(required in reset_test, f"pinned reset-semantics oracle missing: {required}")

    verify_real_bundle_execution(head, rows)

    print("PASS: exact machine-only X3 characterization package, strict manifest and observational verification contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
