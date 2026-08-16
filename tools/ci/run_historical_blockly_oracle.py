#!/usr/bin/env python3
"""Execute the vendored Blockly 2020 runtime against the six historical XML fixtures.

The existing static gate proves that the files and registrations exist. This gate
loads the real browser bundles, deserializes every XML program into a Blockly
Workspace, runs Blockly.Python.workspaceToCode(), and compiles the resulting
Python with the current interpreter.
"""

from __future__ import annotations

import html
import json
import re
import shutil
import subprocess
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROBOT_WINDOW_DIR = ROOT / "plugins" / "robot_windows" / "blockly"
HTML_PATH = ROBOT_WINDOW_DIR / "blockly.html"
PROGRAM_DIR = ROOT / "controllers" / "Blockly_Programs"
PROGRAMS = (
    "BoxWithDistSensor.xml",
    "BoxWithEncoders.xml",
    "BoxWithGyroGPS.xml",
    "BoxWithLightSensor.xml",
    "myFile.xml",
    "sensorProbing.xml",
)
RESULT_RE = re.compile(r'<pre id="oracle-result">(.*?)</pre>', re.DOTALL)


class ScriptParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.sources: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "script":
            return
        src = dict(attrs).get("src")
        if src and src.startswith("google-blockly-31ee4ea/"):
            self.sources.append(src)


def chrome_executable() -> str:
    for candidate in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        path = shutil.which(candidate)
        if path:
            return path
    raise RuntimeError("no Chrome/Chromium executable found on the CI runner")


def build_harness() -> str:
    parser = ScriptParser()
    parser.feed(HTML_PATH.read_text(encoding="utf-8"))
    if not parser.sources:
        raise RuntimeError("blockly.html did not expose any vendored Blockly scripts")

    script_tags = "\n".join(f'<script src="{html.escape(src)}"></script>' for src in parser.sources)
    programs = {
        name: (PROGRAM_DIR / name).read_text(encoding="utf-8")
        for name in PROGRAMS
    }
    payload = json.dumps(programs)

    return f"""<!doctype html>
<html>
<head><meta charset=\"utf-8\">{script_tags}</head>
<body><pre id=\"oracle-result\">NOT_RUN</pre>
<script>
(function() {{
  const programs = {payload};
  const result = {{ok: true, programs: {{}}}};
  try {{
    for (const [name, xmlText] of Object.entries(programs)) {{
      const workspace = new Blockly.Workspace();
      const xml = Blockly.Xml.textToDom(xmlText);
      Blockly.Xml.domToWorkspace(xml, workspace);
      const code = Blockly.Python.workspaceToCode(workspace);
      result.programs[name] = {{code: code, topBlocks: workspace.getTopBlocks(false).length}};
      workspace.dispose();
    }}
  }} catch (error) {{
    result.ok = false;
    result.error = String(error && error.stack ? error.stack : error);
  }}
  document.getElementById('oracle-result').textContent = JSON.stringify(result);
}})();
</script></body></html>"""


def run_browser(harness_path: Path) -> dict[str, object]:
    chrome = chrome_executable()
    command = [
        chrome,
        "--headless=new",
        "--no-sandbox",
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--allow-file-access-from-files",
        "--virtual-time-budget=5000",
        "--dump-dom",
        harness_path.as_uri(),
    ]
    result = subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=30,
    )
    if result.returncode:
        raise RuntimeError(
            f"headless browser exited with {result.returncode}: {result.stderr.strip()}"
        )
    match = RESULT_RE.search(result.stdout)
    if not match:
        raise RuntimeError("headless browser did not emit oracle-result")
    raw = html.unescape(match.group(1))
    if raw == "NOT_RUN":
        raise RuntimeError("Blockly harness JavaScript did not run")
    return json.loads(raw)


def main() -> int:
    harness = build_harness()
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".html", dir=ROBOT_WINDOW_DIR, encoding="utf-8", delete=False
    ) as handle:
        handle.write(harness)
        harness_path = Path(handle.name)

    try:
        result = run_browser(harness_path)
    finally:
        harness_path.unlink(missing_ok=True)

    if not result.get("ok"):
        print(f"FAIL: Blockly browser execution failed: {result.get('error')}", file=sys.stderr)
        return 1

    generated = result.get("programs")
    if not isinstance(generated, dict) or set(generated) != set(PROGRAMS):
        print("FAIL: browser result does not contain exactly the six historical programs", file=sys.stderr)
        return 1

    nonempty = 0
    print("Historical Blockly browser oracle")
    for name in PROGRAMS:
        entry = generated[name]
        if not isinstance(entry, dict):
            print(f"FAIL: malformed browser result for {name}", file=sys.stderr)
            return 1
        code = entry.get("code")
        if not isinstance(code, str):
            print(f"FAIL: generated code is not text for {name}", file=sys.stderr)
            return 1
        if code.strip():
            nonempty += 1
            try:
                compile(code, f"<Blockly:{name}>", "exec")
            except SyntaxError as exc:
                print(f"FAIL: generated Python is invalid for {name}: {exc}", file=sys.stderr)
                return 1
        print(
            f"  {name}: topBlocks={entry.get('topBlocks')}, "
            f"pythonBytes={len(code.encode('utf-8'))}"
        )

    if nonempty != 5:
        print(f"FAIL: expected five non-empty generated programs, got {nonempty}", file=sys.stderr)
        return 1

    print("PASS: Blockly 2020 loaded all six historical XML fixtures and generated syntactically valid Python for the five non-empty programs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
