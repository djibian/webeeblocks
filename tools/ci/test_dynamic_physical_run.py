#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import subprocess
from types import SimpleNamespace
import sys

ROOT = Path(__file__).resolve().parents[2]
PHYSICAL = ROOT / "tools" / "physical"
if str(PHYSICAL) not in sys.path:
    sys.path.insert(0, str(PHYSICAL))

import dynamic_physical_run as subject  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


class FakeBackend:
    ast_binding = "canonical-ast"

    def __init__(self) -> None:
        self.closed = 0

    def close(self) -> None:
        self.closed += 1


def test_exact_backend_and_one_shot_execution() -> None:
    original_backend = subject.TrustedDynamicPhysicalBackend
    original_interpreter = subject.BoundSharedInterpreter

    class ExactBackend(FakeBackend):
        pass

    class FakeInterpreter:
        calls: list[tuple[str, object]] = []

        def __init__(self, ast_binding: str, backend: object) -> None:
            self.ast_binding = ast_binding
            self.backend = backend

        def run(self):
            self.calls.append((self.ast_binding, self.backend))
            return SimpleNamespace(remaining_budget=7, variables={})

    subject.TrustedDynamicPhysicalBackend = ExactBackend
    subject.BoundSharedInterpreter = FakeInterpreter
    try:
        backend = ExactBackend()
        run = subject.BoundDynamicPhysicalRun(backend)
        result = run.execute()
        require(result.accepted is True, "successful bound run must return non-authority acceptance data")
        require(
            FakeInterpreter.calls == [("canonical-ast", backend)],
            "dynamic run must execute exactly the bound shared interpreter/backend pair",
        )
        try:
            run.execute()
        except subject.DynamicPhysicalRunError as exc:
            require("one-shot" in str(exc), "second execution failed for wrong reason")
        else:
            raise AssertionError("bound dynamic physical run was reusable")
        run.close()
        require(backend.closed == 1, "dynamic run must close backend-owned observers")
    finally:
        subject.TrustedDynamicPhysicalBackend = original_backend
        subject.BoundSharedInterpreter = original_interpreter


def test_interpreter_failure_is_fail_closed_but_cleanup_remains_explicit() -> None:
    original_backend = subject.TrustedDynamicPhysicalBackend
    original_interpreter = subject.BoundSharedInterpreter

    class ExactBackend(FakeBackend):
        pass

    class FailingInterpreter:
        def __init__(self, _ast_binding: str, _backend: object) -> None:
            pass

        def run(self):
            raise RuntimeError("worker lost")

    subject.TrustedDynamicPhysicalBackend = ExactBackend
    subject.BoundSharedInterpreter = FailingInterpreter
    try:
        backend = ExactBackend()
        run = subject.BoundDynamicPhysicalRun(backend)
        try:
            run.execute()
        except subject.DynamicPhysicalRunError as exc:
            require("failed closed" in str(exc), "interpreter failure escaped fail-closed boundary")
        else:
            raise AssertionError("interpreter failure was accepted")
        require(backend.closed == 0, "run wrapper must not hide teardown outcome during execution failure")
        run.close()
        require(backend.closed == 1, "trusted host can still perform explicit terminal cleanup")
    finally:
        subject.TrustedDynamicPhysicalBackend = original_backend
        subject.BoundSharedInterpreter = original_interpreter


def run_production_regression(relative_path: str, label: str) -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / relative_path)],
        text=True,
        capture_output=True,
    )
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.returncode:
        if result.stderr.strip():
            print(result.stderr.strip(), file=sys.stderr)
        raise AssertionError(label)


def main() -> int:
    test_exact_backend_and_one_shot_execution()
    test_interpreter_failure_is_fail_closed_but_cleanup_remains_explicit()
    # These production-host regressions install broad fake trusted-host surfaces.
    # Run each in a fresh interpreter so one oracle cannot leak monkeypatch state
    # into the next and manufacture a false product-path failure.
    run_production_regression(
        "tools/ci/test_dynamic_run_activation.py",
        "production dynamic activation/dispatch regression must pass",
    )
    run_production_regression(
        "tools/ci/test_physical_dynamic_run_activation.py",
        "production dynamic host range/recovery regression must pass",
    )
    print(
        "PASS dynamic physical run owner: exact bound shared interpreter, one-shot execution, "
        "production activation/dispatch, fresh range host path and terminal recovery"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
