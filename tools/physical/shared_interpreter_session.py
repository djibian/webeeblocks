#!/usr/bin/env python3
"""Host-owned resumable adapter for the authoritative Runtime v2 interpreter.

This module does not implement WebeeBlocks expression or control-flow semantics.
It runs the existing CommonJS ``interpreter.js`` in a private Node subprocess and
turns only the backend calls reached by that interpreter into process-local
requests. The exact canonical teacher-bound AST remains the sole program input.

Range requests are resolved immediately through a trusted callback derived from
the exact expression path. Physical action requests are paused and exposed as an
opaque host-local claim whose semantics are re-derived from the exact bound AST;
the worker-supplied payload is only checked for agreement. A later physical-host
consumer may acknowledge that exact claim after its already-established
independent authority/completion chain succeeds. Nothing here emits cflib/CRTP,
changes the physical execution domain, or exposes browser/caller IPC.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from math import isfinite
from pathlib import Path
from queue import Empty, Queue
import subprocess
from threading import Thread
from typing import Callable

import physical_dynamic_preflight
import takeoff_command


class SharedInterpreterSessionError(RuntimeError):
    """Fail-closed error for the private shared-interpreter adapter."""


@dataclass(frozen=True, slots=True)
class SelectedPhysicalAction:
    """Non-authority description of one exact action selected by interpreter.js."""

    path: tuple[object, ...]
    kind: str
    statement: dict[str, object]


class _ActionClaim:
    __slots__ = ("action", "request_id")

    def __init__(self, action: SelectedPhysicalAction, request_id: int) -> None:
        self.action = action
        self.request_id = request_id


_EOF = object()
_ACTION_KINDS = frozenset(
    ("takeoff", "land", "move", "vertical", "turn", "wait", "set_speed", "set_light")
)


class SharedInterpreterSession:
    """One exact-AST interpreter execution owned entirely by the trusted host."""

    def __init__(
        self,
        ast_binding: str,
        read_range: Callable[[str], float],
        *,
        node_binary: str = "node",
        worker_path: Path | None = None,
        response_timeout_seconds: float = 2.0,
    ) -> None:
        if not isinstance(ast_binding, str) or not ast_binding.strip() or ast_binding != ast_binding.strip():
            raise SharedInterpreterSessionError("exact canonical ast binding is required")
        if not callable(read_range):
            raise SharedInterpreterSessionError("trusted range callback is required")
        if not isinstance(response_timeout_seconds, (int, float)) or isinstance(response_timeout_seconds, bool):
            raise SharedInterpreterSessionError("interpreter response timeout must be positive")
        timeout = float(response_timeout_seconds)
        if not isfinite(timeout) or timeout <= 0:
            raise SharedInterpreterSessionError("interpreter response timeout must be positive")

        try:
            parsed = takeoff_command._parse_ast_binding(ast_binding)
            envelope = physical_dynamic_preflight.validate_bound_dynamic_program(ast_binding)
        except Exception as exc:
            raise SharedInterpreterSessionError(
                "teacher-bound AST is not eligible for shared physical interpretation"
            ) from exc
        if envelope.ast_binding != ast_binding:
            raise SharedInterpreterSessionError("dynamic preflight changed exact ast binding identity")

        root = Path(__file__).resolve().parents[2]
        worker = worker_path or (Path(__file__).resolve().parent / "shared_interpreter_worker.js")
        if not isinstance(worker, Path):
            worker = Path(worker)
        if not worker.is_file():
            raise SharedInterpreterSessionError("trusted shared-interpreter worker is unavailable")

        self._ast_binding = ast_binding
        self._ast = parsed
        self._envelope = envelope
        self._read_range = read_range
        self._timeout = timeout
        self._events: Queue[object] = Queue()
        self._pending: _ActionClaim | None = None
        self._takeoff_acknowledged = False
        self._completed = False
        self._terminal_reason: str | None = None
        self._variables: dict[str, object] | None = None

        try:
            self._process = subprocess.Popen(
                [node_binary, str(worker)],
                cwd=str(root),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                bufsize=1,
            )
        except Exception as exc:
            raise SharedInterpreterSessionError("could not start trusted shared interpreter") from exc
        if self._process.stdin is None or self._process.stdout is None:
            self._terminate_process()
            raise SharedInterpreterSessionError("trusted shared interpreter pipes are unavailable")

        self._reader = Thread(target=self._read_worker, daemon=True)
        self._reader.start()
        try:
            self._send({"type": "start", "astBinding": ast_binding})
        except Exception:
            self._terminate_process()
            raise

    @property
    def ast_binding(self) -> str:
        return self._ast_binding

    @property
    def reachable_envelope(self) -> physical_dynamic_preflight.ReachablePhysicalEnvelope:
        return self._envelope

    @property
    def completed(self) -> bool:
        return self._completed

    @property
    def terminal(self) -> bool:
        return self._terminal_reason is not None

    @property
    def variables(self) -> dict[str, object] | None:
        return None if self._variables is None else dict(self._variables)

    def _read_worker(self) -> None:
        assert self._process.stdout is not None
        try:
            for line in self._process.stdout:
                self._events.put(line.rstrip("\n"))
        finally:
            self._events.put(_EOF)

    def _send(self, message: dict[str, object]) -> None:
        if self._terminal_reason is not None:
            raise SharedInterpreterSessionError(
                "shared interpreter session is terminal: " + self._terminal_reason
            )
        stdin = self._process.stdin
        if stdin is None or self._process.poll() is not None:
            self._poison("trusted shared interpreter process is unavailable")
        try:
            assert stdin is not None
            stdin.write(json.dumps(message, separators=(",", ":"), sort_keys=True) + "\n")
            stdin.flush()
        except Exception as exc:
            self._poison("trusted shared interpreter protocol write failed")
            raise SharedInterpreterSessionError(self._terminal_reason or "protocol write failed") from exc

    def _poison(self, reason: str) -> None:
        if self._terminal_reason is None:
            self._terminal_reason = reason

    def _next_event(self) -> dict[str, object]:
        if self._terminal_reason is not None:
            raise SharedInterpreterSessionError(
                "shared interpreter session is terminal: " + self._terminal_reason
            )
        try:
            raw = self._events.get(timeout=self._timeout)
        except Empty as exc:
            self._poison("trusted shared interpreter timed out")
            raise SharedInterpreterSessionError(self._terminal_reason) from exc
        if raw is _EOF:
            self._poison("trusted shared interpreter exited before completion")
            raise SharedInterpreterSessionError(self._terminal_reason)
        if not isinstance(raw, str):
            self._poison("trusted shared interpreter produced an invalid event")
            raise SharedInterpreterSessionError(self._terminal_reason)
        try:
            event = json.loads(raw)
        except json.JSONDecodeError as exc:
            self._poison("trusted shared interpreter emitted malformed JSON")
            raise SharedInterpreterSessionError(self._terminal_reason) from exc
        if not isinstance(event, dict):
            self._poison("trusted shared interpreter event is not an object")
            raise SharedInterpreterSessionError(self._terminal_reason)
        return event

    def _node_at_path(self, raw_path: object) -> tuple[tuple[object, ...], dict[str, object]]:
        if not isinstance(raw_path, list) or not raw_path or raw_path[0] != "program":
            raise SharedInterpreterSessionError("interpreter event path is outside the bound program")
        current: object = self._ast
        normalized: list[object] = []
        for component in raw_path:
            if isinstance(component, bool) or not isinstance(component, (str, int)):
                raise SharedInterpreterSessionError("interpreter event path is malformed")
            normalized.append(component)
            try:
                if isinstance(component, int):
                    if not isinstance(current, list) or component < 0 or component >= len(current):
                        raise KeyError(component)
                    current = current[component]
                else:
                    if not isinstance(current, dict) or component not in current:
                        raise KeyError(component)
                    current = current[component]
            except (KeyError, IndexError) as exc:
                raise SharedInterpreterSessionError(
                    "interpreter event path does not resolve in exact bound AST"
                ) from exc
        if not isinstance(current, dict):
            raise SharedInterpreterSessionError("interpreter event path does not resolve to a node")
        return tuple(normalized), current

    @staticmethod
    def _request_id(event: dict[str, object]) -> int:
        request_id = event.get("id")
        if isinstance(request_id, bool) or not isinstance(request_id, int) or request_id < 1:
            raise SharedInterpreterSessionError("interpreter backend request id is invalid")
        return request_id

    def _validate_exact_node(self, event: dict[str, object]) -> tuple[tuple[object, ...], dict[str, object]]:
        path, node = self._node_at_path(event.get("path"))
        if event.get("node") != node:
            raise SharedInterpreterSessionError(
                "interpreter backend request node differs from exact bound AST"
            )
        return path, node

    def _range_direction(self, event: dict[str, object]) -> str:
        self._request_id(event)
        _path, node = self._validate_exact_node(event)
        if set(node) != {"kind", "direction", "unit"} or node.get("kind") != "range" or node.get("unit") != "m":
            raise SharedInterpreterSessionError("interpreter range request is not an exact range expression")
        direction = node.get("direction")
        if not isinstance(direction, str) or event.get("direction") != direction:
            raise SharedInterpreterSessionError("interpreter range direction differs from exact bound AST")
        return direction

    def _action_claim(self, event: dict[str, object]) -> _ActionClaim:
        request_id = self._request_id(event)
        path, node = self._validate_exact_node(event)
        kind = node.get("kind")
        if not isinstance(kind, str) or kind not in _ACTION_KINDS or event.get("kind") != kind:
            raise SharedInterpreterSessionError("interpreter action differs from exact bound AST")
        protocol = {key: value for key, value in event.items() if key not in {"event", "id", "path", "node"}}
        expected = dict(node)
        if protocol != expected:
            raise SharedInterpreterSessionError(
                "interpreter action payload differs from exact bound AST"
            )
        action = SelectedPhysicalAction(path=path, kind=kind, statement=dict(node))
        return _ActionClaim(action, request_id)

    def _respond(self, request_id: int, *, value: object = None, include_value: bool = False) -> None:
        message: dict[str, object] = {"type": "response", "id": request_id, "ok": True}
        if include_value:
            message["value"] = value
        self._send(message)

    def acknowledge_bound_takeoff(self) -> SelectedPhysicalAction:
        """Advance only the exact first takeoff already completed by trusted activation."""
        if self._takeoff_acknowledged:
            raise SharedInterpreterSessionError("bound takeoff was already acknowledged")
        claim = self._wait_for_action()
        if claim is None:
            self._poison("shared interpreter completed before exact bound takeoff")
            raise SharedInterpreterSessionError(self._terminal_reason)
        if claim.action.kind != "takeoff" or claim.action.path != ("program", 0):
            self._poison("shared interpreter did not begin with exact bound takeoff")
            raise SharedInterpreterSessionError(self._terminal_reason)
        self._respond(claim.request_id)
        self._pending = None
        self._takeoff_acknowledged = True
        return claim.action

    def _wait_for_action(self) -> _ActionClaim | None:
        if self._pending is not None:
            return self._pending
        while True:
            event = self._next_event()
            event_type = event.get("event")
            try:
                if event_type == "range":
                    direction = self._range_direction(event)
                    value = self._read_range(direction)
                    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(float(value)):
                        raise SharedInterpreterSessionError(
                            "trusted range callback returned a non-finite numeric value"
                        )
                    self._respond(self._request_id(event), value=float(value), include_value=True)
                    continue
                if event_type == "action":
                    claim = self._action_claim(event)
                    self._pending = claim
                    return claim
                if event_type == "done":
                    variables = event.get("variables")
                    remaining = event.get("remainingBudget")
                    if not isinstance(variables, dict) or isinstance(remaining, bool) or not isinstance(remaining, int):
                        raise SharedInterpreterSessionError("shared interpreter completion is malformed")
                    self._variables = dict(variables)
                    self._completed = True
                    return None
                if event_type == "error" and isinstance(event.get("error"), str):
                    raise SharedInterpreterSessionError("shared interpreter failed: " + event["error"])
                raise SharedInterpreterSessionError("shared interpreter emitted an unsupported event")
            except Exception as exc:
                if isinstance(exc, SharedInterpreterSessionError):
                    self._poison(str(exc))
                    raise
                self._poison("trusted shared interpreter collaborator failed")
                raise SharedInterpreterSessionError(self._terminal_reason) from exc

    def next_inflight_action(self) -> SelectedPhysicalAction | None:
        """Resolve private sensor/control flow and pause at the next exact action."""
        if not self._takeoff_acknowledged:
            raise SharedInterpreterSessionError("exact completed takeoff must be acknowledged first")
        if self._completed:
            return None
        claim = self._wait_for_action()
        if claim is None:
            return None
        if claim.action.kind == "takeoff":
            self._poison("nested or replayed takeoff reached physical interpreter")
            raise SharedInterpreterSessionError(self._terminal_reason)
        return claim.action

    def acknowledge_action(self, action: SelectedPhysicalAction) -> None:
        """Resume only after the exact selected action definitively completed elsewhere."""
        claim = self._pending
        if claim is None or action is not claim.action:
            raise SharedInterpreterSessionError("exact pending interpreter action claim is required")
        self._respond(claim.request_id)
        self._pending = None

    def reject_action_terminal(self, action: SelectedPhysicalAction, reason: str) -> None:
        claim = self._pending
        if claim is None or action is not claim.action:
            raise SharedInterpreterSessionError("exact pending interpreter action claim is required")
        if not isinstance(reason, str) or not reason.strip():
            raise SharedInterpreterSessionError("terminal action rejection reason is required")
        try:
            self._send({"type": "response", "id": claim.request_id, "ok": False, "error": reason.strip()})
        finally:
            self._pending = None
            self._poison("selected physical action failed or became ambiguous")

    def _terminate_process(self) -> None:
        process = getattr(self, "_process", None)
        if process is None:
            return
        if process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=0.5)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass

    def close(self) -> None:
        self._terminate_process()
