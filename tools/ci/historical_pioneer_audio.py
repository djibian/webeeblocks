#!/usr/bin/env python3
"""Remove only optional Pioneer wheel sounds from the pinned R2025a CI copy."""
from pathlib import Path
import sys

PIONEER = Path('robots/adept/pioneer3/protos/Pioneer3dx.proto')
WHEELS = ('left', 'right')


def neutralize_source(original: str) -> str:
    patched = original
    for side in WHEELS:
        seam = f'RotationalMotor {{\n            name "{side} wheel"\n            maxVelocity 12.3'
        replacement = seam + '\n            sound ""'
        if patched.count(seam) != 1 or replacement in patched:
            raise ValueError(f'Pinned Pioneer3dx {side} wheel motor seam changed or was already patched')
        patched = patched.replace(seam, replacement, 1)
    if patched.count('sound ""') != original.count('sound ""') + 2:
        raise ValueError('Expected exactly two Pioneer motor sound overrides')
    return patched


def neutralize_wheel_sound(projects: Path) -> Path:
    proto = projects / PIONEER
    source = proto.read_text(encoding='utf-8')
    patched = neutralize_source(source)
    proto.write_text(patched, encoding='utf-8')
    return proto


def main() -> int:
    if len(sys.argv) != 2:
        print('usage: historical_pioneer_audio.py PINNED_WEBOTS_PROJECTS', file=sys.stderr)
        return 2
    try:
        proto = neutralize_wheel_sound(Path(sys.argv[1]))
    except (ValueError, OSError) as error:
        print(f'FAIL pinned Pioneer sound isolation: {error}', file=sys.stderr)
        return 1
    print(f'PASS: neutralized exactly two optional wheel sounds in {proto}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
