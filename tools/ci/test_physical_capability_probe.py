#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
PROBE_PATH = ROOT / "tools" / "physical" / "probe_reference_hardware.py"
CONTRACT_PATH = ROOT / "plugins" / "robot_windows" / "blockly" / "webeeblocks" / "physical_capability_contract.js"

spec = importlib.util.spec_from_file_location("probe_reference_hardware", PROBE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("cannot load physical capability probe")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)

BASE_VALUES = {
    "firmware.revision0": "305419896",
    "firmware.revision1": "2596069104",
    "firmware.modified": "0",
    "system.selftestPassed": "1",
    "deck.bcFlow2": "1",
    "deck.bcMultiranger": "1",
    "deck.bcColorLedBot": "1",
    "deckTest.bcColorLedBot": "0",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def expect_probe_error(callable_, pattern: str) -> None:
    try:
        callable_()
    except probe.ProbeError as exc:
        require(pattern in str(exc), f"expected {pattern!r} in {exc!r}")
        return
    raise AssertionError(f"expected ProbeError containing {pattern!r}")


def main() -> int:
    descriptor = probe.build_descriptor("11", BASE_VALUES)

    require(descriptor["transport"] == "crazyradio", "transport")
    require(descriptor["connected"] is True, "connected")
    require(descriptor["executionAuthority"] is False, "execution authority")
    require(
        descriptor["identity"]
        == {"family": "crazyflie", "model": None, "modelEvidence": "unproven"},
        "exact airframe must remain unproven",
    )

    verified_descriptor = probe.build_descriptor("11", BASE_VALUES, "Crazyflie 2.1")
    require(
        verified_descriptor["identity"]
        == {
            "family": "crazyflie",
            "model": "crazyflie-2.1",
            "modelEvidence": "verified",
        },
        "Crazyflie 2.1 device-type-name evidence must verify the exact airframe",
    )
    require(
        verified_descriptor["evidence"]["deviceTypeName"] == "Crazyflie 2.1"
        and verified_descriptor["evidence"]["exactAirframeModel"] == "crazyflie-2.1",
        "exact device-type evidence must be preserved",
    )

    other_descriptor = probe.build_descriptor("11", BASE_VALUES, "Crazyflie 2.1 Brushless")
    require(
        other_descriptor["identity"]
        == {"family": "crazyflie", "model": None, "modelEvidence": "unproven"},
        "non-reference device type name must not satisfy the exact-airframe claim",
    )
    require(
        other_descriptor["evidence"]["deviceTypeName"] == "Crazyflie 2.1 Brushless",
        "incompatible observed device type must remain visible as evidence",
    )

    expect_probe_error(
        lambda: probe.build_descriptor("11", BASE_VALUES, ""),
        "device type name is empty",
    )
    require(
        descriptor["hardware"]
        == ["flow-deck-v2", "multi-ranger-deck", "color-led-deck"],
        "reference deck evidence",
    )
    require(
        descriptor["capabilities"]["rangeDirections"]
        == ["front", "back", "left", "right", "up"],
        "Multi-ranger directions",
    )
    require(
        descriptor["capabilities"]["moveDirections"]
        == ["forward", "back", "left", "right"],
        "Flow movement directions",
    )
    require(
        descriptor["capabilities"]["verticalDirections"] == ["up", "down"],
        "Flow vertical directions",
    )
    require("set_light" in descriptor["capabilities"]["actions"], "healthy Color LED action fact")
    require(
        descriptor["evidence"]["decks"]["colorLedBottom"]
        == {"present": True, "selfTestMask": 0, "healthy": True},
        "Color LED self-test evidence",
    )

    color_failed = dict(BASE_VALUES)
    color_failed["deckTest.bcColorLedBot"] = "4"
    failed_descriptor = probe.build_descriptor(11, color_failed)
    require("color-led-deck" not in failed_descriptor["hardware"], "failed LED deck must not be advertised")
    require("set_light" not in failed_descriptor["capabilities"]["actions"], "failed LED action must not be advertised")
    require(
        failed_descriptor["evidence"]["decks"]["colorLedBottom"]["selfTestMask"] == 4,
        "failed LED self-test mask preserved",
    )

    selftest_failed = dict(BASE_VALUES)
    selftest_failed["system.selftestPassed"] = "0"
    selftest_failed_descriptor = probe.build_descriptor(11, selftest_failed)
    require(
        "flow-deck-v2" not in selftest_failed_descriptor["hardware"],
        "Flow deck must not be advertised when boot self-test failed",
    )
    require(
        "multi-ranger-deck" not in selftest_failed_descriptor["hardware"],
        "Multi-ranger must not be advertised when boot self-test failed",
    )
    require(
        selftest_failed_descriptor["capabilities"]["moveDirections"] == [],
        "movement must fail closed when boot self-test failed",
    )
    require(
        selftest_failed_descriptor["capabilities"]["verticalDirections"] == [],
        "vertical movement must fail closed when boot self-test failed",
    )
    require(
        selftest_failed_descriptor["capabilities"]["rangeDirections"] == [],
        "range must fail closed when boot self-test failed",
    )
    require(
        "set_light" in selftest_failed_descriptor["capabilities"]["actions"],
        "Color LED keeps its own explicit deck self-test evidence",
    )
    require(
        selftest_failed_descriptor["evidence"]["systemSelfTestPassed"] is False,
        "failed boot self-test evidence must be preserved",
    )
    require(
        selftest_failed_descriptor["evidence"]["decks"]["flowDeckV2"] is True
        and selftest_failed_descriptor["evidence"]["decks"]["multiRanger"] is True,
        "deck presence evidence must remain distinct from health",
    )

    malformed_selftest = dict(BASE_VALUES)
    malformed_selftest["system.selftestPassed"] = "not-an-int"
    expect_probe_error(
        lambda: probe.build_descriptor(11, malformed_selftest),
        "system.selftestPassed is not an integer",
    )

    no_flow = dict(BASE_VALUES)
    no_flow["deck.bcFlow2"] = "0"
    no_flow_descriptor = probe.build_descriptor(11, no_flow)
    require(no_flow_descriptor["capabilities"]["moveDirections"] == [], "movement must fail closed without Flow")
    require(no_flow_descriptor["capabilities"]["verticalDirections"] == [], "vertical must fail closed without Flow")
    require("takeoff" not in no_flow_descriptor["capabilities"]["actions"], "flight actions require Flow evidence")

    no_multiranger = dict(BASE_VALUES)
    no_multiranger["deck.bcMultiranger"] = "0"
    no_multiranger_descriptor = probe.build_descriptor(11, no_multiranger)
    require(no_multiranger_descriptor["capabilities"]["rangeDirections"] == [], "range must fail closed without Multi-ranger")

    expect_probe_error(
        lambda: probe.build_descriptor("not-an-int", BASE_VALUES),
        "protocolVersion is not an integer",
    )
    expect_probe_error(
        lambda: probe._read_required_parameters(
            lambda name: (_ for _ in ()).throw(KeyError(name))
        ),
        "required read-only parameter unavailable",
    )
    expect_probe_error(
        lambda: probe.probe_live("usb://not-crazyradio"),
        "explicit Crazyradio radio:// URI",
    )

    # Prove that the live-probe descriptor is accepted by the integrated P0a
    # structural normalizer while still remaining unusable for an exact 2.1
    # profile until distinct model evidence exists.
    node_script = (
        "const c=require(" + json.dumps(str(CONTRACT_PATH)) + ");"
        "let s='';process.stdin.on('data',d=>s+=d);"
        "process.stdin.on('end',()=>process.stdout.write(JSON.stringify(c.normalizeDescriptor(JSON.parse(s)))));"
    )
    normalized = subprocess.run(
        ["node", "-e", node_script],
        input=json.dumps(descriptor),
        text=True,
        capture_output=True,
        cwd=ROOT,
        check=False,
    )
    require(normalized.returncode == 0, f"JS descriptor normalization failed: {normalized.stderr}")
    normalized_descriptor = json.loads(normalized.stdout)
    require(normalized_descriptor["executionAuthority"] is False, "JS keeps non-authority invariant")
    require(normalized_descriptor["identity"]["modelEvidence"] == "unproven", "JS keeps identity boundary")
    require("evidence" not in normalized_descriptor, "P0a normalizer exposes only decision fields")

    verified_normalized = subprocess.run(
        ["node", "-e", node_script],
        input=json.dumps(verified_descriptor),
        text=True,
        capture_output=True,
        cwd=ROOT,
        check=False,
    )
    require(
        verified_normalized.returncode == 0,
        f"JS verified descriptor normalization failed: {verified_normalized.stderr}",
    )
    verified_normalized_descriptor = json.loads(verified_normalized.stdout)
    require(
        verified_normalized_descriptor["identity"]
        == {
            "family": "crazyflie",
            "model": "crazyflie-2.1",
            "modelEvidence": "verified",
        },
        "JS exact-airframe contract must retain verified Crazyflie 2.1 evidence",
    )

    source = PROBE_PATH.read_text(encoding="utf-8")
    for forbidden in (
        ".set_value(",
        "scan_interfaces",
        "commander.",
        "supervisor.",
        "send_arming_request",
        "send_setpoint",
        "send_hover_setpoint",
        "send_velocity_world_setpoint",
    ):
        require(forbidden not in source, f"read-only probe contains forbidden authority surface: {forbidden}")

    print("PASS cflib probe maps read-only platform/deck and exact-airframe evidence without execution authority")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
