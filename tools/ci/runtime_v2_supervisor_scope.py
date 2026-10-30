#!/usr/bin/env python3
"""Keep the shared runtime's Supervisor inventory explicit and body-local.

Contact observation is a private LAND actuation input. It cannot query another
node, choose a mission target, or replace an independent mission outcome oracle.
This static inventory complements, and does not replace, native evidence.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "controllers/crazyflie_runtime_v2/crazyflie_runtime_v2.c"
API = re.compile(r"\b(wb_supervisor_[A-Za-z0-9_]+)\s*\(")
ALLOWED = {
    "wb_supervisor_node_get_self",
    "wb_supervisor_node_get_field",
    "wb_supervisor_field_get_sf_vec3f",
    "wb_supervisor_field_get_sf_rotation",
    "wb_supervisor_field_set_sf_vec3f",
    "wb_supervisor_field_set_sf_rotation",
    "wb_supervisor_node_reset_physics",
    "wb_supervisor_world_reload",
    "wb_supervisor_node_get_contact_points",
}


def validate(source: str) -> None:
    used = set(API.findall(source))
    if used != ALLOWED:
        raise ValueError(f"unexpected Runtime v2 Supervisor API set: used={sorted(used)} allowed={sorted(ALLOWED)}")
    contact = "wb_supervisor_node_get_contact_points"
    if API.findall(source).count(contact) != 1:
        raise ValueError("exactly one private contact observation required")
    helper = re.search(
        r"static int land_has_ground_contact\(double z, double ground_z\) \{(?P<body>.*?)\n\}",
        source, re.S,
    )
    if helper is None:
        raise ValueError("private LAND contact helper missing")
    body = helper.group("body")
    if (set(API.findall(body)) != {contact, "wb_supervisor_node_get_self"} or
            not re.search(r"wb_supervisor_node_get_contact_points\(\s*"
                          r"wb_supervisor_node_get_self\(\),\s*true,\s*&count\s*\)", body)):
        raise ValueError("contact observation must query only the current body")
    land = re.search(r"\} else if \(command == CMD_LAND\) \{(?P<body>.*?)"
                     r"\} else if \(airborne\) \{", source, re.S)
    calls = re.findall(r"\bland_has_ground_contact\s*\(", source)
    if (land is None or len(calls) != 2 or
            "land_has_ground_contact(z, origin_z)" not in land.group("body")):
        raise ValueError("contact observation must remain private to LAND")


if __name__ == "__main__":
    validate(SOURCE.read_text())
    print("PASS exact Supervisor inventory; contact observation restricted to body-local LAND")
