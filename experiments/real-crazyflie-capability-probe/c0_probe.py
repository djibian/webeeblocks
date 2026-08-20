#!/usr/bin/env python3
"""C0 Crazyflie capability probe: connection + telemetry only, never motor control."""

from __future__ import annotations

import argparse
import json
import math
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Protocol, Sequence

RANGE_KEYS = ("range.front", "range.back", "range.left", "range.right", "range.up")
FLOW_KEYS = ("motion.deltaX", "motion.deltaY", "range.zrange")
STATE_KEYS = ("stateEstimate.x", "stateEstimate.y", "stateEstimate.z")
REQUIRED_DECKS = ("bcFlow2", "bcMultiranger")

# Strings only: this is a display-only mapping. No commander module is imported or called.
MISSION_MAPPING = {
    "TAKEOFF": "cflib.positioning.motion_commander:take_off(height_m)",
    "FORWARD": "cflib.positioning.motion_commander:forward(distance_m)",
    "LEFT": "cflib.positioning.motion_commander:left(distance_m)",
    "RIGHT": "cflib.positioning.motion_commander:right(distance_m)",
    "UP": "cflib.positioning.motion_commander:up(distance_m)",
    "DOWN": "cflib.positioning.motion_commander:down(distance_m)",
    "TURN": "cflib.positioning.motion_commander:turn_left_or_right(angle_deg)",
    "LAND": "cflib.positioning.motion_commander:land()",
}


class ProbeError(RuntimeError):
    pass


class ReadOnlyPort(Protocol):
    def init_drivers(self) -> None: ...
    def scan_uris(self) -> Sequence[str]: ...
    def connect(self, uri: str, timeout_s: float) -> None: ...
    def deck_names(self) -> Sequence[str]: ...
    def read_telemetry(self, timeout_s: float) -> Dict[str, float]: ...
    def close(self) -> None: ...


@dataclass(frozen=True)
class ProbeReport:
    mode: str
    uri: str
    connected: bool
    decks: List[str]
    flow_v2_detected: bool
    multiranger_detected: bool
    telemetry: Dict[str, float]
    telemetry_complete: bool
    mission_mapping: List[Dict[str, Any]]
    physical_proof: bool


def normalize_deck_name(name: str) -> str:
    return name.strip().lower().replace("-", "")


def has_deck(deck_names: Iterable[str], expected: str) -> bool:
    target = normalize_deck_name(expected)
    return any(normalize_deck_name(name) == target for name in deck_names)


def compile_display_only_mapping(mission: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for index, command in enumerate(mission):
        op = str(command.get("op", "")).upper()
        if op not in MISSION_MAPPING:
            raise ProbeError(f"unsupported semantic command at {index}: {op!r}")
        result.append({"index": index, "semantic": command, "potential_cflib": MISSION_MAPPING[op]})
    return result


def validate_telemetry(values: Dict[str, float]) -> bool:
    required = RANGE_KEYS + FLOW_KEYS + STATE_KEYS
    for key in required:
        if key not in values:
            return False
        value = values[key]
        if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            return False
    return True


def run_probe(
    port: ReadOnlyPort,
    *,
    uri: Optional[str],
    scan: bool,
    connection_timeout_s: float,
    telemetry_timeout_s: float,
    mission: Sequence[Dict[str, Any]],
    mode: str,
) -> ProbeReport:
    mapping = compile_display_only_mapping(mission)
    connected = False
    selected_uri = uri or ""
    try:
        port.init_drivers()
        if scan:
            uris = list(port.scan_uris())
            if not uris:
                raise ProbeError("no Crazyflie URI found")
            if uri and uri not in uris:
                raise ProbeError(f"requested URI not found by scan: {uri}")
            selected_uri = uri or uris[0]
        elif not selected_uri:
            raise ProbeError("provide --uri or --scan")

        port.connect(selected_uri, connection_timeout_s)
        connected = True
        decks = list(port.deck_names())
        flow = has_deck(decks, "bcFlow2") or any("bcflow" in normalize_deck_name(d) for d in decks)
        multiranger = has_deck(decks, "bcMultiranger") or any("multiranger" in normalize_deck_name(d) for d in decks)
        if not flow or not multiranger:
            missing = []
            if not flow:
                missing.append("Flow V2")
            if not multiranger:
                missing.append("Multi-ranger")
            raise ProbeError("required deck(s) not detected: " + ", ".join(missing))

        telemetry = port.read_telemetry(telemetry_timeout_s)
        complete = validate_telemetry(telemetry)
        if not complete:
            raise ProbeError("required read-only telemetry was not received completely")

        return ProbeReport(
            mode=mode,
            uri=selected_uri,
            connected=True,
            decks=decks,
            flow_v2_detected=flow,
            multiranger_detected=multiranger,
            telemetry={key: float(telemetry[key]) for key in RANGE_KEYS + FLOW_KEYS + STATE_KEYS},
            telemetry_complete=True,
            mission_mapping=mapping,
            physical_proof=(mode == "live"),
        )
    finally:
        # Closing a read-only link is required on every success/error path.
        port.close()


class MockReadOnlyPort:
    def __init__(self, *, uris=None, decks=None, telemetry=None, connect_error: Optional[Exception] = None):
        self.uris = list(uris or ["radio://0/80/2M/E7E7E7E7E7"])
        self.decks = list(decks or ["bcFlow2", "bcMultiranger"])
        self.telemetry = dict(telemetry or _mock_telemetry())
        self.connect_error = connect_error
        self.initialized = False
        self.connected = False
        self.closed = False
        self.actions: List[str] = []

    def init_drivers(self) -> None:
        self.initialized = True
        self.actions.append("init_drivers")

    def scan_uris(self) -> Sequence[str]:
        self.actions.append("scan")
        return self.uris

    def connect(self, uri: str, timeout_s: float) -> None:
        self.actions.append(f"connect:{uri}")
        if self.connect_error:
            raise self.connect_error
        self.connected = True

    def deck_names(self) -> Sequence[str]:
        self.actions.append("deck_names")
        return self.decks

    def read_telemetry(self, timeout_s: float) -> Dict[str, float]:
        self.actions.append("read_telemetry")
        return self.telemetry

    def close(self) -> None:
        self.actions.append("close")
        self.closed = True
        self.connected = False


def _mock_telemetry() -> Dict[str, float]:
    return {
        "range.front": 420.0,
        "range.back": 910.0,
        "range.left": 650.0,
        "range.right": 700.0,
        "range.up": 1200.0,
        "motion.deltaX": 2.0,
        "motion.deltaY": -1.0,
        "range.zrange": 310.0,
        "stateEstimate.x": 0.01,
        "stateEstimate.y": -0.02,
        "stateEstimate.z": 0.30,
    }


class CflibReadOnlyPort:
    """The only cflib adapter in C0. It exposes no commander/setpoint API."""

    def __init__(self, cache_dir: str = "./cache"):
        self.cache_dir = cache_dir
        self.cf = None
        self._connected_event = threading.Event()
        self._failure_event = threading.Event()
        self._failure_message = ""

    def init_drivers(self) -> None:
        import cflib.crtp
        cflib.crtp.init_drivers()

    def scan_uris(self) -> Sequence[str]:
        import cflib.crtp
        return [item[0] if isinstance(item, tuple) else item for item in cflib.crtp.scan_interfaces()]

    def _on_fully_connected(self, uri: str) -> None:
        self._connected_event.set()

    def _on_failure(self, uri: str, message: str) -> None:
        self._failure_message = f"{uri}: {message}"
        self._failure_event.set()
        self._connected_event.set()

    def connect(self, uri: str, timeout_s: float) -> None:
        from cflib.crazyflie import Crazyflie
        self.cf = Crazyflie(rw_cache=self.cache_dir)
        self.cf.fully_connected.add_callback(self._on_fully_connected)
        self.cf.connection_failed.add_callback(self._on_failure)
        self.cf.connection_lost.add_callback(self._on_failure)
        self.cf.open_link(uri)
        if not self._connected_event.wait(timeout_s):
            raise ProbeError(f"fully_connected timeout after {timeout_s:.1f}s")
        if self._failure_event.is_set():
            raise ProbeError("connection failed/lost: " + self._failure_message)

    def deck_names(self) -> Sequence[str]:
        if self.cf is None:
            raise ProbeError("not connected")
        from cflib.crazyflie.mem import MemoryElement
        from cflib.crazyflie.mem import deck_memory
        mems = self.cf.mem.get_mems(MemoryElement.TYPE_DECK_MEMORY)
        if not mems:
            raise ProbeError("no deck memory interface found")
        decks = deck_memory.SyncDeckMemoryManager(mems[0]).query_decks()
        return [deck.name for _, deck in sorted(decks.items())]

    def read_telemetry(self, timeout_s: float) -> Dict[str, float]:
        if self.cf is None:
            raise ProbeError("not connected")
        from cflib.crazyflie.log import LogConfig

        result: Dict[str, float] = {}
        done = threading.Event()
        configs = []

        range_flow = LogConfig(name="C0RangeFlow", period_in_ms=100)
        for key in RANGE_KEYS + FLOW_KEYS:
            range_flow.add_variable(key)
        state = LogConfig(name="C0State", period_in_ms=100)
        for key in STATE_KEYS:
            state.add_variable(key, "float")
        configs.extend([range_flow, state])

        def received(_ts, data, _conf):
            result.update(data)
            if all(key in result for key in RANGE_KEYS + FLOW_KEYS + STATE_KEYS):
                done.set()

        def error(_conf, message):
            self._failure_message = str(message)
            self._failure_event.set()
            done.set()

        try:
            for config in configs:
                config.data_received_cb.add_callback(received)
                config.error_cb.add_callback(error)
                self.cf.log.add_config(config)
                config.start()
            if not done.wait(timeout_s):
                raise ProbeError(f"telemetry timeout after {timeout_s:.1f}s")
            if self._failure_event.is_set():
                raise ProbeError("telemetry/link error: " + self._failure_message)
            return result
        finally:
            for config in configs:
                try:
                    config.stop()
                except Exception:
                    pass
                try:
                    config.delete()
                except Exception:
                    pass

    def close(self) -> None:
        if self.cf is not None:
            try:
                self.cf.close_link()
            finally:
                self.cf = None


DEFAULT_MISSION = [
    {"op": "TAKEOFF", "height_m": 0.5},
    {"op": "FORWARD", "distance_m": 0.5},
    {"op": "TURN", "angle_deg": 90},
    {"op": "LAND"},
]


def main() -> int:
    parser = argparse.ArgumentParser(description="WebeeBlocks C0 read-only Crazyflie capability probe")
    parser.add_argument("--live", action="store_true", help="connect to real hardware; still telemetry-only")
    parser.add_argument("--uri", help="explicit Crazyflie radio URI")
    parser.add_argument("--scan", action="store_true", help="scan for Crazyflie URIs")
    parser.add_argument("--connection-timeout", type=float, default=10.0)
    parser.add_argument("--telemetry-timeout", type=float, default=5.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    if args.live:
        port: ReadOnlyPort = CflibReadOnlyPort()
        mode = "live"
    else:
        port = MockReadOnlyPort()
        mode = "mock"
        if not args.uri and not args.scan:
            args.scan = True

    try:
        report = run_probe(
            port,
            uri=args.uri,
            scan=args.scan,
            connection_timeout_s=args.connection_timeout,
            telemetry_timeout_s=args.telemetry_timeout,
            mission=DEFAULT_MISSION,
            mode=mode,
        )
    except Exception as exc:
        print(json.dumps({"status": "ERROR", "mode": mode, "error": str(exc)}, indent=2))
        return 2

    payload = {"status": "OK", **asdict(report)}
    text = json.dumps(payload, indent=2, sort_keys=True)
    print(text)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
