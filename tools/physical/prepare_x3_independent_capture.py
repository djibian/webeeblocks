#!/usr/bin/env python3
"""Prepare the exact #251 X3 props-off state before read-only acquisition.

This is the only X3 characterization helper allowed to flash firmware, write
the four predeclared configuration parameters and perform the exact fresh UKF
reset already used by the valid #251 evidence. It never arms, invokes a
commander, sends motor setpoints, tunes from observations or retries a
scientific acquisition.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import tempfile
import threading
import time
from typing import Any

FIRMWARE_TARGET = "6562ad827bf0c8bf2c9b609edad36f3e15652133"
FIRMWARE_BIN_SHA256 = "67d71f2fc74c06001bb141ed6206b0d06df23497a48f498531c3aba192f0b738"
TEST_PROFILE = "x3-independent-props-off"
EXPECTED_CFLIB_COMMIT = "45fdb784c9d13074c42835f3b5ac1d12133bf873"
EXPECTED_CFLIB_TREE = "a78cf78d2b4aba51a0fa2b03de0260664b523401"
EXPECTED_CFLIB_SUBTREE = "750e850390753de14019f0e1f55d4fbc44317699"
SCHEMA = "webeeblocks.x3.preparation.v1"
PARAMETERS: dict[str, dict[str, Any]] = {
    "stabilizer.estimator": {"ctype": "uint8_t", "value": 3},
    "ukf.qualityGateTof": {"ctype": "float", "value": 20.0},
    "ukf.baroNoise": {"ctype": "float", "value": 6.25},
    "ukf.surfaceOffsetS3": {"ctype": "uint8_t", "value": 1},
}
RESET_PARAMETER = "ukf.resetEstimation"
RESET_CTYPE = "uint8_t"
RESET_ACTIVE = 1
RESET_INACTIVE = 0
RESET_HOLD_SECONDS = 0.25
RESET_SETTLE_SECONDS = 5.0
HEALTH_OBSERVE_SECONDS = 2.0
HEALTH_PERIOD_MS = 100
HEALTH_MIN_SAMPLES = 10
HEALTH_BOUNDS: dict[str, tuple[float, float]] = {
    "stabilizer.roll": (-45.0, 45.0),
    "stabilizer.pitch": (-45.0, 45.0),
    "stateEstimate.z": (-1.0, 5.0),
    "stateEstimate.vz": (-1.0, 1.0),
}
URI_RE = re.compile(r"radio://[0-9]+/[0-9]+/(250K|1M|2M)(/[0-9A-Fa-f]+)?")
SHA_RE = re.compile(r"[0-9a-f]{40}")


class PreparationError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json_once(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def load_provenance(path: Path) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise PreparationError("bundle PROVENANCE.txt is unavailable") from exc
    result: dict[str, str] = {}
    for line in lines:
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key in result:
            raise PreparationError(f"duplicate provenance key: {key}")
        result[key] = value
    required = {
        "repository_target_sha": None,
        "test_profile": TEST_PROFILE,
        "firmware_bin_sha256": FIRMWARE_BIN_SHA256,
        "cflib_commit": EXPECTED_CFLIB_COMMIT,
        "cflib_tree": EXPECTED_CFLIB_TREE,
        "cflib_subtree": EXPECTED_CFLIB_SUBTREE,
    }
    for key, expected in required.items():
        value = result.get(key)
        if value is None:
            raise PreparationError(f"missing provenance key: {key}")
        if expected is not None and value != expected:
            raise PreparationError(f"unexpected provenance value: {key}")
    if not SHA_RE.fullmatch(result["repository_target_sha"]):
        raise PreparationError("invalid repository_target_sha")
    return result


def normalize_value(ctype: str, raw: object) -> int | float:
    if isinstance(raw, bool):
        raise PreparationError(f"boolean is not valid for {ctype}")
    try:
        if ctype == "uint8_t":
            if isinstance(raw, float) and not raw.is_integer():
                raise ValueError
            text = str(raw)
            value = int(text, 10)
            if str(value) != text and text not in {f"{value}.0", f"+{value}"}:
                # cflib normally returns canonical integer strings. Accept a
                # numeric Python input for deterministic fakes, not arbitrary
                # lossy conversions.
                if not isinstance(raw, int):
                    raise ValueError
            if not 0 <= value <= 255:
                raise ValueError
            return value
        if ctype == "float":
            value = float(raw)
            if not math.isfinite(value):
                raise ValueError
            return value
    except (TypeError, ValueError) as exc:
        raise PreparationError(f"invalid {ctype} value: {raw!r}") from exc
    raise PreparationError(f"unsupported parameter type: {ctype}")


def same_value(ctype: str, raw: object, expected: object) -> bool:
    observed = normalize_value(ctype, raw)
    target = normalize_value(ctype, expected)
    return observed == target


class CflibParamAdapter:
    def __init__(self, cf: object) -> None:
        self.cf = cf

    def describe(self, name: str) -> tuple[str, bool, str]:
        element = self.cf.param.toc.get_element_by_complete_name(name)
        if element is None:
            raise PreparationError(f"required parameter missing: {name}")
        ctype = getattr(element, "ctype", None)
        writable = getattr(element, "get_readable_access", lambda: "RO")() == "RW"
        return str(ctype), writable, str(self.cf.param.get_value(name))

    def read_fresh(self, name: str, timeout: float = 3.0) -> str:
        group, short_name = name.split(".", 1)
        event = threading.Event()
        result: dict[str, str] = {}

        def callback(param_name: str, value: str) -> None:
            if param_name == name:
                result["value"] = str(value)
                event.set()

        self.cf.param.add_update_callback(group=group, name=short_name, cb=callback)
        try:
            self.cf.param.request_param_update(name)
            if not event.wait(timeout=timeout):
                raise PreparationError(f"read-back timeout: {name}")
            return result["value"]
        finally:
            self.cf.param.remove_update_callback(group=group, name=short_name, cb=callback)

    def write(self, name: str, value: object, timeout: float = 3.0) -> str:
        group, short_name = name.split(".", 1)
        event = threading.Event()
        result: dict[str, str] = {}

        def callback(param_name: str, observed: str) -> None:
            if param_name == name:
                result["value"] = str(observed)
                event.set()

        self.cf.param.add_update_callback(group=group, name=short_name, cb=callback)
        try:
            self.cf.param.set_value(name, value)
            if not event.wait(timeout=timeout):
                raise PreparationError(f"write acknowledgement timeout: {name}")
            return result["value"]
        finally:
            self.cf.param.remove_update_callback(group=group, name=short_name, cb=callback)


def configure_required_parameters(adapter: object) -> dict[str, dict[str, object]]:
    observed: dict[str, tuple[str, str]] = {}
    for name, spec in PARAMETERS.items():
        ctype, writable, before = adapter.describe(name)
        if ctype != spec["ctype"]:
            raise PreparationError(
                f"wrong parameter type for {name}: expected {spec['ctype']}, got {ctype}"
            )
        if not writable:
            raise PreparationError(f"required parameter is not writable: {name}")
        normalize_value(ctype, before)
        observed[name] = (ctype, before)

    records: dict[str, dict[str, object]] = {}
    for name, spec in PARAMETERS.items():
        ctype, before = observed[name]
        action = "unchanged"
        if not same_value(ctype, before, spec["value"]):
            adapter.write(name, spec["value"])
            action = "written"
        after = adapter.read_fresh(name)
        if not same_value(ctype, after, spec["value"]):
            raise PreparationError(
                f"read-back mismatch for {name}: expected {spec['value']!r}, got {after!r}"
            )
        records[name] = {
            "ctype": ctype,
            "expected": spec["value"],
            "observed_before": before,
            "action": action,
            "observed_after": after,
        }
    return records


def pulse_estimator_reset(adapter: object, sleeper=time.sleep) -> dict[str, object]:
    ctype, writable, before = adapter.describe(RESET_PARAMETER)
    if ctype != RESET_CTYPE:
        raise PreparationError(
            f"wrong parameter type for {RESET_PARAMETER}: expected {RESET_CTYPE}, got {ctype}"
        )
    if not writable:
        raise PreparationError(f"required parameter is not writable: {RESET_PARAMETER}")
    normalize_value(ctype, before)

    active_ack = adapter.write(RESET_PARAMETER, RESET_ACTIVE)
    if not same_value(ctype, active_ack, RESET_ACTIVE):
        raise PreparationError(f"reset activation acknowledgement mismatch: {active_ack!r}")
    sleeper(RESET_HOLD_SECONDS)
    inactive_ack = adapter.write(RESET_PARAMETER, RESET_INACTIVE)
    if not same_value(ctype, inactive_ack, RESET_INACTIVE):
        raise PreparationError(f"reset release acknowledgement mismatch: {inactive_ack!r}")
    after = adapter.read_fresh(RESET_PARAMETER)
    if not same_value(ctype, after, RESET_INACTIVE):
        raise PreparationError(f"reset final read-back mismatch: {after!r}")

    return {
        "parameter": RESET_PARAMETER,
        "ctype": RESET_CTYPE,
        "observed_before": before,
        "active_value": RESET_ACTIVE,
        "hold_seconds": RESET_HOLD_SECONDS,
        "inactive_value": RESET_INACTIVE,
        "observed_after": after,
    }


def evaluate_health_samples(samples: list[dict[str, object]]) -> dict[str, object]:
    if len(samples) < HEALTH_MIN_SAMPLES:
        raise PreparationError(
            f"insufficient estimator health samples: {len(samples)} < {HEALTH_MIN_SAMPLES}"
        )
    observed: dict[str, dict[str, float]] = {}
    for name, (low, high) in HEALTH_BOUNDS.items():
        values: list[float] = []
        for sample in samples:
            raw = sample.get(name)
            if isinstance(raw, bool):
                raise PreparationError(f"non-finite estimator health sample: {name}")
            try:
                value = float(raw)
            except (TypeError, ValueError) as exc:
                raise PreparationError(f"non-finite estimator health sample: {name}") from exc
            if not math.isfinite(value):
                raise PreparationError(f"non-finite estimator health sample: {name}")
            if value < low or value > high:
                raise PreparationError(
                    f"estimator health bound exceeded: {name}={value} outside [{low}, {high}]"
                )
            values.append(value)
        observed[name] = {"min": min(values), "max": max(values)}
    return {
        "status": "HEALTHY",
        "sample_count": len(samples),
        "period_ms": HEALTH_PERIOD_MS,
        "observe_seconds": HEALTH_OBSERVE_SECONDS,
        "bounds": {name: [low, high] for name, (low, high) in HEALTH_BOUNDS.items()},
        "observed": observed,
    }


def collect_live_health(cf: object, *, settle_seconds: float) -> dict[str, object]:
    from cflib.crazyflie.log import LogConfig

    if settle_seconds:
        time.sleep(settle_seconds)

    samples: list[dict[str, object]] = []
    error: list[str] = []
    config = LogConfig("X3_health", HEALTH_PERIOD_MS)
    for name in HEALTH_BOUNDS:
        config.add_variable(name, "float")

    def received(_timestamp, data, _config) -> None:
        samples.append({name: data.get(name) for name in HEALTH_BOUNDS})

    def failed(_config, message) -> None:
        if not error:
            error.append(str(message))

    config.data_received_cb.add_callback(received)
    config.error_cb.add_callback(failed)
    cf.log.add_config(config)
    try:
        config.start()
        deadline = time.monotonic() + HEALTH_OBSERVE_SECONDS
        while time.monotonic() < deadline:
            if error:
                raise PreparationError(f"estimator health log failed: {error[0]}")
            time.sleep(0.02)
    finally:
        try:
            config.stop()
        except Exception:
            pass

    health = evaluate_health_samples(samples)
    health["settle_seconds"] = settle_seconds
    return health


def require_firmware(path: Path) -> None:
    if not path.is_file():
        raise PreparationError("exact bundled cf2.bin is missing")
    digest = sha256(path)
    if digest != FIRMWARE_BIN_SHA256:
        raise PreparationError(
            f"firmware digest mismatch: expected {FIRMWARE_BIN_SHA256}, got {digest}"
        )


def flash_exact_firmware(uri: str, firmware_bin: Path) -> None:
    # Imports are deliberately inside the physical path so --self-test and
    # --verify-record remain hardware-free and do not require cflib.
    import cflib.crtp
    from cflib.bootloader import Bootloader, Target

    cflib.crtp.init_drivers()
    bootloader = Bootloader(clink=uri)
    target = Target("cf2", "stm32", "fw", [], [])
    try:
        bootloader.flash_full(
            filename=str(firmware_bin),
            warm=True,
            targets=[target],
            enable_console_log=False,
        )
    except Exception as exc:
        raise PreparationError(f"exact STM32 firmware flash failed: {exc}") from exc
    finally:
        try:
            bootloader.close()
        except Exception:
            pass


def configure_live(
    uri: str,
) -> tuple[dict[str, dict[str, object]], dict[str, object], dict[str, object]]:
    from cflib.crazyflie import Crazyflie
    from cflib.crazyflie.syncCrazyflie import SyncCrazyflie

    try:
        with SyncCrazyflie(uri, cf=Crazyflie(rw_cache=None)) as scf:
            adapter = CflibParamAdapter(scf.cf)
            parameters = configure_required_parameters(adapter)
            reset = pulse_estimator_reset(adapter)
            health = collect_live_health(scf.cf, settle_seconds=RESET_SETTLE_SECONDS)
            return parameters, reset, health
    except PreparationError:
        raise
    except Exception as exc:
        raise PreparationError(f"post-flash configuration/reset failed: {exc}") from exc


def verify_live_health(uri: str) -> dict[str, object]:
    import cflib.crtp
    from cflib.crazyflie import Crazyflie
    from cflib.crazyflie.syncCrazyflie import SyncCrazyflie

    try:
        cflib.crtp.init_drivers()
        with SyncCrazyflie(uri, cf=Crazyflie(rw_cache=None)) as scf:
            return collect_live_health(scf.cf, settle_seconds=0.0)
    except PreparationError:
        raise
    except Exception as exc:
        raise PreparationError(f"live estimator health verification failed: {exc}") from exc


def build_record(
    *,
    uri: str,
    firmware_bin: Path,
    provenance_path: Path,
    parameters: dict[str, dict[str, object]],
    reset: dict[str, object],
    health: dict[str, object],
) -> dict[str, object]:
    provenance = load_provenance(provenance_path)
    return {
        "schema": SCHEMA,
        "status": "PREPARED",
        "test_profile": TEST_PROFILE,
        "repository_target_sha": provenance["repository_target_sha"],
        "uri": uri,
        "props_removed": True,
        "firmware": {
            "tested_source_sha": FIRMWARE_TARGET,
            "bundled_cf2_sha256": FIRMWARE_BIN_SHA256,
            "flash_target": "cf2/stm32/fw",
            "flash_completed": True,
        },
        "runtime": {
            "cflib_commit": EXPECTED_CFLIB_COMMIT,
            "cflib_tree": EXPECTED_CFLIB_TREE,
            "cflib_subtree": EXPECTED_CFLIB_SUBTREE,
        },
        "parameters": parameters,
        "estimator_reset": reset,
        "estimator_health": health,
        "effects": {
            "firmware_flash": "exact-bundled-stm32",
            "parameter_writes": [
                name for name, row in parameters.items() if row["action"] == "written"
            ],
            "persistent_store": False,
            "estimator_reset": "ukf.resetEstimation:uint8_t:1->0:0.25s",
            "arming": False,
            "commander": False,
            "motors": False,
            "scientific_retry": False,
        },
        "preparation_script_sha256": sha256(Path(__file__)),
        "provenance_sha256": sha256(provenance_path),
        "firmware_file_sha256": sha256(firmware_bin),
        "finished_unix_s": time.time(),
    }


def validate_record(
    record: object,
    *,
    uri: str,
    firmware_bin: Path,
    provenance_path: Path,
) -> None:
    if not isinstance(record, dict):
        raise PreparationError("preparation record must be a JSON object")
    provenance = load_provenance(provenance_path)
    checks = {
        "schema": SCHEMA,
        "status": "PREPARED",
        "test_profile": TEST_PROFILE,
        "repository_target_sha": provenance["repository_target_sha"],
        "uri": uri,
        "props_removed": True,
        "preparation_script_sha256": sha256(Path(__file__)),
        "provenance_sha256": sha256(provenance_path),
        "firmware_file_sha256": FIRMWARE_BIN_SHA256,
    }
    for key, expected in checks.items():
        if record.get(key) != expected:
            raise PreparationError(f"preparation record mismatch: {key}")

    firmware = record.get("firmware")
    if not isinstance(firmware, dict):
        raise PreparationError("preparation record firmware section missing")
    expected_firmware = {
        "tested_source_sha": FIRMWARE_TARGET,
        "bundled_cf2_sha256": FIRMWARE_BIN_SHA256,
        "flash_target": "cf2/stm32/fw",
        "flash_completed": True,
    }
    for key, expected in expected_firmware.items():
        if firmware.get(key) != expected:
            raise PreparationError(f"preparation record firmware mismatch: {key}")
    require_firmware(firmware_bin)

    runtime = record.get("runtime")
    expected_runtime = {
        "cflib_commit": EXPECTED_CFLIB_COMMIT,
        "cflib_tree": EXPECTED_CFLIB_TREE,
        "cflib_subtree": EXPECTED_CFLIB_SUBTREE,
    }
    if runtime != expected_runtime:
        raise PreparationError("preparation record runtime mismatch")

    parameters = record.get("parameters")
    if not isinstance(parameters, dict) or set(parameters) != set(PARAMETERS):
        raise PreparationError("preparation record parameter set mismatch")
    for name, spec in PARAMETERS.items():
        row = parameters.get(name)
        if not isinstance(row, dict):
            raise PreparationError(f"preparation record parameter missing: {name}")
        if row.get("ctype") != spec["ctype"]:
            raise PreparationError(f"preparation record type mismatch: {name}")
        if not same_value(spec["ctype"], row.get("expected"), spec["value"]):
            raise PreparationError(f"preparation record expected value mismatch: {name}")
        if not same_value(spec["ctype"], row.get("observed_after"), spec["value"]):
            raise PreparationError(f"preparation record read-back mismatch: {name}")
        if row.get("action") not in {"unchanged", "written"}:
            raise PreparationError(f"preparation record action invalid: {name}")

    reset = record.get("estimator_reset")
    if not isinstance(reset, dict):
        raise PreparationError("preparation record estimator reset section missing")
    expected_reset = {
        "parameter": RESET_PARAMETER,
        "ctype": RESET_CTYPE,
        "active_value": RESET_ACTIVE,
        "hold_seconds": RESET_HOLD_SECONDS,
        "inactive_value": RESET_INACTIVE,
    }
    for key, expected in expected_reset.items():
        if reset.get(key) != expected:
            raise PreparationError(f"preparation record estimator reset mismatch: {key}")
    if not same_value(RESET_CTYPE, reset.get("observed_after"), RESET_INACTIVE):
        raise PreparationError("preparation record estimator reset final value mismatch")

    health = record.get("estimator_health")
    if not isinstance(health, dict) or health.get("status") != "HEALTHY":
        raise PreparationError("preparation record estimator health missing")
    if health.get("sample_count", 0) < HEALTH_MIN_SAMPLES:
        raise PreparationError("preparation record estimator health sample count too small")
    if health.get("settle_seconds") != RESET_SETTLE_SECONDS:
        raise PreparationError("preparation record estimator settle duration mismatch")
    if health.get("bounds") != {
        name: [low, high] for name, (low, high) in HEALTH_BOUNDS.items()
    }:
        raise PreparationError("preparation record estimator health bounds mismatch")
    observed_health = health.get("observed")
    if not isinstance(observed_health, dict):
        raise PreparationError("preparation record estimator health observations missing")
    for name, (low, high) in HEALTH_BOUNDS.items():
        row = observed_health.get(name)
        if not isinstance(row, dict):
            raise PreparationError(f"preparation record estimator health missing: {name}")
        for edge in ("min", "max"):
            value = row.get(edge)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise PreparationError(f"preparation record estimator health invalid: {name}")
            if value < low or value > high:
                raise PreparationError(f"preparation record estimator health out of bounds: {name}")

    effects = record.get("effects")
    if not isinstance(effects, dict):
        raise PreparationError("preparation record effects section missing")
    for key in ("persistent_store", "arming", "commander", "motors", "scientific_retry"):
        if effects.get(key) is not False:
            raise PreparationError(f"forbidden preparation effect recorded: {key}")
    if effects.get("estimator_reset") != "ukf.resetEstimation:uint8_t:1->0:0.25s":
        raise PreparationError("preparation record estimator reset effect mismatch")
    if effects.get("firmware_flash") != "exact-bundled-stm32":
        raise PreparationError("preparation record firmware effect mismatch")
    writes = effects.get("parameter_writes")
    expected_writes = [
        name for name, row in parameters.items() if row.get("action") == "written"
    ]
    if writes != expected_writes:
        raise PreparationError("preparation record parameter write list mismatch")


class FakeAdapter:
    def __init__(
        self,
        rows: dict[str, tuple[str, bool, object]],
        *,
        read_override: dict[str, object] | None = None,
    ) -> None:
        self.rows = dict(rows)
        self.read_override = read_override or {}
        self.writes: list[tuple[str, object]] = []

    def describe(self, name: str) -> tuple[str, bool, str]:
        if name not in self.rows:
            raise PreparationError(f"required parameter missing: {name}")
        ctype, writable, value = self.rows[name]
        return ctype, writable, str(value)

    def write(self, name: str, value: object, timeout: float = 3.0) -> str:
        ctype, writable, _ = self.rows[name]
        if not writable:
            raise PreparationError(f"required parameter is not writable: {name}")
        self.rows[name] = (ctype, writable, value)
        self.writes.append((name, value))
        return str(value)

    def read_fresh(self, name: str, timeout: float = 3.0) -> str:
        if name in self.read_override:
            return str(self.read_override[name])
        return str(self.rows[name][2])


def self_test() -> None:
    exact = {
        name: (spec["ctype"], True, spec["value"])
        for name, spec in PARAMETERS.items()
    }

    configured = configure_required_parameters(FakeAdapter(exact))
    if any(row["action"] != "unchanged" for row in configured.values()):
        raise AssertionError("exact configuration must not be rewritten")

    reset_rows = dict(exact)
    reset_rows[RESET_PARAMETER] = (RESET_CTYPE, True, RESET_INACTIVE)
    reset_adapter = FakeAdapter(reset_rows)
    slept: list[float] = []
    reset_record = pulse_estimator_reset(reset_adapter, sleeper=slept.append)
    if reset_adapter.writes[-2:] != [
        (RESET_PARAMETER, RESET_ACTIVE),
        (RESET_PARAMETER, RESET_INACTIVE),
    ]:
        raise AssertionError("fresh estimator reset pulse was not exact")
    if slept != [RESET_HOLD_SECONDS] or reset_record["observed_after"] != "0":
        raise AssertionError("fresh estimator reset timing/read-back changed")

    healthy = [
        {
            "stabilizer.roll": 0.5,
            "stabilizer.pitch": -0.5,
            "stateEstimate.z": 0.7,
            "stateEstimate.vz": 0.01,
        }
        for _ in range(HEALTH_MIN_SAMPLES)
    ]
    if evaluate_health_samples(healthy)["status"] != "HEALTHY":
        raise AssertionError("healthy estimator state was rejected")
    divergent = list(healthy)
    divergent[-1] = dict(divergent[-1], **{"stateEstimate.z": 57.0})
    try:
        evaluate_health_samples(divergent)
    except PreparationError as exc:
        if "health bound exceeded" not in str(exc):
            raise
    else:
        raise AssertionError("grossly divergent estimator state must fail closed")
    nonfinite = list(healthy)
    nonfinite[-1] = dict(nonfinite[-1], **{"stabilizer.pitch": float("nan")})
    try:
        evaluate_health_samples(nonfinite)
    except PreparationError as exc:
        if "non-finite" not in str(exc):
            raise
    else:
        raise AssertionError("non-finite estimator state must fail closed")

    changed = dict(exact)
    changed["stabilizer.estimator"] = ("uint8_t", True, 2)
    changed["ukf.qualityGateTof"] = ("float", True, 100.0)
    changed["ukf.surfaceOffsetS3"] = ("uint8_t", True, 0)
    configured = configure_required_parameters(FakeAdapter(changed))
    if configured["stabilizer.estimator"]["action"] != "written":
        raise AssertionError("mismatched estimator was not reconstructed")
    if configured["ukf.baroNoise"]["action"] != "unchanged":
        raise AssertionError("already-correct parameter was unnecessarily rewritten")

    missing = dict(exact)
    del missing["ukf.surfaceOffsetS3"]
    try:
        configure_required_parameters(FakeAdapter(missing))
    except PreparationError as exc:
        if "missing" not in str(exc):
            raise
    else:
        raise AssertionError("missing required parameter must fail closed")

    wrong_type = dict(exact)
    wrong_type["ukf.surfaceOffsetS3"] = ("float", True, 1.0)
    try:
        configure_required_parameters(FakeAdapter(wrong_type))
    except PreparationError as exc:
        if "wrong parameter type" not in str(exc):
            raise
    else:
        raise AssertionError("wrong parameter type must fail closed")

    wrong_readback = dict(exact)
    wrong_readback["ukf.surfaceOffsetS3"] = ("uint8_t", True, 0)
    try:
        configure_required_parameters(
            FakeAdapter(wrong_readback, read_override={"ukf.surfaceOffsetS3": 0})
        )
    except PreparationError as exc:
        if "read-back mismatch" not in str(exc):
            raise
    else:
        raise AssertionError("wrong post-write value must fail closed")

    with tempfile.TemporaryDirectory(prefix="webeeblocks-x3-prep-selftest-") as text:
        root = Path(text)
        fixture = root / "fixture.bin"
        fixture.write_bytes(b"not-the-x3-firmware")
        try:
            require_firmware(fixture)
        except PreparationError as exc:
            if "digest mismatch" not in str(exc):
                raise
        else:
            raise AssertionError("wrong firmware must fail closed")

    print("PASS: X3 preparation fail-closed firmware, parameter, fresh-reset and health contract")


def prepare(args: argparse.Namespace) -> int:
    if not args.props_removed:
        raise PreparationError("props removal must be explicitly confirmed")
    if not URI_RE.fullmatch(args.uri):
        raise PreparationError("one explicit Crazyradio URI is required")
    require_firmware(args.firmware_bin)
    provenance = load_provenance(args.provenance)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    write_json_once(
        output / "preparation-start.json",
        {
            "schema": SCHEMA,
            "status": "STARTED",
            "test_profile": TEST_PROFILE,
            "repository_target_sha": provenance["repository_target_sha"],
            "uri": args.uri,
            "props_removed": True,
            "firmware_file_sha256": FIRMWARE_BIN_SHA256,
            "started_unix_s": time.time(),
        },
    )

    result: dict[str, object]
    try:
        flash_exact_firmware(args.uri, args.firmware_bin)
        parameters, reset, health = configure_live(args.uri)
        result = build_record(
            uri=args.uri,
            firmware_bin=args.firmware_bin,
            provenance_path=args.provenance,
            parameters=parameters,
            reset=reset,
            health=health,
        )
        validate_record(
            result,
            uri=args.uri,
            firmware_bin=args.firmware_bin,
            provenance_path=args.provenance,
        )
    except Exception as exc:
        result = {
            "schema": SCHEMA,
            "status": "INCOMPLETE",
            "test_profile": TEST_PROFILE,
            "repository_target_sha": provenance["repository_target_sha"],
            "uri": args.uri,
            "props_removed": True,
            "firmware_file_sha256": FIRMWARE_BIN_SHA256,
            "error": f"{type(exc).__name__}: {exc}",
            "finished_unix_s": time.time(),
            "scientific_verdict": None,
        }
        write_json_once(output / "preparation.json", result)
        print(f"PREPARATION_INCOMPLETE: {output}", file=__import__("sys").stderr)
        return 1

    result["scientific_verdict"] = None
    write_json_once(output / "preparation.json", result)
    print(f"PREPARED: {output / 'preparation.json'}")
    return 0


def verify_record_file(args: argparse.Namespace) -> int:
    if not URI_RE.fullmatch(args.uri):
        raise PreparationError("one explicit Crazyradio URI is required")
    try:
        record = json.loads(args.verify_record.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PreparationError("preparation record is unavailable or invalid JSON") from exc
    validate_record(
        record,
        uri=args.uri,
        firmware_bin=args.firmware_bin,
        provenance_path=args.provenance,
    )
    print("PASS: exact X3 preparation record verified")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--verify-record", type=Path)
    parser.add_argument("--health-check", action="store_true")
    parser.add_argument("--uri")
    parser.add_argument("--firmware-bin", type=Path)
    parser.add_argument("--provenance", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--props-removed", action="store_true")
    args = parser.parse_args()

    try:
        if args.self_test:
            self_test()
            return 0
        if args.verify_record is not None:
            if not all((args.uri, args.firmware_bin, args.provenance)):
                parser.error("--verify-record requires --uri, --firmware-bin and --provenance")
            return verify_record_file(args)
        if args.health_check:
            if not args.uri:
                parser.error("--health-check requires --uri")
            health = verify_live_health(args.uri)
            print("PASS: X3 live estimator health verified " + json.dumps(health, sort_keys=True))
            return 0
        if not all((args.uri, args.firmware_bin, args.provenance, args.output)):
            parser.error(
                "preparation requires --uri, --firmware-bin, --provenance, --output and --props-removed"
            )
        return prepare(args)
    except (OSError, UnicodeError, PreparationError) as exc:
        print(f"PREPARATION_ERROR: {exc}", file=__import__("sys").stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
