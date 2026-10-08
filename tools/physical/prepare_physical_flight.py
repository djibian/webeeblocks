#!/usr/bin/env python3
"""One-shot props-off restoration of the pinned representative-flight binary.

Importing this module is effect-free. Installation is an explicit human-owned
preparation action; its record is evidence, never execution/teacher authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import time

FIRMWARE_SOURCE_SHA = "54f31e243a0b28b67efef5ba20dbb6d9890a5478"
FIRMWARE_FILENAME = "cf2-2026.08.bin"
FIRMWARE_SHA256 = "9b745fe76da30e071ba8e04e6a8535d1dbd747d7ce6ca72d2d3ccf8c18978298"
FIRMWARE_RELATIVE = "tools/physical/firmware/" + FIRMWARE_FILENAME
SCHEMA = "webeeblocks.physical-flight-preparation.v1"
URI_RE = re.compile(r"radio://[0-9]+/[0-9]+/(250K|1M|2M)(/[0-9A-Fa-f]+)?")
EXPECTED = {
    "firmware.revision0": ("uint32_t", 0x54F31E24),
    "firmware.revision1": ("uint16_t", 0x3A0B),
    "firmware.modified": ("uint8_t", 0),
    "stabilizer.estimator": ("uint8_t", 2),
    "stabilizer.controller": ("uint8_t", 1),
}


class FlightPreparationError(RuntimeError):
    pass


def firmware_provenance() -> dict[str, str]:
    return {"release": "2026.08", "source_sha": FIRMWARE_SOURCE_SHA,
            "filename": FIRMWARE_FILENAME, "sha256": FIRMWARE_SHA256}


def require_inputs(root: Path, uri: str) -> tuple[str, Path]:
    if not URI_RE.fullmatch(uri):
        raise FlightPreparationError("one explicit Crazyradio URI is required")
    source = (root / "SOURCE_SHA").read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"[0-9a-f]{40}", source):
        raise FlightPreparationError("exact package source SHA is unavailable")
    binary = root / FIRMWARE_RELATIVE
    if hashlib.sha256(binary.read_bytes()).hexdigest() != FIRMWARE_SHA256:
        raise FlightPreparationError("physical flight firmware binary digest mismatch")
    return source, binary


def write_once(path: Path, value: dict) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def check_readbacks(observed: object) -> None:
    if not isinstance(observed, dict) or set(observed) != set(EXPECTED):
        raise FlightPreparationError("flight parameter readbacks are incomplete")
    for name, (ctype, expected) in EXPECTED.items():
        row = observed[name]
        if (not isinstance(row, dict) or set(row) != {"ctype", "value", "raw"}
                or row["ctype"] != ctype or type(row["value"]) is not int
                or row["value"] != expected or not isinstance(row["raw"], str)):
            raise FlightPreparationError("flight parameter type/read-back mismatch: " + name)


def exception_chain(exc: BaseException) -> list[str]:
    result = []
    seen = set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        result.append(f"{type(exc).__name__}: {exc}")
        exc = exc.__cause__ or exc.__context__
    return result


def flash_exact_firmware(uri: str, binary: Path) -> None:
    # Use the pinned public STM32-only bootloader primitives. No Crazyflie
    # object is passed, so start_bootloader cannot call normal close_link().
    # Avoid flash_full's ignored reset result and any swallowed teardown error.
    import cflib.crtp
    from cflib.bootloader import Bootloader, Target
    cflib.crtp.init_drivers()
    bootloader = Bootloader(clink=uri)
    target = Target("cf2", "stm32", "fw", [], [])
    try:
        if bootloader.start_bootloader(warm_boot=True, cf=None) is not True:
            raise FlightPreparationError("warm bootloader connection is not established")
        bootloader.flash(str(binary), [target], cf=None,
                         enable_console_log=False, boot_delay=5.0)
        if bootloader.reset_to_firmware(boot_delay=5.0) is not True:
            raise FlightPreparationError("return to firmware is unproven after installation")
    finally:
        bootloader.close()


def live_install(uri: str, binary: Path, observations: dict) -> None:
    # Reuse the bounded fresh-read and one-shot
    # no-Commander connection helpers. No X3 parameter/reset routine is called.
    from prepare_x3_independent_capture import (
        open_live_crazyflie, CflibParamAdapter,
    )
    from x3_no_commander_link import close_link_without_commander
    from probe_reference_hardware import _parse_uint, _read_device_type_name

    flash_exact_firmware(uri, binary)
    cf = open_live_crazyflie(uri)
    try:
        observations["device_type"] = _read_device_type_name(cf)
        if observations["device_type"] != "Crazyflie 2.1":
            raise FlightPreparationError("post-flash exact Crazyflie 2.1 identity is unavailable")
        protocol = cf.platform.get_protocol_version()
        observations["protocol_raw"] = repr(protocol)
        if type(protocol) is not int or protocol != 12:
            raise FlightPreparationError("post-flash pinned firmware protocol mismatch")
        adapter = CflibParamAdapter(cf)
        observed = observations["readbacks"]
        for name in EXPECTED:
            ctype, _writable, _cached = adapter.describe(name)
            raw = adapter.read_fresh(name)
            observed[name] = {"ctype": ctype, "raw": repr(raw), "value": None}
            observed[name]["value"] = _parse_uint(raw, name)
        check_readbacks(observed)
    finally:
        close_link_without_commander(cf)


def prepare(root: Path, uri: str, output: Path, props_removed: bool, *, installer=live_install) -> dict:
    if props_removed is not True:
        raise FlightPreparationError("all four propellers must be removed before preparation")
    source, binary = require_inputs(root, uri)
    if output.resolve().is_relative_to(root.resolve()):
        raise FlightPreparationError("preparation evidence must be outside the manifest-covered package")
    output.mkdir(parents=True, exist_ok=False)
    start = {"schema": SCHEMA, "source_sha": source, "uri": uri,
             "firmware": firmware_provenance(), "props_removed": True,
             "execution_authority": False, "started_host_monotonic_s": time.monotonic()}
    write_once(output / "preparation-start.json", start)
    observations = {"readbacks": {}}
    error = None
    try:
        installer(uri, binary, observations)
        check_readbacks(observations["readbacks"])
    except BaseException as exc:
        error = exception_chain(exc)
        raise
    finally:
        # Failed/interrupted installation remains uncertain and is never retried.
        write_once(output / "preparation.json", {
            **start, "status": "PREPARED" if error is None else "FAILED",
            "observations": observations, "readbacks": observations["readbacks"], "error": error,
            "finished_host_monotonic_s": time.monotonic(),
            "binary_attestation": "local digest + installation result + reported source metadata; no remote binary attestation",
        })
    return json.loads((output / "preparation.json").read_text(encoding="utf-8"))


def verify_record(root: Path, uri: str, record: Path) -> dict:
    source, _binary = require_inputs(root, uri)
    value = json.loads(record.read_text(encoding="utf-8"))
    if (not isinstance(value, dict) or value.get("schema") != SCHEMA
            or value.get("status") != "PREPARED" or value.get("error") is not None
            or value.get("source_sha") != source or value.get("uri") != uri
            or value.get("firmware") != firmware_provenance()
            or value.get("props_removed") is not True
            or value.get("execution_authority") is not False):
        raise FlightPreparationError("physical flight preparation record is not applicable")
    observations = value.get("observations")
    if (not isinstance(observations, dict)
            or observations.get("device_type") != "Crazyflie 2.1"
            or observations.get("protocol_raw") != "12"
            or observations.get("readbacks") != value.get("readbacks")):
        raise FlightPreparationError("preparation identity/read-back evidence is inconsistent")
    check_readbacks(value.get("readbacks"))
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--uri", required=True)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--output", type=Path)
    choice.add_argument("--verify-record", type=Path)
    parser.add_argument("--props-removed", action="store_true")
    args = parser.parse_args()
    try:
        if args.verify_record:
            value = verify_record(args.root, args.uri, args.verify_record)
            print("PASS: exact physical flight preparation record verified without hardware")
            print("FLIGHT_PREPARATION_RECORD " + json.dumps(value, sort_keys=True, allow_nan=False))
        else:
            prepare(args.root, args.uri, args.output, args.props_removed)
            print("PREPARED: " + str(args.output / "preparation.json"))
        return 0
    except (Exception, KeyboardInterrupt) as exc:
        print("FLIGHT_PREPARATION_ERROR: " + str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
