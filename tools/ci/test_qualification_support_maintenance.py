#!/usr/bin/env python3
"""Static contract for main-scoped physical qualification support maintenance."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "qualification-support-maintenance.yml"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
HUMAN_WORKFLOW = ROOT / ".github" / "workflows" / "human-checkpoint.yml"

RUNTIME_KEY = (
    "qualification-runtime-ubuntu22-cp310-cflib-"
    "45fdb784c9d13074c42835f3b5ac1d12133bf873-"
    "${{ hashFiles('tools/physical/qualification_runtime_lock.txt') }}"
)
PACKAGE_KEY_PREFIX = "qualification-package-inputs-r2025a-f0023e30daf38b17-"
WEBOTS_IMAGE = (
    "cyberbotics/webots@sha256:"
    "f0023e30daf38b172e4e6ad24ed345909bcd9551df34d63d824e121a7cebf099"
)
WEBOTS_SUPPORT_TAR = ".qualification-webots-r2025a-image.tar"
WEBOTS_SUPPORT_ID = ".qualification-webots-r2025a-image.id"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    ci = CI_WORKFLOW.read_text(encoding="utf-8")
    human = HUMAN_WORKFLOW.read_text(encoding="utf-8")

    for required in (
        "push:\n    branches: [main]",
        "workflow_dispatch:",
        "pull_request:",
        "if: github.event_name == 'pull_request'",
        "if: github.event_name != 'pull_request'",
        "actions/cache/restore@v4",
        "actions/cache/save@v4",
        "repository: bitcraze/crazyflie-lib-python",
        "ref: 45fdb784c9d13074c42835f3b5ac1d12133bf873",
        RUNTIME_KEY,
        PACKAGE_KEY_PREFIX,
        WEBOTS_IMAGE,
        WEBOTS_SUPPORT_TAR,
        WEBOTS_SUPPORT_ID,
        "docker save --output",
        "docker image inspect --format '{{.Id}}'",
        "python3 tools/physical/verify_qualification_runtime.py",
        "python3 tools/physical/verify_qualification_generated_inputs.py",
        "python3 tools/physical/package_physical_qualification.py",
        "python3 tools/physical/verify_physical_qualification_package.py",
        "python3 tools/ci/test_physical_qualification_package.py",
    ):
        require(required in workflow, f"maintenance workflow missing contract: {required}")

    require(
        workflow.count("actions/cache/save@v4") == 2,
        "maintenance workflow must save only the exact runtime and package-input caches",
    )
    require(
        workflow.count("actions/cache/restore@v4") == 2,
        "maintenance workflow must restore only the exact runtime and package-input caches",
    )
    require("restore-keys:" not in workflow, "maintenance cache restores must remain exact-key only")

    package_save = workflow.index("- name: Save exact prepared qualification package inputs")
    support_prime = workflow.index("- name: Prime exact cached Webots image support")
    package_verify = workflow.index("- name: Verify exact prepared qualification package inputs")
    require(
        support_prime < package_save < package_verify,
        "Webots support must be present in the saved cache, then sanitized/verified before packaging",
    )
    require(
        "if: steps.qualification-package-input-cache.outputs.cache-hit != 'true'" in workflow[support_prime:package_save],
        "Webots support may only be generated on an exact package-input cache miss",
    )
    verify_block = workflow[package_verify:]
    require(
        "if [ \"${{ steps.qualification-package-input-cache.outputs.cache-hit }}\" = \"true\" ]; then" in verify_block
        and f"test -s plugins/robot_windows/blockly_v2/vendor/{WEBOTS_SUPPORT_TAR}" in verify_block
        and f"test -s plugins/robot_windows/blockly_v2/vendor/{WEBOTS_SUPPORT_ID}" in verify_block,
        "restored cache hits must fail closed unless exact Webots smoke support is present",
    )

    for forbidden in (
        "issues: write",
        "CHECKPOINT_REQUEST",
        "TEST_REQUIRED",
        "ntfy.sh",
        "actions/upload-artifact",
    ):
        require(forbidden not in workflow, f"maintenance workflow must not gain human/publication authority: {forbidden}")

    for canonical in (ci, human):
        require(RUNTIME_KEY in canonical, "runtime cache identity drifted from a canonical consumer")
        require(PACKAGE_KEY_PREFIX in canonical, "package-input cache identity drifted from a canonical consumer")

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
    ):
        require(
            forbidden not in representative,
            f"representative human checkpoint must remain restore-and-verify only: {forbidden}",
        )

    print(
        "PASS: main-scoped qualification support maintenance is exact-key, preserves packaged Webots smoke support, stays non-authoritative and keeps the human checkpoint restore-only"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
