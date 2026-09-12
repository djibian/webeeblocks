#!/usr/bin/env python3
"""Read the Crazyflie STM32 OTP platform string without firmware or parameter writes.

This is X3 provenance support only. It does not prove PCB net continuity, sensor
interrupt provenance, sensor producer timing, or any physical result. The normal
cflib link-close path may still emit its documented safety-zero commander setpoint.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import threading
import time
from typing import Iterable, Sequence


PINNED_CFLIB_COMMIT = "45fdb784c9d13074c42835f3b5ac1d12133bf873"
PINNED_FIRMWARE_COMMIT = "54f31e243a0b28b67efef5ba20dbb6d9890a5478"
OTP_BASE = 0x1FFF7800
OTP_BLOCK_COUNT = 16
OTP_BLOCK_LEN = 32
MAX_MEMORY_VARIABLES_PER_LOG_CONFIG = 5
LOG_PERIOD_MS = 10
REPEATED_SAMPLES = 3


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def chunks(values: Sequence[int], size: int) -> Iterable[Sequence[int]]:
    for start in range(0, len(values), size):
        yield values[start:start + size]


def otp_block_address(index: int) -> int:
    if not 0 <= index < OTP_BLOCK_COUNT:
        raise ValueError("OTP block index out of range")
    return OTP_BASE + index * OTP_BLOCK_LEN


def select_platform_block(start_bytes: bytes) -> tuple[int | None, str]:
    if len(start_bytes) != OTP_BLOCK_COUNT:
        raise ValueError("exactly 16 OTP block-start bytes are required")
    for index, value in enumerate(start_bytes):
        if value != 0:
            if value == 0xFF:
                return None, "firmware-fallback-first-nonzero-is-ff"
            return index, "selected-first-nonzero-block"
    return None, "firmware-fallback-no-nonzero-block"


def parse_platform_block(block: bytes) -> dict[str, object]:
    if len(block) != OTP_BLOCK_LEN:
        raise ValueError("exactly one 32-byte OTP block is required")
    raw_string = block.split(b"\0", 1)[0]
    try:
        platform_string = raw_string.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ValueError("selected OTP platform block is not ASCII") from exc

    device_type = None
    fields: list[str] = []
    if platform_string.startswith("0;"):
        fields = platform_string.split(";")
        if len(fields) >= 2 and fields[1]:
            device_type = fields[1]
    revision = next((field[2:] for field in fields[2:] if field.startswith("R=") and len(field) > 2), None)
    explicit_cf21 = device_type == "CF21"
    return {
        "platform_string": platform_string,
        "device_type": device_type,
        "revision_field": revision,
        "identity_verdict": "EXPLICIT_CF21" if explicit_cf21 else "UNPROVEN",
        "explicit_cf21": explicit_cf21,
    }


def _coerce_memory_sample(data: dict[str, object], names: Sequence[str]) -> tuple[int, ...]:
    sample: list[int] = []
    for name in names:
        value = data.get(name)
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 0xFF:
            raise ValueError(f"malformed raw-memory byte for {name}")
        sample.append(value)
    return tuple(sample)


def read_memory_group(cf: object, log_config_cls: object, *, name: str,
                      addresses: Sequence[int], timeout_s: float = 2.0) -> bytes:
    if not 1 <= len(addresses) <= MAX_MEMORY_VARIABLES_PER_LOG_CONFIG:
        raise ValueError("raw-memory log group must contain 1..5 variables")
    config = log_config_cls(name, LOG_PERIOD_MS)
    variable_names = [f"mem_{address:08x}" for address in addresses]
    for variable_name, address in zip(variable_names, addresses):
        config.add_memory(variable_name, "uint8_t", "uint8_t", address)

    samples: list[tuple[int, ...]] = []
    errors: list[str] = []
    done = threading.Event()

    def received(_timestamp, data, _config):
        if done.is_set():
            return
        try:
            sample = _coerce_memory_sample(data, variable_names)
        except ValueError as exc:
            errors.append(str(exc))
            done.set()
            return
        samples.append(sample)
        if len(samples) >= REPEATED_SAMPLES:
            done.set()

    def failed(_config, message):
        errors.append(f"log error: {message}")
        done.set()

    config.data_received_cb.add_callback(received)
    config.error_cb.add_callback(failed)
    cf.log.add_config(config)
    started = False
    try:
        config.start()
        started = True
        if not done.wait(timeout_s):
            raise RuntimeError("timed out waiting for repeated OTP observations")
        if errors:
            raise RuntimeError(errors[0])
        if len(samples) < REPEATED_SAMPLES:
            raise RuntimeError("insufficient repeated OTP observations")
        if any(sample != samples[0] for sample in samples[1:]):
            raise RuntimeError("OTP observations changed while being read")
        return bytes(samples[0])
    finally:
        if started:
            try:
                config.stop()
            except Exception as exc:
                raise RuntimeError(f"OTP log stop failed: {exc}") from exc


def read_memory(cf: object, log_config_cls: object, addresses: Sequence[int], *, prefix: str) -> bytes:
    values = bytearray()
    for index, group in enumerate(chunks(addresses, MAX_MEMORY_VARIABLES_PER_LOG_CONFIG)):
        values.extend(read_memory_group(
            cf, log_config_cls, name=f"{prefix}{index}", addresses=group,
        ))
    return bytes(values)


def observe_otp(cf: object, log_config_cls: object) -> dict[str, object]:
    start_addresses = [otp_block_address(index) for index in range(OTP_BLOCK_COUNT)]
    starts = read_memory(cf, log_config_cls, start_addresses, prefix="X3OtpS")
    selected_index, selection_reason = select_platform_block(starts)

    result: dict[str, object] = {
        "schema": "webeeblocks.x3.platform-otp-provenance.v1",
        "pinned_firmware_commit": PINNED_FIRMWARE_COMMIT,
        "pinned_cflib_commit_required": PINNED_CFLIB_COMMIT,
        "otp_base": f"0x{OTP_BASE:08x}",
        "otp_block_count": OTP_BLOCK_COUNT,
        "otp_block_len": OTP_BLOCK_LEN,
        "block_start_bytes_hex": starts.hex(),
        "selection_reason": selection_reason,
        "selected_block_index": selected_index,
        "selected_block_address": None,
        "selected_block_hex": None,
        "platform_string": None,
        "device_type": None,
        "revision_field": None,
        "identity_verdict": "UNPROVEN",
        "electrical_interrupt_source": "UNPROVEN",
        "physical_verdict": None,
        "observation_boundary": (
            "read-only STM32 OTP platform-string provenance only; does not prove PCB net continuity, "
            "BMI088 interrupt source, sensor timing, or firmware installation identity"
        ),
    }
    if selected_index is None:
        return result

    selected_address = otp_block_address(selected_index)
    block_addresses = [selected_address + offset for offset in range(OTP_BLOCK_LEN)]
    block = read_memory(cf, log_config_cls, block_addresses, prefix="X3OtpB")
    parsed = parse_platform_block(block)
    result.update(parsed)
    result["selected_block_address"] = f"0x{selected_address:08x}"
    result["selected_block_hex"] = block.hex()
    return result


def write_json_once(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def run_probe(uri: str, output: Path) -> int:
    if not re.fullmatch(r"radio://[0-9]+/[0-9]+/(250K|1M|2M)(/[0-9A-Fa-f]+)?", uri):
        raise ValueError("one explicit Crazyradio URI is required")

    import cflib
    import cflib.crtp
    from cflib.crazyflie import Crazyflie
    from cflib.crazyflie.log import LogConfig

    output.mkdir(parents=True, exist_ok=False)
    write_json_once(output / "probe-start.json", {
        "schema": "webeeblocks.x3.platform-otp-probe-start.v1",
        "uri": uri,
        "pinned_firmware_commit": PINNED_FIRMWARE_COMMIT,
        "pinned_cflib_commit_required": PINNED_CFLIB_COMMIT,
        "probe_script_sha256": file_digest(Path(__file__)),
        "cflib_module_sha256": file_digest(Path(cflib.__file__)),
        "runtime_boundary": "module fingerprints are not a complete cflib source/runtime attestation",
        "started_host_monotonic_s": time.monotonic(),
        "physical_verdict": None,
    })

    cflib.crtp.init_drivers()
    cf = Crazyflie(rw_cache=None)
    connected = threading.Event()
    failures: list[str] = []
    cf.fully_connected.add_callback(lambda *_: connected.set())
    cf.connection_failed.add_callback(lambda _, message: failures.append(f"connection failed: {message}"))
    cf.connection_lost.add_callback(lambda *_: failures.append("Crazyradio connection lost"))
    try:
        cf.open_link(uri)
        deadline = time.monotonic() + 30.0
        while not connected.is_set():
            if failures:
                raise RuntimeError(failures[0])
            if time.monotonic() >= deadline:
                raise RuntimeError("connection/TOC download did not complete within 30 s")
            time.sleep(0.02)
        if failures:
            raise RuntimeError(failures[0])
        result = observe_otp(cf, LogConfig)
        if failures:
            raise RuntimeError(failures[0])
        write_json_once(output / "platform-otp.json", result)
        return 0 if result["identity_verdict"] == "EXPLICIT_CF21" else 2
    finally:
        cf.close_link()


def describe() -> dict[str, object]:
    return {
        "schema": "webeeblocks.x3.platform-otp-probe-plan.v1",
        "pinned_firmware_commit": PINNED_FIRMWARE_COMMIT,
        "pinned_cflib_commit_required": PINNED_CFLIB_COMMIT,
        "otp_base": f"0x{OTP_BASE:08x}",
        "otp_blocks": OTP_BLOCK_COUNT,
        "otp_block_len": OTP_BLOCK_LEN,
        "max_memory_variables_per_log_config": MAX_MEMORY_VARIABLES_PER_LOG_CONFIG,
        "repeated_samples_per_group": REPEATED_SAMPLES,
        "writes": "none to firmware/parameters/memory; log-control packets only",
        "identity_acceptance": "explicit selected STM32 OTP device type CF21 only",
        "electrical_interrupt_source": "UNPROVEN",
        "physical_verdict": None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--describe", action="store_true")
    parser.add_argument("--uri")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.describe:
        print(json.dumps(describe(), indent=2, sort_keys=True))
        return 0
    if not args.uri or args.output is None:
        parser.error("probe requires --uri and a new --output directory")
    try:
        return run_probe(args.uri, args.output)
    except (OSError, ValueError, RuntimeError, ImportError) as exc:
        print(f"PROBE_ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
