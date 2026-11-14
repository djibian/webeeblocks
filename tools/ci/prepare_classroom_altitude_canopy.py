#!/usr/bin/env python3
"""CI-only native canopy mission world; reject unrecognized cleanup targets."""
from __future__ import annotations
import hashlib
from pathlib import Path

import prepare_classroom_altitude_scene_ack as ack

ROOT = ack.ROOT
WORLD = ROOT / 'worlds/ci_classroom_altitude_canopy.wbt'
PROJECT = ROOT / 'worlds/.ci_classroom_altitude_canopy.wbproj'
MARKER = '# WEBEEBLOCKS_ALTITUDE_CANOPY_FLIGHT_CI_ONLY'
PROJECT_BYTES = 'Webots Project File version R2025a\nrobotWindow: Crazyflie WebeeBlocks\n'


def compose(source: str) -> str:
    original = ack.compose(source)
    if original.count('window "altitude_scene_ack_probe"') != 1 or original.count(ack.MARKER) != 1:
        raise ValueError('cannot isolate exact native canopy browser')
    candidate = original.replace('window "altitude_scene_ack_probe"', 'window "altitude_canopy_probe"')
    candidate = candidate.replace(ack.MARKER, MARKER)
    if (candidate.count('controller "crazyflie_classroom_v2"') != 1 or
            'controller "crazyflie_runtime_v2"' in candidate or
            'DEF WEBEEBLOCKS_ALTITUDE_SCENE' in candidate or
            candidate.count('window "altitude_canopy_probe"') != 1):
        raise ValueError('canopy mission world has unsafe roles/preloaded scene')
    return candidate


def prepare() -> None:
    if WORLD.exists() or PROJECT.exists():
        raise FileExistsError('refusing to overwrite existing canopy CI world/project')
    created = compose(ack.SOURCE.read_text(encoding='utf-8'))
    WORLD.write_text(created, encoding='utf-8')
    PROJECT.write_text(PROJECT_BYTES, encoding='utf-8')
    print('WEBEEBLOCKS_CANOPY_CI_WORLD_SHA256 ' +
          hashlib.sha256(created.encode('utf-8')).hexdigest(), flush=True)


def cleanup() -> None:
    if WORLD.exists():
        raw = WORLD.read_text(encoding='utf-8')
        if raw.count(MARKER) != 1 or 'window "altitude_canopy_probe"' not in raw:
            raise ValueError('refusing to delete an unrecognized canopy world')
        WORLD.unlink()
    if PROJECT.exists():
        if PROJECT.read_text(encoding='utf-8') != PROJECT_BYTES:
            raise ValueError('refusing to delete an unrecognized canopy project')
        PROJECT.unlink()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('action',choices=('prepare','clean'))
    args = parser.parse_args()
    if args.action == 'prepare': prepare()
    else: cleanup()
