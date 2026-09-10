#!/usr/bin/env python3
"""Pure exact-AST -> typed HighLevel takeoff request semantics.

This module is deliberately non-authority and emits no CRTP packet. It consumes
the exact canonical ``astBinding`` already established by the browser-side
#249/#278 current-program round trip and derives only the first top-level
``takeoff`` statement. The resulting request is the pinned Crazyflie firmware
``COMMAND_TAKEOFF_WITH_VELOCITY`` packet with absolute height, current-yaw
preservation and an explicit safe-default 0.5 m/s vertical velocity.

No caller-supplied height, raw packet bytes, teacher decision, session object or
other effect authority is accepted here. A later trusted physical-host consumer
must still compose this pure request with #267/#266/#262/#257/#272/#271/#273
and fresh #278/#249 provenance immediately before emission.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import json
import math
import struct

AST_VERSION = 1
AST_SEMANTICS = "webeeblocks-ast-v1"
MIN_TAKEOFF_HEIGHT_M = 0.2
MAX_TAKEOFF_HEIGHT_M = 1.5
TAKEOFF_WITH_VELOCITY_COMMAND = 9
TAKEOFF_GROUP_MASK = 0
TAKEOFF_VELOCITY_M_S = 0.5
_TAKEOFF_PACKET = struct.Struct("<BBf?f?f")


class TakeoffCommandError(RuntimeError):
    """Fail-closed error for an unavailable exact-bound takeoff request."""


def _reject_json_constant(_value: str) -> None:
    raise TakeoffCommandError("AST binding contains a non-finite JSON number")


def _object_without_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise TakeoffCommandError("AST binding contains duplicate object keys")
        result[key] = value
    return result


def _canonical_json_string(value: str) -> str:
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    # Modern JSON.stringify emits non-ASCII text directly but escapes lone UTF-16
    # surrogates. Python can retain a lone surrogate when ensure_ascii=False, so
    # normalize that one difference before exact-text comparison.
    return "".join(
        f"\\u{ord(character):04x}"
        if 0xD800 <= ord(character) <= 0xDFFF
        else character
        for character in encoded
    )


def _canonical_json_number(value: int | float) -> str:
    number = float(value)
    if not math.isfinite(number):
        raise TakeoffCommandError("AST binding contains a non-finite JSON number")
    if number == 0.0:
        return "0"

    # JSON.parse/JSON.stringify use IEEE-754 Number semantics. Python's float
    # ``repr`` supplies the shortest round-tripping decimal; normalize only the
    # ECMAScript presentation thresholds/exponent spelling used by canonicalJson.
    shortest = repr(number).lower()
    magnitude = abs(number)
    if 1e-6 <= magnitude < 1e21:
        fixed = format(Decimal(shortest), "f") if "e" in shortest else shortest
        if "." in fixed:
            fixed = fixed.rstrip("0").rstrip(".")
        return fixed

    if "e" not in shortest:
        return shortest.rstrip("0").rstrip(".") if "." in shortest else shortest
    mantissa, exponent_text = shortest.split("e", 1)
    if mantissa.endswith(".0"):
        mantissa = mantissa[:-2]
    exponent = int(exponent_text)
    sign = "+" if exponent >= 0 else ""
    return f"{mantissa}e{sign}{exponent}"


def _canonical_json(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return _canonical_json_string(value)
    if isinstance(value, (int, float)):
        return _canonical_json_number(value)
    if isinstance(value, list):
        return "[" + ",".join(_canonical_json(item) for item in value) + "]"
    if isinstance(value, dict):
        return "{" + ",".join(
            _canonical_json_string(key) + ":" + _canonical_json(value[key])
            for key in sorted(value)
        ) + "}"
    raise TakeoffCommandError("AST binding contains a non-JSON value")


def _parse_ast_binding(ast_binding: object) -> dict[str, object]:
    if (
        not isinstance(ast_binding, str)
        or not ast_binding.strip()
        or ast_binding != ast_binding.strip()
    ):
        raise TakeoffCommandError(
            "exact canonical AST binding must be a non-empty trimmed string"
        )
    try:
        value = json.loads(
            ast_binding,
            parse_constant=_reject_json_constant,
            parse_int=float,
            parse_float=float,
            object_pairs_hook=_object_without_duplicate_keys,
        )
    except TakeoffCommandError:
        raise
    except (TypeError, ValueError) as exc:
        raise TakeoffCommandError("exact canonical AST binding is malformed JSON") from exc

    if _canonical_json(value) != ast_binding:
        raise TakeoffCommandError(
            "AST binding is not the exact canonical JSON serialization"
        )
    if not isinstance(value, dict) or set(value) != {"version", "semantics", "program"}:
        raise TakeoffCommandError(
            "AST binding must contain only version, semantics and program"
        )
    version = value["version"]
    if isinstance(version, bool) or version != AST_VERSION:
        raise TakeoffCommandError("unsupported physical AST version")
    if value["semantics"] != AST_SEMANTICS:
        raise TakeoffCommandError("unsupported physical AST semantics")
    if not isinstance(value["program"], list) or len(value["program"]) < 2:
        raise TakeoffCommandError("physical AST program must contain flight boundaries")
    return value


def _takeoff_height(ast_binding: object) -> float:
    ast = _parse_ast_binding(ast_binding)
    first = ast["program"][0]
    if (
        not isinstance(first, dict)
        or set(first) != {"kind", "height_m"}
        or first.get("kind") != "takeoff"
    ):
        raise TakeoffCommandError(
            "physical AST must begin with the exact takeoff statement"
        )

    height = first["height_m"]
    if isinstance(height, bool) or not isinstance(height, (int, float)):
        raise TakeoffCommandError("takeoff height must be numeric")
    parsed = float(height)
    if not math.isfinite(parsed):
        raise TakeoffCommandError("takeoff height must be finite")
    if parsed < MIN_TAKEOFF_HEIGHT_M or parsed > MAX_TAKEOFF_HEIGHT_M:
        raise TakeoffCommandError("takeoff height is outside Runtime v2 bounds")
    return parsed


@dataclass(frozen=True)
class BoundTakeoffCommand:
    """Pure typed command derived from one exact canonical student AST binding."""

    ast_binding: str
    height_m: float
    request: bytes


def derive_bound_takeoff_command(ast_binding: object) -> BoundTakeoffCommand:
    """Derive command 9 only from the first takeoff in the exact AST binding."""
    height = _takeoff_height(ast_binding)
    request = _TAKEOFF_PACKET.pack(
        TAKEOFF_WITH_VELOCITY_COMMAND,
        TAKEOFF_GROUP_MASK,
        height,
        False,  # absolute target height
        0.0,  # ignored because current yaw is explicitly preserved
        True,
        TAKEOFF_VELOCITY_M_S,
    )
    return BoundTakeoffCommand(
        ast_binding=str(ast_binding),
        height_m=height,
        request=request,
    )
