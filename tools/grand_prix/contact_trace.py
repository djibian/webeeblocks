"""Lossless ordered native contact positions for CI trace comparison only."""
import json
import math


def encode_contact_points(contacts):
    """Distinguish not observed ('') from observed empty ('[]').

    Keep the full per-tick world XYZ manifold, not an inferred contact force.
    An invalid native point is not silently filtered into valid evidence.
    """
    if contacts is None:
        return ''
    points = []
    for contact in contacts:
        xyz = tuple(float(value) for value in contact.point)
        if len(xyz) != 3 or not all(math.isfinite(value) for value in xyz):
            raise ValueError('invalid native contact point')
        points.append(xyz)
    return json.dumps(points, separators=(',', ':'), allow_nan=False)
