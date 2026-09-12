#!/usr/bin/env python3
"""Trusted backend for one exact shared-interpreter physical run.

This module is the process-local composition seam between the already integrated
host-owned shared Runtime interpreter and the existing trusted physical
primitives. It does not expose caller IPC and it does not interpret Blockly or
AST control flow itself.

The causal takeoff has already been completed by ``ProductionTakeoffRunController``
before this backend is used. The interpreter's first ``takeoff(height)`` call is
therefore verification-only and emits no second command. The verification height
is derived here from the same exact canonical AST through the integrated dynamic
preflight; it is never accepted as an independent host semantic input. The
in-flight transport must expose the same AST-derived initial nominal altitude, so
takeoff verification and runtime landing cannot acquire split altitude roots.

Later action callbacks consume the already established trusted transports.
``readRange(direction)`` opens the exact ``FreshRangeObserver`` selected by the
shared interpreter only while the process-wide physical observation exclusion is
held, and requires current-program, teacher, watchdog and reconnect-sensitive
epoch provenance both before and after the fresh sample.

Sensor values remain finite non-authority data. This class never turns a range
value, branch result or worker message into physical authority; every selected
action still crosses the independently established downstream transport.
"""

from __future__ import annotations

from math import isfinite
from typing import Callable

from physical_dynamic_preflight import (
    DynamicPhysicalPreflightError,
    validate_bound_dynamic_program,
)
from physical_execution_domain import FLYING, INACTIVE
from range_observer import FreshRangeObserver, SUPPORTED_DIRECTIONS
from yaw_observer import FreshYawObserver


class DynamicPhysicalBackendError(RuntimeError):
    """Fail-closed error for shared-interpreter/live-physical composition."""


def _finite(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DynamicPhysicalBackendError(label + " must be finite")
    parsed = float(value)
    if not isfinite(parsed):
        raise DynamicPhysicalBackendError(label + " must be finite")
    return parsed


class TrustedDynamicPhysicalBackend:
    """Backend methods reached only by one bound shared Runtime interpreter."""

    def __init__(
        self,
        *,
        ast_binding: str,
        active_run: object,
        connection_epoch_reader: Callable[[], str],
        assert_current_program: Callable[[], object],
        inflight_transport: object,
        color_transport: object,
        timing_policy: object,
        execute_wait: Callable[[float], object],
        range_observer_factory: Callable[[str], object] | None = None,
        yaw_observer_factory: Callable[[], object] | None = None,
    ) -> None:
        if not isinstance(ast_binding, str) or not ast_binding.strip() or ast_binding != ast_binding.strip():
            raise DynamicPhysicalBackendError("exact canonical AST binding is required")
        try:
            safety = validate_bound_dynamic_program(ast_binding)
        except DynamicPhysicalPreflightError as exc:
            raise DynamicPhysicalBackendError(
                "exact dynamic physical preflight evidence is unavailable"
            ) from exc
        height = _finite(safety.initial_altitude_m, "preflight-proven takeoff height")
        if height <= 0:
            raise DynamicPhysicalBackendError("preflight-proven takeoff height must be positive")
        if safety.ast_binding != ast_binding:
            raise DynamicPhysicalBackendError("dynamic preflight changed the exact AST binding")
        if not callable(connection_epoch_reader):
            raise DynamicPhysicalBackendError("connection epoch reader is required")
        if not callable(assert_current_program):
            raise DynamicPhysicalBackendError("current-program assertion is required")
        if not callable(execute_wait):
            raise DynamicPhysicalBackendError("trusted exact-wait consumer is required")

        authorization = getattr(active_run, "teacher_authorization", None)
        binding = getattr(authorization, "binding", None)
        powered_session = getattr(active_run, "powered_session", None)
        epoch = getattr(powered_session, "connection_epoch", None)
        crazyflie = getattr(active_run, "crazyflie", None)
        execution_domain = getattr(active_run, "execution_domain", None)
        watchdog = getattr(active_run, "watchdog_guard", None)
        if (
            binding is None
            or getattr(binding, "ast_binding", None) != ast_binding
            or not isinstance(epoch, str)
            or not epoch.strip()
            or crazyflie is None
            or execution_domain is None
            or watchdog is None
        ):
            raise DynamicPhysicalBackendError(
                "active run does not match the exact bound interpreter program"
            )

        transport_initial = _finite(
            getattr(inflight_transport, "initial_nominal_altitude_m", None),
            "dynamic landing transport initial nominal altitude",
        )
        if transport_initial != height:
            raise DynamicPhysicalBackendError(
                "dynamic landing transport altitude differs from exact preflight-proven takeoff"
            )

        self._ast_binding = ast_binding
        self._initial_height = height
        self._active_run = active_run
        self._epoch_reader = connection_epoch_reader
        self._assert_current_program_callback = assert_current_program
        self._transport = inflight_transport
        self._color_transport = color_transport
        self._timing_policy = timing_policy
        self._execute_wait_callback = execute_wait
        self._bound_epoch = epoch
        self._takeoff_verified = False
        self._landed = False
        self._yaw_reader = None
        self._range_factory = range_observer_factory or self._default_range_observer
        self._yaw_factory = yaw_observer_factory or self._default_yaw_observer
        if not callable(self._range_factory) or not callable(self._yaw_factory):
            raise DynamicPhysicalBackendError("trusted physical observer factory is unavailable")

    @property
    def ast_binding(self) -> str:
        return self._ast_binding

    @property
    def bound_connection_epoch(self) -> str:
        return self._bound_epoch

    @property
    def initial_takeoff_height_m(self) -> float:
        """Exact preflight-derived height retained only as verification evidence."""
        return self._initial_height

    def _read_epoch(self) -> str:
        try:
            value = self._epoch_reader()
        except Exception as exc:
            raise DynamicPhysicalBackendError("live connection epoch is unavailable") from exc
        if value != self._bound_epoch:
            raise DynamicPhysicalBackendError("connection epoch changed during dynamic physical run")
        return value

    def _assert_live_flying(self) -> None:
        execution_domain = self._active_run.execution_domain
        if getattr(execution_domain, "phase", None) != FLYING:
            raise DynamicPhysicalBackendError(
                "dynamic physical operation requires causally established flying state"
            )
        assert_live = getattr(self._active_run.watchdog_guard, "assert_live", None)
        if not callable(assert_live):
            raise DynamicPhysicalBackendError("dynamic physical run has no live watchdog guard")
        assert_live()
        self._read_epoch()

        authorization = self._active_run.teacher_authorization
        binding = authorization.binding
        assert_effect_binding = getattr(authorization, "assert_effect_binding", None)
        if not callable(assert_effect_binding):
            raise DynamicPhysicalBackendError("dynamic physical run has no teacher binding assertion")
        assert_effect_binding(
            profile_id=binding.profile_id,
            ast_binding=self._ast_binding,
            connection_epoch=self._bound_epoch,
        )
        try:
            self._assert_current_program_callback()
        except Exception as exc:
            raise DynamicPhysicalBackendError(
                "fresh current-program assertion failed during dynamic physical run"
            ) from exc

    def _require_interpreter_started(self) -> None:
        if not self._takeoff_verified:
            raise DynamicPhysicalBackendError(
                "shared interpreter has not verified the completed bound takeoff"
            )
        if self._landed:
            raise DynamicPhysicalBackendError("dynamic physical run is already terminal")

    def _default_range_observer(self, direction: str) -> FreshRangeObserver:
        return FreshRangeObserver(
            self._active_run.crazyflie,
            self._epoch_reader,
            direction,
        )

    def _default_yaw_observer(self) -> FreshYawObserver:
        return FreshYawObserver(
            self._active_run.crazyflie,
            self._epoch_reader,
        )

    def _ensure_yaw_reader(self):
        if self._yaw_reader is not None:
            return self._yaw_reader
        try:
            reader = self._yaw_factory()
            reader.open()
        except Exception as exc:
            raise DynamicPhysicalBackendError(
                "fresh yaw observer could not be opened for dynamic physical run"
            ) from exc
        if (
            getattr(reader, "bound_crazyflie", None) is not self._active_run.crazyflie
            or getattr(reader, "bound_connection_epoch", None) != self._bound_epoch
        ):
            try:
                reader.close()
            except Exception:
                pass
            raise DynamicPhysicalBackendError(
                "fresh yaw observer does not match the active physical run"
            )
        self._yaw_reader = reader
        return reader

    def _accepted_flying(self, result: object, label: str) -> None:
        if getattr(result, "accepted", None) is not True:
            raise DynamicPhysicalBackendError(label + " was not positively acknowledged")
        if getattr(self._active_run.execution_domain, "phase", None) != FLYING:
            raise DynamicPhysicalBackendError(label + " did not causally return to flying")

    def takeoff(self, height_m: float) -> None:
        """Verify, but never repeat, the already completed causal takeoff."""
        if self._takeoff_verified:
            raise DynamicPhysicalBackendError("shared interpreter repeated bound takeoff")
        height = _finite(height_m, "shared interpreter takeoff height")
        if height != self._initial_height:
            raise DynamicPhysicalBackendError(
                "shared interpreter takeoff differs from preflight-proven bound height"
            )
        self._assert_live_flying()
        self._takeoff_verified = True

    def readRange(self, direction: str) -> float:
        """Return one fresh same-epoch range selected only by the bound interpreter."""
        self._require_interpreter_started()
        if not isinstance(direction, str) or direction not in SUPPORTED_DIRECTIONS:
            raise DynamicPhysicalBackendError("shared interpreter range direction is unsupported")

        execution_domain = self._active_run.execution_domain
        observation = execution_domain.observation_transaction(self._assert_live_flying)
        observer = None
        close_error = None
        try:
            with observation:
                try:
                    observer = self._range_factory(direction)
                    observer.open()
                    if (
                        getattr(observer, "bound_crazyflie", None) is not self._active_run.crazyflie
                        or getattr(observer, "bound_connection_epoch", None) != self._bound_epoch
                        or getattr(observer, "direction", None) != direction
                    ):
                        raise DynamicPhysicalBackendError(
                            "fresh range observer does not match interpreter-selected live demand"
                        )
                    sample = observer.read()
                    if (
                        getattr(sample, "connection_epoch", None) != self._bound_epoch
                        or getattr(sample, "direction", None) != direction
                    ):
                        raise DynamicPhysicalBackendError(
                            "fresh range sample does not match active run demand"
                        )
                    value = _finite(
                        getattr(sample, "range_m", None),
                        "fresh physical range",
                    )
                    self._assert_live_flying()
                finally:
                    if observer is not None:
                        try:
                            observer.close()
                        except Exception as exc:
                            close_error = exc
                if close_error is not None:
                    raise DynamicPhysicalBackendError(
                        "fresh range observer teardown is uncertain"
                    ) from close_error
                return value
        except DynamicPhysicalBackendError:
            raise
        except Exception as exc:
            raise DynamicPhysicalBackendError(
                "fresh physical range observation failed closed"
            ) from exc

    def move(self, direction: str, distance_m: float) -> None:
        self._require_interpreter_started()
        self._assert_live_flying()
        try:
            result = self._transport.send_horizontal_move(
                direction=direction,
                distance_m=distance_m,
                yaw_reader=self._ensure_yaw_reader(),
                timing_policy=self._timing_policy,
            )
        except Exception as exc:
            raise DynamicPhysicalBackendError("dynamic horizontal move failed closed") from exc
        self._accepted_flying(result, "dynamic horizontal move")

    def vertical(self, direction: str, distance_m: float) -> None:
        self._require_interpreter_started()
        self._assert_live_flying()
        try:
            result = self._transport.send_vertical_move(
                direction=direction,
                distance_m=distance_m,
                timing_policy=self._timing_policy,
            )
        except Exception as exc:
            raise DynamicPhysicalBackendError("dynamic vertical move failed closed") from exc
        self._accepted_flying(result, "dynamic vertical move")

    def turn(self, angle_deg: float) -> None:
        self._require_interpreter_started()
        self._assert_live_flying()
        try:
            result = self._transport.send_turn(
                angle_deg=angle_deg,
                timing_policy=self._timing_policy,
            )
        except Exception as exc:
            raise DynamicPhysicalBackendError("dynamic turn failed closed") from exc
        self._accepted_flying(result, "dynamic turn")

    def wait(self, seconds: float) -> None:
        self._require_interpreter_started()
        self._assert_live_flying()
        try:
            self._execute_wait_callback(seconds)
        except Exception as exc:
            raise DynamicPhysicalBackendError("dynamic exact wait failed closed") from exc
        self._assert_live_flying()

    def setSpeed(self, speed_m_s: float) -> None:
        self._require_interpreter_started()
        self._assert_live_flying()
        setter = getattr(self._timing_policy, "set_horizontal_speed", None)
        if not callable(setter):
            raise DynamicPhysicalBackendError("dynamic run timing policy is unavailable")
        try:
            setter(speed_m_s)
        except Exception as exc:
            raise DynamicPhysicalBackendError("dynamic set_speed failed closed") from exc
        self._assert_live_flying()

    def setLight(self, color: str) -> None:
        self._require_interpreter_started()
        self._assert_live_flying()
        try:
            result = self._color_transport.send_color(color=color)
        except Exception as exc:
            raise DynamicPhysicalBackendError("dynamic bottom Color LED effect failed closed") from exc
        self._accepted_flying(result, "dynamic bottom Color LED effect")

    def land(self) -> None:
        self._require_interpreter_started()
        self._assert_live_flying()
        try:
            result = self._transport.send_controlled_landing()
        except Exception as exc:
            raise DynamicPhysicalBackendError("dynamic terminal landing failed closed") from exc
        if getattr(result, "accepted", None) is not True:
            raise DynamicPhysicalBackendError(
                "dynamic terminal landing was not positively acknowledged"
            )
        if getattr(self._active_run.execution_domain, "phase", None) != INACTIVE:
            raise DynamicPhysicalBackendError(
                "dynamic terminal landing did not causally establish inactive"
            )
        self._landed = True

    def close(self) -> None:
        """Close process-local observers; teardown uncertainty remains an error."""
        reader = self._yaw_reader
        self._yaw_reader = None
        if reader is None:
            return
        try:
            reader.close()
        except Exception as exc:
            raise DynamicPhysicalBackendError(
                "fresh yaw observer teardown is uncertain"
            ) from exc
