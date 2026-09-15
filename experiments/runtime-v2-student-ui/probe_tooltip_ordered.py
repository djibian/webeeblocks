#!/usr/bin/env python3
"""Run the full student-UI oracle with the real tooltip before the dropdown.

This is a fail-closed experimental refactoring of ``probe.main``: it moves only
one contiguous interaction block while preserving every other product-facing
assertion from the canonical probe.  The transformation is intentionally exact
and aborts if the source shape changes.
"""

from __future__ import annotations

import hashlib
import inspect
import json

import probe
import probe_tooltip_ready


START = "    c.click(rendered['directionFieldRect']); time.sleep(.4)\n"
END = "    c.screenshot(screenshot.with_name('repeat-tooltip-1366x768.png'))\n"

REORDERED = r'''    # #405 causal repair: prove the real repeat tooltip before any dropdown
    # lifecycle can affect Blockly's tooltip input state.  This uses the same exact
    # bound path, real CDP hover and visible/non-empty/non-English product oracle.
    repeat_before_dropdown=c.eval(REPEAT_HOVER_RECT)
    c.hover(repeat_before_dropdown)
    tooltip=[]
    end=time.time()+5.0
    while time.time()<end:
        overlay=c.eval(VISIBLE_OVERLAY)
        tooltip=[entry for entry in overlay if ('Tooltip' in entry['className'] or 'tooltip' in entry['className'].lower()) and entry['text'].strip()]
        if tooltip: break
        time.sleep(.1)
    if not tooltip: raise RuntimeError('real repeat tooltip did not become visible and non-empty before dropdown within 5.0s')
    tooltip_text=' '.join(entry['text'] for entry in tooltip).lower()
    if not tooltip_text or 'repeat' in tooltip_text:
        raise RuntimeError('real repeat tooltip is empty or English: '+tooltip_text)
    c.screenshot(screenshot.with_name('repeat-tooltip-1366x768.png'))

    # Leave the exact tooltip path through ordinary browser input, then require
    # the visible tooltip lifecycle to have closed before opening the real menu.
    c.call('Input.dispatchMouseEvent',{'type':'mouseMoved','x':repeat_before_dropdown['outsideX'],'y':repeat_before_dropdown['outsideY']})
    tooltip_overlay=[]
    tooltip_end=time.time()+2.0
    while time.time()<tooltip_end:
        tooltip_overlay=[entry for entry in c.eval(VISIBLE_OVERLAY) if 'tooltip' in entry['className'].lower() and entry['text'].strip()]
        if not tooltip_overlay: break
        time.sleep(.05)
    if tooltip_overlay:
        raise RuntimeError('repeat tooltip did not close before direction dropdown: '+json.dumps(tooltip_overlay,ensure_ascii=False))

    # Test the dropdown independently, after the tooltip acceptance oracle has
    # already passed.  No tooltip result is retried or manufactured from this path.
    c.click(rendered['directionFieldRect']); time.sleep(.4)
    direction_menu=c.eval(VISIBLE_OVERLAY)
    if not direction_menu: raise RuntimeError('real direction dropdown did not open after tooltip proof')
    menu_text=' '.join(entry['text'] for entry in direction_menu).lower()
    for expected in ('devant','derrière','à gauche','à droite','au-dessus'):
        if expected not in menu_text:
            raise RuntimeError('real direction dropdown lacks '+expected+': '+menu_text)
    c.screenshot(screenshot.with_name('direction-menu-1366x768.png'))
    c.key('Escape')
    blocking_overlay=[]
    overlay_end=time.time()+2.0
    while time.time()<overlay_end:
        blocking_overlay=[
            entry for entry in c.eval(VISIBLE_OVERLAY)
            if 'tooltip' not in entry['className'].lower() and entry['text'].strip()
        ]
        if not blocking_overlay: break
        time.sleep(.05)
    if blocking_overlay:
        raise RuntimeError('direction dropdown overlay did not close independently: '+json.dumps(blocking_overlay,ensure_ascii=False))
'''


def ordered_main():
    source = inspect.getsource(probe.main)
    if source.count(START) != 1 or source.count(END) != 1:
        raise RuntimeError('canonical probe interaction block shape changed; refusing ordered transformation')
    start = source.index(START)
    end = source.index(END, start) + len(END)
    if end <= start:
        raise RuntimeError('canonical probe interaction block bounds are invalid')

    original_block = source[start:end]
    required_fragments = (
        "real direction dropdown did not open",
        "real repeat tooltip did not become visible and non-empty after hover within 5.0s",
        "c.eval(REPEAT_HOVER_RECT)",
        "c.hover(repeat_after_close)",
    )
    missing = [fragment for fragment in required_fragments if fragment not in original_block]
    if missing:
        raise RuntimeError('canonical interaction block no longer matches the proven precondition: '+json.dumps(missing))

    transformed = source[:start] + REORDERED + source[end:]
    print('WEBEEBLOCKS_TOOLTIP_ORDERED_SOURCE ' + json.dumps({
        'canonicalMainSha256': hashlib.sha256(source.encode('utf-8')).hexdigest(),
        'orderedMainSha256': hashlib.sha256(transformed.encode('utf-8')).hexdigest(),
        'removedBlockSha256': hashlib.sha256(original_block.encode('utf-8')).hexdigest(),
        'ordering': 'tooltip-before-direction-dropdown-single-flow',
    }, sort_keys=True), flush=True)

    namespace = dict(probe.__dict__)
    exec(compile(transformed, probe.__file__, 'exec'), namespace)
    return namespace['main']()


if __name__ == '__main__':
    try:
        raise SystemExit(ordered_main())
    except BaseException:
        probe_tooltip_ready._record_terminal_diagnostics()
        raise
