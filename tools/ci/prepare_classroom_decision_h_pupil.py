#!/usr/bin/env python3
"""CI-only A4 pupil world from the exact typed school classroom source.

Uses one ordinary school flight controller, zero preloaded scenes, and a
browser-only Blockly/.wbb witness; no changes to the physical flight binary.
"""
from __future__ import annotations
import hashlib
from pathlib import Path
import prepare_classroom_altitude_scene_ack as ack

ROOT=ack.ROOT
WORLD=ROOT/'worlds/ci_classroom_decision_h_pupil.wbt'
PROJECT=ROOT/'worlds/.ci_classroom_decision_h_pupil.wbproj'
MARKER='# WEBEEBLOCKS_A4_BLOCKLY_PUPIL_CI_ONLY'
PROJECT_TEXT='Webots Project File version R2025a\nrobotWindow: Crazyflie WebeeBlocks\n'


def compose(source:str)->str:
    original=ack.compose(source)
    if (original.count(ack.MARKER)!=1 or
        original.count('window "altitude_scene_ack_probe"')!=1 or
        original.count('controller "crazyflie_classroom_v2"')!=1):
        raise ValueError('invalid native school startup source')
    result=original.replace(ack.MARKER,MARKER).replace(
        'window "altitude_scene_ack_probe"',
        'window "decision_h_pupil_probe"')
    if (result.count(MARKER)!=1 or
        result.count('window "decision_h_pupil_probe"')!=1 or
        result.count('controller "crazyflie_classroom_v2"')!=1 or
        'controller "crazyflie_runtime_v2"' in result or
        'DEF WEBEEBLOCKS_DECISION_A_SCENE' in result or
        'DEF WEBEEBLOCKS_DECISION_B_SCENE' in result or
        'DEF WEBEEBLOCKS_LEGACY_SCENE' in result or
        'DEF WEBEEBLOCKS_ORIENTATION_SCENE' in result):
        raise ValueError('not a unique empty typed startup world')
    return result


def prepare():
    if WORLD.exists() or PROJECT.exists():
        raise FileExistsError('refusing overwrite of existing A4 pupil CI world')
    body=compose(ack.SOURCE.read_text(encoding='utf-8'))
    WORLD.write_text(body,encoding='utf-8')
    PROJECT.write_text(PROJECT_TEXT,encoding='utf-8')
    print('A4_PUPIL_WORLD_SHA256 '+
          hashlib.sha256(body.encode('utf-8')).hexdigest(),flush=True)


def cleanup():
    if WORLD.exists():
        actual=WORLD.read_text(encoding='utf-8')
        expected=compose(ack.SOURCE.read_text(encoding='utf-8'))
        if actual!=expected or actual.count(MARKER)!=1:
            raise ValueError('refusing removal of modified A4 pupil world')
        WORLD.unlink()
    if PROJECT.exists():
        if PROJECT.read_text(encoding='utf-8')!=PROJECT_TEXT:
            raise ValueError('refusing removal of modified A4 pupil Webots project')
        PROJECT.unlink()


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=('prepare','clean'))
    args=parser.parse_args()
    if args.action=='prepare':prepare()
    else:cleanup()
