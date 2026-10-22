"""Read-only R2025a observer for #637; never controls or judges the vehicle."""
import json
import math
import os
from pathlib import Path


def diagnostic_number(value):
    # Preserve unavailable/non-finite evidence without producing invalid JSON.
    return value if math.isfinite(value) else repr(value)


def record(supervisor, destination):
    vehicle = supervisor.getFromDef("CI_AUTONOMOUS_CRAZYFLIE")
    if vehicle is None:
        raise RuntimeError("CI autonomous observer vehicle unavailable")
    custom_data = vehicle.getField("customData")
    if custom_data is None:
        raise RuntimeError("CI autonomous observer customData unavailable")
    step = int(supervisor.getBasicTimeStep())
    with Path(destination).open("w", encoding="utf-8", buffering=1) as stream:
        stream.write(json.dumps({"type": "header", "version": 1,
                                 "step_ms": step,
                                 "scope": "read-only-native-state-not-runtime-ack"}) + "\n")
        while supervisor.step(step) != -1:
            # These native observations complement cached GPS/IMU/gyro and the
            # Runtime's finite differences. They do not replace either oracle.
            contacts = vehicle.getContactPoints(includeDescendants=True)
            sample = {
                "type": "sample", "time": supervisor.getTime(),
                "custom_data": custom_data.getSFString(),
                "position": vehicle.getPosition(),
                "orientation": vehicle.getOrientation(),
                "velocity": vehicle.getVelocity(),
                "contacts": [{"point": contact.point, "node_id": contact.node_id}
                             for contact in contacts],
            }
            for key in ("position", "orientation", "velocity"):
                sample[key] = [diagnostic_number(value) for value in sample[key]]
            for contact in sample["contacts"]:
                contact["point"] = [diagnostic_number(value) for value in contact["point"]]
            stream.write(json.dumps(sample, allow_nan=False, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    from controller import Supervisor
    directory = Path(os.environ["WEBEEBLOCKS_CI_ARTIFACT_DIR"])
    record(Supervisor(), directory / "native-reset-state.jsonl")
