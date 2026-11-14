#!/usr/bin/env python3
"""CI-only Blockly Activity 2 world: never overwrite or delete unknown files."""
from __future__ import annotations
import hashlib
from pathlib import Path
import prepare_classroom_altitude_canopy as canopy

ROOT=canopy.ROOT
WORLD=ROOT/'worlds/ci_classroom_altitude_pupil.wbt'
PROJECT=ROOT/'worlds/.ci_classroom_altitude_pupil.wbproj'
MARKER='# WEBEEBLOCKS_ALTITUDE_PUPIL_BLOCKLY_CI_ONLY'
PROJECT_BYTES=canopy.PROJECT_BYTES

def compose(source: str) -> str:
    original=canopy.compose(source)
    if original.count(canopy.MARKER)!=1 or original.count('window "altitude_canopy_probe"')!=1:
        raise ValueError('unexpected original native school-world identity')
    result=original.replace(canopy.MARKER,MARKER).replace(
        'window "altitude_canopy_probe"','window "altitude_pupil_probe"')
    if (result.count(MARKER)!=1 or result.count('window "altitude_pupil_probe"')!=1 or
            result.count('controller "crazyflie_classroom_v2"')!=1 or
            'controller "crazyflie_runtime_v2"' in result or
            'DEF WEBEEBLOCKS_ALTITUDE_SCENE' in result):
        raise ValueError('pupil witness did not isolate real native roles')
    return result

def prepare() -> None:
    if WORLD.exists() or PROJECT.exists():
        raise FileExistsError('refusing to overwrite existing pupil CI world')
    text=compose(canopy.ack.SOURCE.read_text(encoding='utf-8'))
    WORLD.write_text(text,encoding='utf-8')
    PROJECT.write_text(PROJECT_BYTES,encoding='utf-8')
    print('WEBEEBLOCKS_A2_PUPIL_WORLD_SHA256 '+hashlib.sha256(text.encode()).hexdigest(),flush=True)

def cleanup() -> None:
    if WORLD.exists():
        text=WORLD.read_text(encoding='utf-8')
        if text.count(MARKER)!=1 or 'window "altitude_pupil_probe"' not in text:
            raise ValueError('refusing cleanup of modified witness world')
        WORLD.unlink()
    if PROJECT.exists():
        if PROJECT.read_text(encoding='utf-8')!=PROJECT_BYTES:
            raise ValueError('refusing cleanup of unknown Webots project')
        PROJECT.unlink()

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument('action',choices=['prepare','clean'])
    args=p.parse_args()
    if args.action=='prepare':prepare()
    else:cleanup()
