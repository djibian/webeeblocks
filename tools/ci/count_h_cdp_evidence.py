"""Pure, adversarially tested evidence parser for the real A6 Chrome/Webots test.

No native authority is created here: only actual native transcript lines count.
The UI's sceneIdentity alone never proves a fresh Webots scene incarnation.
"""
import re


def attest_visit(trace, index, variant, observed_ready, seen_nonces):
    """Return a fresh native witness or None while pending; never mutate inputs.

    Native request sequence is 1/2/3/4 for the same browser/WBT incarnation.
    The exact current response and a subsequent, NEW observer READY are required.
    Duplicate responses, extra observers and reused nonce are fatal evidence.
    """
    if index not in range(4) or variant not in (1, 2, 3):
        raise ValueError("A6 visit index or variant out of bounds")
    if set(observed_ready) != {1, 2, 3}:
        raise ValueError("missing A6 observer history")
    ack_pattern = re.compile(
        r"(?m)^WEBEEBLOCKS_RUNTIME_V2 RESPONSE " +
        str(index + 1) + r" SCENE_OK ([0-9a-f]{64})$")
    acks = list(ack_pattern.finditer(trace))
    if not acks:
        return None
    if len(acks) != 1:
        raise AssertionError("duplicate native SCENE_OK for A6 request")
    ack = acks[0]
    nonce = ack.group(1)
    if nonce in seen_nonces:
        raise AssertionError("reused A6 native scene nonce")
    marker = re.compile(
        r"(?m)^WEBEEBLOCKS_A6_MOTOR_READY n=" + str(variant) + r" ")
    markers = list(marker.finditer(trace))
    previous = observed_ready[variant]
    if len(markers) <= previous:
        return None
    if len(markers) != previous + 1:
        raise AssertionError("unexpected duplicate A6 native observer READY")
    if markers[-1].start() <= ack.end():
        # The sole new marker must occur AFTER the exact current SCENE_OK.
        return None
    return {"nonce": nonce, "ready_count": len(markers), "request_id": index + 1}
