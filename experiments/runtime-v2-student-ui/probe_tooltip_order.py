#!/usr/bin/env python3
"""Falsify whether the direction dropdown lifecycle destabilizes real tooltips."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import probe


def _visible_tooltip(cdp: probe.Cdp) -> list[dict[str, object]]:
    overlay = cdp.eval(probe.VISIBLE_OVERLAY)
    if not isinstance(overlay, list):
        raise RuntimeError('visible-overlay probe did not return a list')
    return [
        entry for entry in overlay
        if isinstance(entry, dict)
        and ('tooltip' in str(entry.get('className', '')).lower())
        and str(entry.get('text', '')).strip()
    ]


def _wait_real_tooltip(cdp: probe.Cdp, timeout: float = 5.0) -> list[dict[str, object]]:
    end = time.time() + timeout
    while time.time() < end:
        tooltip = _visible_tooltip(cdp)
        if tooltip:
            return tooltip
        time.sleep(.1)
    raise RuntimeError('clean-workspace repeat tooltip did not become visible and non-empty within 5.0s')


def _wait_non_tooltip_overlays_closed(cdp: probe.Cdp, timeout: float = 2.0) -> None:
    end = time.time() + timeout
    blocking: list[dict[str, object]] = []
    while time.time() < end:
        overlay = cdp.eval(probe.VISIBLE_OVERLAY)
        blocking = [
            entry for entry in overlay
            if isinstance(entry, dict)
            and 'tooltip' not in str(entry.get('className', '')).lower()
            and str(entry.get('text', '')).strip()
        ]
        if not blocking:
            return
        time.sleep(.05)
    raise RuntimeError('direction dropdown did not close independently: ' + json.dumps(blocking, ensure_ascii=False))


def _artifact_path() -> Path:
    directory = Path(os.environ.get('WEBEEBLOCKS_CI_ARTIFACT_DIR', '/tmp'))
    directory.mkdir(parents=True, exist_ok=True)
    return directory / 'tooltip-order-clean.json'


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--fixture', required=True)
    args = parser.parse_args()

    cdp = probe.Cdp(probe.wait_target()['webSocketDebuggerUrl'])
    cdp.call('Runtime.enable')
    cdp.call('Page.enable')
    cdp.call('Emulation.setDeviceMetricsOverride', {
        'width': 1366,
        'height': 768,
        'deviceScaleFactor': 1,
        'mobile': False,
    })

    end = time.time() + 30
    while time.time() < end:
        ready = cdp.eval("({v:window.Blockly&&Blockly.VERSION,w:!!window.workspace})")
        if ready and ready.get('v') == '13.2.1' and ready.get('w'):
            break
        time.sleep(.2)
    else:
        raise RuntimeError('Blockly 13.2.1 workspace did not initialize for clean tooltip probe')

    fixture = Path(args.fixture).read_text(encoding='utf-8')
    cdp.eval(
        "workspace.clear();Blockly.Xml.domToWorkspace(Blockly.utils.xml.textToDom(%s),workspace);Blockly.svgResize(workspace);true"
        % json.dumps(fixture)
    )
    time.sleep(.5)

    # Add only the deterministic locale-evidence blocks needed to expose the real
    # direction field. No dropdown/widget interaction occurs before the tooltip.
    rendered = cdp.eval(probe.RENDER_LOCALE)
    if not isinstance(rendered, dict) or not rendered.get('directionFieldRect'):
        raise RuntimeError('rendered direction field unavailable for ordering probe')
    time.sleep(.5)

    before = cdp.eval(probe.VISIBLE_OVERLAY)
    blocking_before = [
        entry for entry in before
        if isinstance(entry, dict)
        and 'tooltip' not in str(entry.get('className', '')).lower()
        and str(entry.get('text', '')).strip()
    ]
    if blocking_before:
        raise RuntimeError('clean tooltip probe started with a blocking popup: ' + json.dumps(blocking_before, ensure_ascii=False))

    hover_rect = cdp.eval(probe.REPEAT_HOVER_RECT)
    if not isinstance(hover_rect, dict):
        raise RuntimeError('clean tooltip hover rectangle unavailable')
    cdp.hover(hover_rect)
    tooltip = _wait_real_tooltip(cdp)
    tooltip_text = ' '.join(str(entry.get('text', '')) for entry in tooltip).strip().lower()
    if not tooltip_text or 'repeat' in tooltip_text:
        raise RuntimeError('clean-workspace repeat tooltip is empty or English: ' + tooltip_text)

    # Leave the repeat path using the already hit-tested outside point. This uses
    # ordinary browser input only; no Blockly tooltip API is called.
    cdp.call('Input.dispatchMouseEvent', {
        'type': 'mouseMoved',
        'x': hover_rect['outsideX'],
        'y': hover_rect['outsideY'],
    })
    time.sleep(.1)

    cdp.click(rendered['directionFieldRect'])
    time.sleep(.4)
    direction_menu = cdp.eval(probe.VISIBLE_OVERLAY)
    if not isinstance(direction_menu, list) or not direction_menu:
        raise RuntimeError('real direction dropdown did not open after clean tooltip proof')
    menu_text = ' '.join(
        str(entry.get('text', '')) for entry in direction_menu if isinstance(entry, dict)
    ).lower()
    for expected in ('devant', 'derrière', 'à gauche', 'à droite', 'au-dessus'):
        if expected not in menu_text:
            raise RuntimeError('real direction dropdown lacks ' + expected + ': ' + menu_text)

    cdp.key('Escape')
    _wait_non_tooltip_overlays_closed(cdp)

    evidence = {
        'ordering': 'tooltip-before-direction-dropdown',
        'tooltipText': tooltip_text,
        'tooltipVisible': True,
        'directionMenuText': menu_text,
        'directionMenuOpened': True,
        'directionMenuClosed': True,
    }
    _artifact_path().write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8',
    )
    print('WEBEEBLOCKS_TOOLTIP_ORDER ' + json.dumps(evidence, ensure_ascii=False), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
