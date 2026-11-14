#!/usr/bin/env python3
"""Test-only Blockly Activity 3 world; reuse already-qualified native A3 composition.

No student catalogue activation or modified physical runtime is involved.
"""
from __future__ import annotations
import hashlib
from pathlib import Path
import prepare_classroom_orientation_flight as flight

ROOT=flight.ROOT
WORLD=ROOT/'worlds/ci_classroom_orientation_pupil.wbt'
PROJECT=ROOT/'worlds/.ci_classroom_orientation_pupil.wbproj'
MARKER='# WEBEEBLOCKS_ORIENTATION_PUPIL_BLOCKLY_CI_ONLY'
PROJECT_BYTES=flight.PROJECT_BYTES

def compose(source:str)->str:
    original=flight.compose(source)
    if original.count(flight.MARKER)!=1 or original.count('window "orientation_flight_probe"')!=1:
        raise ValueError('unexpected source native Activity 3 flight world')
    result=original.replace(flight.MARKER,MARKER).replace(
        'window "orientation_flight_probe"','window "orientation_pupil_probe"')
    if (result.count(MARKER)!=1 or
        result.count('window "orientation_pupil_probe"')!=1 or
        result.count('controller "crazyflie_classroom_v2"')!=1 or
        'controller "crazyflie_runtime_v2"' in result or
        'DEF WEBEEBLOCKS_ORIENTATION_SCENE' in result or
        'DEF WEBEEBLOCKS_ALTITUDE_SCENE' in result or
        'DEF WEBEEBLOCKS_LEGACY_SCENE' in result):
        raise ValueError('student witness altered native identities')
    return result

def prepare()->None:
    if WORLD.exists() or PROJECT.exists():
        raise FileExistsError('refusing to overwrite existing A3 pupil witness files')
    created=compose(flight.ack.SOURCE.read_text(encoding='utf-8'))
    WORLD.write_text(created,encoding='utf-8')
    PROJECT.write_text(PROJECT_BYTES,encoding='utf-8')
    print('WEBEEBLOCKS_ORIENTATION_PUPIL_WORLD_SHA256 '+
          hashlib.sha256(created.encode()).hexdigest(),flush=True)

def cleanup()->None:
    if WORLD.exists():
        text=WORLD.read_text(encoding='utf-8')
        if text.count(MARKER)!=1 or 'window "orientation_pupil_probe"' not in text:
            raise ValueError('refusing to delete modified A3 pupil world')
        WORLD.unlink()
    if PROJECT.exists():
        if PROJECT.read_text(encoding='utf-8')!=PROJECT_BYTES:
            raise ValueError('refusing to delete modified A3 pupil Webots project')
        PROJECT.unlink()

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=('prepare','clean'))
    action=parser.parse_args().action
    if action=='prepare':prepare()
    else:cleanup()
