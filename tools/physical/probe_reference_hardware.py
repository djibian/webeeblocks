#!/usr/bin/env python3
"""Read-only Crazyradio/Crazyflie capability probe for WebeeBlocks P0b.

This tool deliberately exposes no flight, arming, setpoint or parameter-write
operation. It requires an explicit Crazyradio URI and reports only observed
platform/deck evidence plus conservative hardware-compatible capability facts.

Exact Crazyflie 2.1 identity is intentionally left unproven: the supported
cflib platform handshake establishes the Crazyflie family, not the exact
airframe model.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import sys
from typing import Callable, Mapping

PARAMETERS = (
    "firmware.revision0",
    "firmware.revision1",
    "firmware.modified",
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


def build_descriptor(protocol_version: object, values: Mapping[str, object]) -> dict[str, object]:
    """Build the P0 capability descriptor from already-read evidence only."""
    protocol = _parse_uint(protocol_version, "protocolVersion")
    parsed = {name: _parse_uint(values[name], name) for name in PARAMETERS}

    flow_present = parsed["deck.bcFlow2"] != 0
    multiranger_present = parsed["deck.bcMultiranger"] != 0
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
    if flow_present:
        hardware.append("flow-deck-v2")
        actions.extend(FLOW_ACTIONS)
        move_directions.extend(MOVE_DIRECTIONS)
        vertical_directions.extend(VERTICAL_DIRECTIONS)

    if multiranger_present:
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
            "model": None,
            "modelEvidence": "unproven",
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
            "exactAirframeModel": "unproven",
        },
    }


def probe_live(uri: str) -> dict[str, object]:
    """Connect to one explicitly named Crazyradio URI and read evidence only."""
    if not uri.startswith("radio://"):
        raise ProbeError("P0b requires an explicit Crazyradio radio:// URI")

    try:
        import cflib.crtp
        from cflib.crazyflie import Crazyflie
        from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
    except ImportError as exc:
        raise ProbeError("cflib is required for the live read-only probe") from exc

    cflib.crtp.init_drivers()
    try:
        cflib_version = importlib.metadata.version("cflib")
    except importlib.metadata.PackageNotFoundError:
        cflib_version = "unknown"

    try:
        with SyncCrazyflie(uri, cf=Crazyflie()) as scf:
            scf.wait_for_params()
            protocol_version = scf.cf.platform.get_protocol_version()
            values = _read_required_parameters(scf.cf.param.get_value)
    except ProbeError:
        raise
    except Exception as exc:
        raise ProbeError(f"Crazyradio/Crazyflie read-only probe failed: {exc}") from exc

    descriptor = build_descriptor(protocol_version, values)
    descriptor["evidence"]["cflibVersion"] = cflib_version
    return descriptor


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
