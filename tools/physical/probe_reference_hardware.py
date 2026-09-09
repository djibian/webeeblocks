#!/usr/bin/env python3
"""Read-only Crazyradio/Crazyflie capability probe for WebeeBlocks P0b.

This tool deliberately exposes no flight, arming, setpoint or parameter-write
operation. It requires an explicit Crazyradio URI and reports only observed
platform/deck evidence plus conservative hardware-compatible capability facts.

Exact Crazyflie 2.1 identity is established only by the firmware's read-only
CRTP Platform "Get device type name" response. Connection success alone never
asserts the exact airframe model.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import secrets
import sys
from threading import Event, Lock
from typing import Callable, Mapping

PARAMETERS = (
    "firmware.revision0",
    "firmware.revision1",
    "firmware.modified",
    "system.selftestPassed",
    "deck.bcFlow2",
    "deck.bcMultiranger",
    "deck.bcColorLedBot",
    "deckTest.bcColorLedBot",
)

FLOW_ACTIONS = (
    "takeoff",
    "move",
    "vertical",
    "turn",
    "wait",
    "set_speed",
    "land",
)
MOVE_DIRECTIONS = ("forward", "back", "left", "right")
VERTICAL_DIRECTIONS = ("up", "down")
MULTIRANGER_DIRECTIONS = ("front", "back", "left", "right", "up")
VERSION_CHANNEL = 1
VERSION_GET_DEVICE_TYPE_NAME = 2
EXACT_DEVICE_TYPE_NAME = "Crazyflie 2.1"
EXACT_AIRFRAME_MODEL = "crazyflie-2.1"


class ProbeError(RuntimeError):
    """Fail-closed error for unavailable or malformed physical evidence."""


def _parse_uint(value: object, name: str) -> int:
    text = str(value).strip()
    try:
        parsed = int(text, 0)
    except (TypeError, ValueError) as exc:
        raise ProbeError(f"{name} is not an integer parameter value: {text!r}") from exc
    if parsed < 0:
        raise ProbeError(f"{name} must be non-negative")
    return parsed


def _read_required_parameters(get_value: Callable[[str], object]) -> dict[str, object]:
    values: dict[str, object] = {}
    for name in PARAMETERS:
        try:
            value = get_value(name)
        except Exception as exc:
            raise ProbeError(f"required read-only parameter unavailable: {name}") from exc
        if value is None:
            raise ProbeError(f"required read-only parameter unavailable: {name}")
        values[name] = value
    return values




def _normalize_device_type_name(value: object) -> str:
    if not isinstance(value, str):
        raise ProbeError("device type name is not text")
    # Accept an optional trailing C-string terminator defensively, while
    # rejecting embedded NUL bytes instead of normalizing ambiguous evidence.
    name = value.rstrip("\x00").strip()
    if not name:
        raise ProbeError("device type name is empty")
    if "\x00" in name:
        raise ProbeError("device type name contains embedded NUL")
    return name


def _read_device_type_name(
    cf: object,
    timeout_seconds: float = 2.0,
    crtp_types: tuple[object, object] | None = None,
) -> str:
    """Issue the documented read-only CRTP Platform device-type query."""
    if crtp_types is None:
        try:
            from cflib.crtp.crtpstack import CRTPPacket, CRTPPort
        except ImportError as exc:
            raise ProbeError("cflib CRTP packet support is unavailable") from exc
    else:
        CRTPPacket, CRTPPort = crtp_types

    done = Event()
    result: dict[str, object] = {}

    def callback(packet: object) -> None:
        try:
            if packet.channel != VERSION_CHANNEL:
                return
            data = bytes(packet.data)
            if not data or data[0] != VERSION_GET_DEVICE_TYPE_NAME:
                return
            result["name"] = data[1:].decode("utf-8")
        except Exception as exc:
            result["error"] = exc
        finally:
            if "name" in result or "error" in result:
                done.set()

    cf.add_port_callback(CRTPPort.PLATFORM, callback)
    try:
        packet = CRTPPacket()
        packet.set_header(CRTPPort.PLATFORM, VERSION_CHANNEL)
        packet.data = (VERSION_GET_DEVICE_TYPE_NAME,)
        cf.send_packet(packet)
        if not done.wait(timeout_seconds):
            raise ProbeError("device type query timed out")
    finally:
        cf.remove_port_callback(CRTPPort.PLATFORM, callback)

    if "error" in result:
        raise ProbeError(f"malformed device type response: {result['error']}")
    return _normalize_device_type_name(result.get("name"))


def build_descriptor(
    protocol_version: object,
    values: Mapping[str, object],
    device_type_name: object | None = None,
) -> dict[str, object]:
    """Build the P0 capability descriptor from already-read evidence only."""
    protocol = _parse_uint(protocol_version, "protocolVersion")
    parsed = {name: _parse_uint(values[name], name) for name in PARAMETERS}
    device_type = None if device_type_name is None else _normalize_device_type_name(device_type_name)
    exact_model_verified = device_type == EXACT_DEVICE_TYPE_NAME

    system_selftest_passed = parsed["system.selftestPassed"] == 1
    flow_present = parsed["deck.bcFlow2"] != 0
    multiranger_present = parsed["deck.bcMultiranger"] != 0
    flow_healthy = flow_present and system_selftest_passed
    multiranger_healthy = multiranger_present and system_selftest_passed
    color_present = parsed["deck.bcColorLedBot"] != 0
    color_test_mask = parsed["deckTest.bcColorLedBot"]
    color_healthy = color_present and color_test_mask == 0

    hardware: list[str] = []
    actions: list[str] = []
    move_directions: list[str] = []
    vertical_directions: list[str] = []
    range_directions: list[str] = []

    # WebeeBlocks physical movement semantics require the Flow Deck path.
    # This is hardware compatibility evidence only; executionAuthority stays false.
    if flow_healthy:
        hardware.append("flow-deck-v2")
        actions.extend(FLOW_ACTIONS)
        move_directions.extend(MOVE_DIRECTIONS)
        vertical_directions.extend(VERTICAL_DIRECTIONS)

    if multiranger_healthy:
        hardware.append("multi-ranger-deck")
        range_directions.extend(MULTIRANGER_DIRECTIONS)

    if color_healthy:
        hardware.append("color-led-deck")
        actions.append("set_light")

    return {
        "transport": "crazyradio",
        "connected": True,
        "executionAuthority": False,
        "identity": {
            "family": "crazyflie",
            "model": EXACT_AIRFRAME_MODEL if exact_model_verified else None,
            "modelEvidence": "verified" if exact_model_verified else "unproven",
        },
        "hardware": hardware,
        "capabilities": {
            "actions": actions,
            "rangeDirections": range_directions,
            "moveDirections": move_directions,
            "verticalDirections": vertical_directions,
        },
        "evidence": {
            "source": "cflib-platform-and-read-only-parameters",
            "protocolVersion": protocol,
            "systemSelfTestPassed": system_selftest_passed,
            "firmware": {
                "revision0": parsed["firmware.revision0"],
                "revision1": parsed["firmware.revision1"],
                "modified": parsed["firmware.modified"] != 0,
            },
            "decks": {
                "flowDeckV2": flow_present,
                "multiRanger": multiranger_present,
                "colorLedBottom": {
                    "present": color_present,
                    "selfTestMask": color_test_mask,
                    "healthy": color_healthy,
                },
            },
            "deviceTypeName": device_type,
            "exactAirframeModel": EXACT_AIRFRAME_MODEL if exact_model_verified else "unproven",
        },
    }


def _read_connected_descriptor(cf: object) -> dict[str, object]:
    """Read one truthful capability descriptor from an already-live link."""
    protocol_version = cf.platform.get_protocol_version()
    device_type_name = _read_device_type_name(cf)
    values = _read_required_parameters(cf.param.get_value)
    return build_descriptor(protocol_version, values, device_type_name)


def _installed_cflib_version() -> str:
    try:
        return importlib.metadata.version("cflib")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


class ReadOnlyCapabilitySession:
    """Persistent non-authority capability adapter for one live Crazyflie link.

    The opaque epoch is created only after a successful live connection and is
    invalidated by the Crazyflie disconnected callback. Reopening creates a new
    epoch. Capability reads are bracketed by that epoch and never cache the
    descriptor, so a later preflight observes the current descriptor fields from
    the same still-live session.

    This adapter deliberately exposes no flight, arming, setpoint or parameter
    write operation. Closing the underlying cflib link retains cflib's documented
    safety-zero close-path behavior; that transport qualification is not execution
    authority.
    """

    def __init__(
        self,
        uri: str,
        *,
        scf_factory: Callable[[str], object] | None = None,
        driver_init: Callable[[], None] | None = None,
        epoch_factory: Callable[[], str] | None = None,
        cflib_version_reader: Callable[[], str] | None = None,
        descriptor_reader: Callable[[object], dict[str, object]] | None = None,
    ) -> None:
        if not uri.startswith("radio://"):
            raise ProbeError("P0b requires an explicit Crazyradio radio:// URI")
        self._uri = uri
        self._effect_preflight_production_backed = all(
            seam is None
            for seam in (
                scf_factory,
                driver_init,
                epoch_factory,
                cflib_version_reader,
                descriptor_reader,
            )
        )
        self._scf_factory = scf_factory
        self._driver_init = driver_init
        self._epoch_factory = epoch_factory or (lambda: secrets.token_hex(16))
        self._cflib_version_reader = cflib_version_reader or _installed_cflib_version
        self._descriptor_reader = descriptor_reader or _read_connected_descriptor
        self._drivers_initialized = False
        self._scf: object | None = None
        self._disconnect_callback: Callable[[str], None] | None = None
        self._connection_epoch: str | None = None
        self._cflib_version = "unknown"
        self._state_lock = Lock()

    def _initialize_drivers(self) -> None:
        if self._drivers_initialized:
            return
        if self._driver_init is not None:
            self._driver_init()
        elif self._scf_factory is None:
            try:
                import cflib.crtp
            except ImportError as exc:
                raise ProbeError("cflib is required for the live read-only probe") from exc
            cflib.crtp.init_drivers()
        self._drivers_initialized = True

    def _new_scf(self) -> object:
        if self._scf_factory is not None:
            return self._scf_factory(self._uri)
        try:
            from cflib.crazyflie import Crazyflie
            from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
        except ImportError as exc:
            raise ProbeError("cflib is required for the live read-only probe") from exc
        return SyncCrazyflie(self._uri, cf=Crazyflie())

    def _invalidate(self, expected_scf: object) -> None:
        with self._state_lock:
            if self._scf is expected_scf:
                self._connection_epoch = None

    def _discard_stale_session(self) -> None:
        with self._state_lock:
            scf = self._scf
            callback = self._disconnect_callback
            if scf is None:
                return
            if scf.is_link_open():
                raise ProbeError("read-only capability session is already connected")
            self._scf = None
            self._disconnect_callback = None
            self._connection_epoch = None
        if callback is not None:
            try:
                scf.cf.disconnected.remove_callback(callback)
            except ValueError:
                pass

    def open(self) -> None:
        self._discard_stale_session()
        self._initialize_drivers()
        scf = self._new_scf()
        try:
            scf.open_link()
            scf.wait_for_params()
            if not scf.is_link_open():
                raise ProbeError("Crazyflie connection closed during session setup")
            epoch = self._epoch_factory()
            if not isinstance(epoch, str) or not epoch.strip():
                raise ProbeError("connection epoch factory returned an invalid epoch")
            epoch = epoch.strip()

            def disconnected(_uri: str) -> None:
                self._invalidate(scf)

            with self._state_lock:
                self._scf = scf
                self._disconnect_callback = disconnected
                self._connection_epoch = epoch
                self._cflib_version = self._cflib_version_reader()

            scf.cf.disconnected.add_callback(disconnected)
            if not scf.is_link_open():
                self._invalidate(scf)
                raise ProbeError("Crazyflie connection closed during session setup")
        except ProbeError:
            self._cleanup_failed_open(scf)
            raise
        except Exception as exc:
            self._cleanup_failed_open(scf)
            raise ProbeError(f"Crazyradio/Crazyflie read-only session failed: {exc}") from exc

    def _cleanup_failed_open(self, scf: object) -> None:
        with self._state_lock:
            callback = self._disconnect_callback if self._scf is scf else None
            if self._scf is scf:
                self._scf = None
                self._disconnect_callback = None
                self._connection_epoch = None
        if callback is not None:
            try:
                scf.cf.disconnected.remove_callback(callback)
            except ValueError:
                pass
        try:
            if scf.is_link_open():
                scf.close_link()
        except Exception:
            pass

    @property
    def effect_preflight_production_backed(self) -> bool:
        """True only for the uninjected live-session construction path."""
        return self._effect_preflight_production_backed

    def read_connection_epoch(self) -> str:
        with self._state_lock:
            scf = self._scf
            epoch = self._connection_epoch
        if scf is None or epoch is None or not scf.is_link_open():
            raise ProbeError("Crazyflie connection is not established for capability preflight")
        return epoch

    def read_capabilities(self) -> dict[str, object]:
        before = self.read_connection_epoch()
        with self._state_lock:
            scf = self._scf
            cflib_version = self._cflib_version
        if scf is None:
            raise ProbeError("Crazyflie connection is not established for capability preflight")
        try:
            descriptor = self._descriptor_reader(scf.cf)
        except ProbeError:
            raise
        except Exception as exc:
            raise ProbeError(f"Crazyflie capability read failed: {exc}") from exc
        after = self.read_connection_epoch()
        if after != before:
            raise ProbeError("Crazyflie connection changed while capabilities were read")
        descriptor["evidence"]["cflibVersion"] = cflib_version
        return descriptor

    def close(self) -> None:
        with self._state_lock:
            scf = self._scf
            callback = self._disconnect_callback
            self._scf = None
            self._disconnect_callback = None
            self._connection_epoch = None
        if scf is None:
            return
        if callback is not None:
            try:
                scf.cf.disconnected.remove_callback(callback)
            except ValueError:
                pass
        try:
            if scf.is_link_open():
                scf.close_link()
        except Exception as exc:
            raise ProbeError(f"Crazyradio/Crazyflie read-only session close failed: {exc}") from exc

    def __enter__(self) -> "ReadOnlyCapabilitySession":
        self.open()
        return self

    def __exit__(self, _exc_type, _exc_val, _exc_tb) -> None:
        self.close()


def probe_live(uri: str) -> dict[str, object]:
    """Connect to one explicitly named Crazyradio URI and read evidence only."""
    try:
        with ReadOnlyCapabilitySession(uri) as session:
            return session.read_capabilities()
    except ProbeError:
        raise
    except Exception as exc:
        raise ProbeError(f"Crazyradio/Crazyflie read-only probe failed: {exc}") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only WebeeBlocks Crazyradio/Crazyflie capability probe"
    )
    parser.add_argument(
        "--uri",
        required=True,
        help="Exact Crazyradio URI, for example radio://0/80/2M/E7E7E7E7E7",
    )
    parser.add_argument("--pretty", action="store_true", help="pretty-print JSON")
    args = parser.parse_args(argv)

    try:
        descriptor = probe_live(args.uri)
    except ProbeError as exc:
        print(f"PROBE_FAILED: {exc}", file=sys.stderr)
        return 2

    json.dump(
        descriptor,
        sys.stdout,
        ensure_ascii=False,
        sort_keys=True,
        indent=2 if args.pretty else None,
    )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
