#!/usr/bin/env python3
"""CI-only real R2025a Activity 3 world from the exact classroom source."""
from __future__ import annotations

import hashlib
from pathlib import Path
import prepare_classroom_altitude_scene_ack as ack

ROOT=ack.ROOT
WORLD=ROOT/'worlds/ci_classroom_orientation_flight.wbt'
PROJECT=ROOT/'worlds/.ci_classroom_orientation_flight.wbproj'
MARKER='# WEBEEBLOCKS_ORIENTATION_FLIGHT_NATIVE_CI_ONLY'
PROJECT_BYTES='Webots Project File version R2025a\nrobotWindow: Crazyflie WebeeBlocks\n'

def compose(source: str)->str:
    original=ack.compose(source)
    if original.count(ack.MARKER)!=1 or original.count('window "altitude_scene_ack_probe"')!=1:
        raise ValueError('ambiguous original classroom scene-ACK world')
    result=original.replace(ack.MARKER,MARKER).replace(
        'window "altitude_scene_ack_probe"','window "orientation_flight_probe"')
    if (result.count(MARKER)!=1 or
        result.count('window "orientation_flight_probe"')!=1 or
        result.count('controller "crazyflie_classroom_v2"')!=1 or
        'controller "crazyflie_runtime_v2"' in result or
        'DEF WEBEEBLOCKS_ORIENTATION_SCENE' in result or
        'DEF WEBEEBLOCKS_ALTITUDE_SCENE' in result or
        'DEF WEBEEBLOCKS_LEGACY_SCENE' in result):
        raise ValueError('orientation flight world lost isolated native identities')
    return result

def prepare()->None:
    if WORLD.exists() or PROJECT.exists():
        raise FileExistsError('refusing overwrite of existing orientation CI world')
    result=compose(ack.SOURCE.read_text(encoding='utf-8'))
    WORLD.write_text(result,encoding='utf-8')
    PROJECT.write_text(PROJECT_BYTES,encoding='utf-8')
    print('WEBEEBLOCKS_ORIENTATION_FLIGHT_WORLD_SHA256 '+
          hashlib.sha256(result.encode()).hexdigest(),flush=True)

def cleanup()->None:
    if WORLD.exists():
        result=WORLD.read_text(encoding='utf-8')
        if result.count(MARKER)!=1 or 'window "orientation_flight_probe"' not in result:
            raise ValueError('refusing deletion of altered orientation CI world')
        WORLD.unlink()
    if PROJECT.exists():
        if PROJECT.read_text(encoding='utf-8')!=PROJECT_BYTES:
            raise ValueError('refusing deletion of altered Webots project')
        PROJECT.unlink()

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('command',choices=('prepare','clean'))
    args=parser.parse_args()
    if args.command=='prepare':prepare()
    else:cleanup()
