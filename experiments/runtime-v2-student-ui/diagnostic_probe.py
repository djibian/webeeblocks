#!/usr/bin/env python3
"""Bounded Lab instrumentation for the intermittent Blockly repeat tooltip gate.

This wrapper does not change product code or the gate oracle. It records DOM state
around the existing CDP hover, then delegates to the unchanged probe.main().
"""
import json
import os
from pathlib import Path

import probe

_ORIGINAL_HOVER = probe.Cdp.hover


def _snapshot(c, rect, phase):
    expr = """(() => {
      const r = %s;
      const x = r.x + r.width / 2, y = r.y + r.height / 2;
      const el = document.elementFromPoint(x, y);
      const tips = [...document.querySelectorAll('.blocklyTooltipDiv')].map(node => {
        const b = node.getBoundingClientRect();
        const s = getComputedStyle(node);
        return {
          className: node.className || '',
          text: (node.innerText || node.textContent || '').trim(),
          display: s.display,
          visibility: s.visibility,
          opacity: s.opacity,
          width: b.width,
          height: b.height,
          left: b.left,
          top: b.top,
          html: node.outerHTML.slice(0, 1200)
        };
      });
      return {
        phase: %s,
        point: {x, y},
        elementAtPoint: el ? {
          tag: el.tagName,
          className: el.className && (el.className.baseVal || el.className) || '',
          text: (el.textContent || '').trim().slice(0, 200),
          outerHTML: el.outerHTML ? el.outerHTML.slice(0, 1200) : ''
        } : null,
        tooltipDivs: tips,
        activeElement: document.activeElement ? {
          tag: document.activeElement.tagName,
          className: document.activeElement.className || '',
          text: (document.activeElement.textContent || '').trim().slice(0, 200)
        } : null
      };
    })()""" % (json.dumps(rect), json.dumps(phase))
    return c.eval(expr)


def diagnostic_hover(self, rect):
    out = Path(os.environ.get('WEBEEBLOCKS_CI_ARTIFACT_DIR', '.')) / 'tooltip-hover-diagnostic.json'
    observations = []
    try:
        observations.append(_snapshot(self, rect, 'before_hover'))
        _ORIGINAL_HOVER(self, rect)
        observations.append(_snapshot(self, rect, 'immediately_after_hover'))
    finally:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(observations, ensure_ascii=False, indent=2), encoding='utf-8')


probe.Cdp.hover = diagnostic_hover

if __name__ == '__main__':
    probe.main()
