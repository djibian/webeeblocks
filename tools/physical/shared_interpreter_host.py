#!/usr/bin/env python3
"""Host-owned wrapper around the existing Runtime v2 JavaScript interpreter.

The exact canonical AST binding is the only semantic input. ``run()`` accepts no
caller-selected direction, value, branch, iteration or action parameter. A child
Node process loads the repository's existing ``interpreter.js`` and can request
only the fixed backend methods below over a private stdio protocol.

This adapter is deliberately not physical composition by itself: it owns no
Crazyflie session, observer or effect-transport authority. A later trusted host
must bind ``readRange`` to the fresh range observer and bind each action method to
its already-authorized consumer while re-establishing current-program provenance.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from math import isfinite
from pathlib import Path
from queue import Empty, Queue
import subprocess
from threading import Thread
from typing import Protocol, TextIO

from physical_dynamic_preflight import (
    ReachablePhysicalEnvelope,
    validate_bound_dynamic_program,
)

_WORKER = Path(__file__).with_name("shared_interpreter_worker.js")
_MAX_PROTOCOL_BYTES = 1024 * 1024
_PROTOCOL_IDLE_TIMEOUT_SECONDS = 2.0
_MOVE_DIRECTIONS = frozenset({"forward", "back", "left", "right"})
_VERTICAL_DIRECTIONS = frozenset({"up", "down"})
_RANGE_DIRECTIONS = frozenset({"front", "back", "left", "right", "up"})
_LIGHT_COLORS = frozenset({"off", "red", "green", "blue", "yellow", "white"})
_METHOD_ARITY = {
    "takeoff": 1,
    "land": 0,
    "move": 2,
    "vertical": 2,
    "turn": 1,
    "wait": 1,
    "setSpeed": 1,
    "setLight": 1,
    "readRange": 1,
}
_EOF = object()


class SharedInterpreterHostError(RuntimeError):
    """Fail-closed error for the host-owned shared interpreter adapter."""


class PhysicalInterpreterBackend(Protocol):
    def takeoff(self, height_m: float): ...
    def land(self): ...
    def move(self, direction: str, distance_m: float): ...
    def vertical(self, direction: str, distance_m: float): ...
    def turn(self, angle_deg: float): ...
    def wait(self, seconds: float): ...
    def setSpeed(self, speed_m_s: float): ...
    def setLight(self, color: str): ...
    def readRange(self, direction: str) -> float: ...


@dataclass(frozen=True, slots=True)
class SharedInterpreterResult:
    remaining_budget: int
    variables: dict[str, object]


class _LinePump:
    """Read child stdout without letting a silent child block the trusted host."""

    def __init__(self, stream: TextIO) -> None:
        self._queue: Queue[object] = Queue()

        def pump() -> None:
            try:
                while True:
                    line = stream.readline()
                    if not line:
                        break
                    self._queue.put(line)
            except Exception as exc:  # pragma: no cover - defensive transport path
                self._queue.put(exc)
            finally:
                self._queue.put(_EOF)

        Thread(target=pump, name="shared-interpreter-stdout", daemon=True).start()

    def read(self) -> str:
        try:
            item = self._queue.get(timeout=_PROTOCOL_IDLE_TIMEOUT_SECONDS)
        except Empty as exc:
            raise SharedInterpreterHostError(
                "shared interpreter protocol timed out"
            ) from exc
        if item is _EOF:
            raise SharedInterpreterHostError(
                "shared interpreter exited before completion"
            )
        if isinstance(item, Exception):
            raise SharedInterpreterHostError(
                "shared interpreter output failed"
            ) from item
        if not isinstance(item, str):
            raise SharedInterpreterHostError(
                "shared interpreter output is malformed"
            )
        return item


def _finite_number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SharedInterpreterHostError(label + " must be finite")
    parsed = float(value)
    if not isfinite(parsed):
        raise SharedInterpreterHostError(label + " must be finite")
    return parsed


def _exact_string(value: object, allowed: frozenset[str], label: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise SharedInterpreterHostError(label + " is unsupported")
    return value


class BoundSharedInterpreter:
    """One exact-AST interpreter execution with no caller-selected semantics."""

    def __init__(self, ast_binding: str, backend: PhysicalInterpreterBackend) -> None:
        self._safety: ReachablePhysicalEnvelope = validate_bound_dynamic_program(
            ast_binding
        )
        self._ast_binding = ast_binding
        self._backend = backend
        self._used = False

    @property
    def safety_evidence(self) -> ReachablePhysicalEnvelope:
        return self._safety

    @staticmethod
    def _write(process: subprocess.Popen[str], message: dict[str, object]) -> None:
        if process.stdin is None:
            raise SharedInterpreterHostError(
                "shared interpreter input is unavailable"
            )
        encoded = json.dumps(
            message,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        if len(encoded.encode("utf-8")) > _MAX_PROTOCOL_BYTES:
            raise SharedInterpreterHostError(
                "shared interpreter protocol message is too large"
            )
        try:
            process.stdin.write(encoded + "\n")
            process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise SharedInterpreterHostError(
                "shared interpreter input failed"
            ) from exc

    @staticmethod
    def _read(pump: _LinePump) -> dict[str, object]:
        line = pump.read()
        if len(line.encode("utf-8")) > _MAX_PROTOCOL_BYTES:
            raise SharedInterpreterHostError(
                "shared interpreter protocol message is too large"
            )
        try:
            message = json.loads(line)
        except (TypeError, ValueError) as exc:
            raise SharedInterpreterHostError(
                "shared interpreter protocol is malformed"
            ) from exc
        if not isinstance(message, dict):
            raise SharedInterpreterHostError(
                "shared interpreter protocol is malformed"
            )
        return message

    @staticmethod
    def _terminate(process: subprocess.Popen[str]) -> None:
        if process.stdin is not None:
            try:
                process.stdin.close()
            except OSError:
                pass
        if process.poll() is None:
            try:
                process.kill()
            except OSError:
                pass
        try:
            process.wait(timeout=1.0)
        except (OSError, subprocess.TimeoutExpired):
            pass

    def _validated_args(self, method: str, args: list[object]) -> list[object]:
        expected = _METHOD_ARITY.get(method)
        if expected is None or len(args) != expected:
            raise SharedInterpreterHostError(
                "shared interpreter requested unsupported backend call"
            )
        if method == "land":
            return []
        if method == "takeoff":
            return [_finite_number(args[0], "takeoff height")]
        if method == "move":
            return [
                _exact_string(args[0], _MOVE_DIRECTIONS, "move direction"),
                _finite_number(args[1], "move distance"),
            ]
        if method == "vertical":
            return [
                _exact_string(args[0], _VERTICAL_DIRECTIONS, "vertical direction"),
                _finite_number(args[1], "vertical distance"),
            ]
        if method == "turn":
            return [_finite_number(args[0], "turn angle")]
        if method == "wait":
            return [_finite_number(args[0], "wait duration")]
        if method == "setSpeed":
            return [_finite_number(args[0], "horizontal speed")]
        if method == "setLight":
            return [_exact_string(args[0], _LIGHT_COLORS, "light color")]
        if method == "readRange":
            return [_exact_string(args[0], _RANGE_DIRECTIONS, "range direction")]
        raise SharedInterpreterHostError(
            "shared interpreter requested unsupported backend call"
        )

    def _dispatch(self, method: str, args: list[object]):
        validated = self._validated_args(method, args)
        target = getattr(self._backend, method, None)
        if not callable(target):
            raise SharedInterpreterHostError(
                "trusted physical backend method is unavailable"
            )
        try:
            value = target(*validated)
        except Exception as exc:
            raise SharedInterpreterHostError(
                "trusted physical backend call failed"
            ) from exc
        if method != "readRange":
            # Action/no-effect consumer return objects stay inside the Python TCB.
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise SharedInterpreterHostError(
                "physical range result must be finite non-authority data"
            )
        parsed = float(value)
        if not isfinite(parsed):
            raise SharedInterpreterHostError(
                "physical range result must be finite non-authority data"
            )
        return parsed

    def run(self) -> SharedInterpreterResult:
        if self._used:
            raise SharedInterpreterHostError("bound shared interpreter is one-shot")
        self._used = True
        if not _WORKER.is_file():
            raise SharedInterpreterHostError(
                "shared interpreter worker is unavailable"
            )
        try:
            process = subprocess.Popen(
                ["node", str(_WORKER)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                bufsize=1,
            )
        except (OSError, ValueError) as exc:
            raise SharedInterpreterHostError(
                "could not start shared interpreter"
            ) from exc
        if process.stdout is None:
            self._terminate(process)
            raise SharedInterpreterHostError(
                "shared interpreter output is unavailable"
            )

        pump = _LinePump(process.stdout)
        expected_call_id = 1
        try:
            self._write(
                process,
                {"op": "run-bound-program", "astBinding": self._ast_binding},
            )
            while True:
                message = self._read(pump)
                message_type = message.get("type")
                if message_type == "call":
                    if set(message) != {"type", "id", "method", "args"}:
                        raise SharedInterpreterHostError(
                            "shared interpreter call is malformed"
                        )
                    call_id = message["id"]
                    method = message["method"]
                    args = message["args"]
                    if (
                        not isinstance(call_id, int)
                        or isinstance(call_id, bool)
                        or call_id != expected_call_id
                        or not isinstance(method, str)
                        or not isinstance(args, list)
                    ):
                        raise SharedInterpreterHostError(
                            "shared interpreter call is malformed"
                        )
                    expected_call_id += 1
                    try:
                        value = self._dispatch(method, args)
                    except SharedInterpreterHostError:
                        self._write(
                            process,
                            {"type": "return", "id": call_id, "ok": False},
                        )
                        raise
                    self._write(
                        process,
                        {
                            "type": "return",
                            "id": call_id,
                            "ok": True,
                            "value": value,
                        },
                    )
                    continue

                if message_type != "done":
                    raise SharedInterpreterHostError(
                        "shared interpreter protocol is malformed"
                    )
                if (
                    message.get("ok") is not True
                    or set(message) != {"type", "ok", "result"}
                ):
                    raise SharedInterpreterHostError(
                        "shared interpreter failed closed"
                    )
                result = message["result"]
                if (
                    not isinstance(result, dict)
                    or set(result) != {"remainingBudget", "variables"}
                ):
                    raise SharedInterpreterHostError(
                        "shared interpreter result is malformed"
                    )
                remaining = result["remainingBudget"]
                variables = result["variables"]
                if (
                    not isinstance(remaining, int)
                    or isinstance(remaining, bool)
                    or remaining < 0
                    or not isinstance(variables, dict)
                ):
                    raise SharedInterpreterHostError(
                        "shared interpreter result is malformed"
                    )
                try:
                    exit_code = process.wait(timeout=_PROTOCOL_IDLE_TIMEOUT_SECONDS)
                except subprocess.TimeoutExpired as exc:
                    raise SharedInterpreterHostError(
                        "shared interpreter did not terminate"
                    ) from exc
                if exit_code != 0:
                    raise SharedInterpreterHostError(
                        "shared interpreter exited unsuccessfully"
                    )
                return SharedInterpreterResult(remaining, dict(variables))
        finally:
            self._terminate(process)
