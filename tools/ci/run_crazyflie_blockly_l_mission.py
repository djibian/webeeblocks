#!/usr/bin/env python3
"""Prove Blockly -> semantic Crazyflie mission, then inject it into the shared L-course executor.

This intentionally does not generate student-facing Python. Blockly is only the UI;
the contract produced here is the semantic command list consumed by the already-
validated C executor.
"""

from __future__ import annotations

import html
import json
import math
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
FIXTURE = ROOT / "controllers" / "Blockly_Programs" / "CrazyflieL.xml"
L_SOURCE = ROOT / "controllers" / "crazyflie_l_course" / "crazyflie_l_course.c"
ARTIFACT_DIR = ROOT / "ci-artifacts" / "crazyflie-blockly-l"
MISSION_PATH = ARTIFACT_DIR / "mission.json"
RESULT_RE = re.compile(r'<pre id="mission-result">(.*?)</pre>', re.DOTALL)

EXPECTED = [
    {"type": "TAKEOFF", "value": 1.0},
    {"type": "FORWARD", "value": 1.0},
    {"type": "TURN", "value": math.pi / 2.0},
    {"type": "FORWARD", "value": 1.0},
    {"type": "LAND", "value": 0.0},
]


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
    raise RuntimeError("no Chrome/Chromium executable found")


def build_harness() -> str:
    parser = ScriptParser()
    parser.feed(HTML_PATH.read_text(encoding="utf-8"))
    if "google-blockly-31ee4ea/blocks/crazyflie.js" not in parser.sources:
        raise RuntimeError("blockly.html does not load the Crazyflie semantic block module")

    script_tags = "\n".join(f'<script src="{html.escape(src)}"></script>' for src in parser.sources)
    xml_text = FIXTURE.read_text(encoding="utf-8")
    payload = json.dumps(xml_text)

    return f"""<!doctype html>
<html><head><meta charset=\"utf-8\">{script_tags}</head>
<body><pre id=\"mission-result\">NOT_RUN</pre>
<script>
(function() {{
  const result = {{ok: false}};
  try {{
    const workspace = new Blockly.Workspace();
    Blockly.Xml.domToWorkspace(Blockly.Xml.textToDom({payload}), workspace);
    const mission = WebeeBlocksCrazyflie.workspaceToMission(workspace);

    // One explicit fail-closed check: a non-Crazyflie top-level block must be rejected.
    const invalid = new Blockly.Workspace();
    invalid.newBlock('math_number');
    let invalidRejected = false;
    try {{ WebeeBlocksCrazyflie.workspaceToMission(invalid); }}
    catch (error) {{ invalidRejected = true; }}
    invalid.dispose();

    result.ok = true;
    result.mission = mission;
    result.invalidRejected = invalidRejected;
    result.topBlocks = workspace.getTopBlocks(false).length;
    workspace.dispose();
  }} catch (error) {{
    result.error = String(error && error.stack ? error.stack : error);
  }}
  document.getElementById('mission-result').textContent = JSON.stringify(result);
}})();
</script></body></html>"""


def parse_browser_output(stdout: str) -> dict[str, object]:
    match = RESULT_RE.search(stdout)
    if not match:
        raise RuntimeError("browser did not emit mission-result")
    raw = html.unescape(match.group(1))
    if raw == "NOT_RUN":
        raise RuntimeError("Blockly mission harness did not run")
    return json.loads(raw)


def run_browser(harness_path: Path) -> dict[str, object]:
    command = [
        chrome_executable(), "--headless=new", "--no-sandbox", "--disable-gpu",
        "--disable-dev-shm-usage", "--disable-background-networking",
        "--allow-file-access-from-files", "--virtual-time-budget=5000", "--dump-dom",
        harness_path.as_uri(),
    ]
    process = subprocess.Popen(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=30)
    except subprocess.TimeoutExpired:
        # Hosted Chrome can finish --dump-dom then linger while shutting down.
        # Keep the already-produced DOM and accept it only if the mission payload
        # is actually present, matching the established historical Blockly oracle.
        timed_out = True
        process.kill()
        stdout, stderr = process.communicate()

    try:
        parsed = parse_browser_output(stdout)
    except RuntimeError as exc:
        if timed_out:
            raise RuntimeError(
                f"browser timed out before emitting mission-result: {stderr.strip()}"
            ) from exc
        if process.returncode:
            raise RuntimeError(
                f"browser exited with {process.returncode}: {stderr.strip()}"
            ) from exc
        raise

    if not timed_out and process.returncode:
        raise RuntimeError(f"browser exited with {process.returncode}: {stderr.strip()}")
    if timed_out:
        print(
            "WARN: browser required forced shutdown after emitting mission-result; accepting verified DOM payload.",
            file=sys.stderr,
        )
    return parsed


def same_mission(actual: object) -> bool:
    if not isinstance(actual, list) or len(actual) != len(EXPECTED):
        return False
    for got, expected in zip(actual, EXPECTED):
        if not isinstance(got, dict) or got.get("type") != expected["type"]:
            return False
        try:
            value = float(got.get("value"))
        except (TypeError, ValueError):
            return False
        if not math.isclose(value, expected["value"], rel_tol=0.0, abs_tol=1e-12):
            return False
    return True


def inject_mission_into_l_course(mission: list[dict[str, object]]) -> None:
    enum = {
        "TAKEOFF": "WEBEEBLOCKS_COMMAND_TAKEOFF",
        "FORWARD": "WEBEEBLOCKS_COMMAND_FORWARD",
        "TURN": "WEBEEBLOCKS_COMMAND_TURN",
        "LAND": "WEBEEBLOCKS_COMMAND_LAND",
    }
    rows = [
        f"    {{{enum[str(item['type'])]}, {float(item['value']):.17g}}},"
        for item in mission
    ]
    replacement = "static const webeeblocks_command_t mission[] = {\n" + "\n".join(rows) + "\n  };"

    source = L_SOURCE.read_text(encoding="utf-8")
    pattern = re.compile(
        r"static const webeeblocks_command_t mission\[\] = \{.*?\n  \};",
        re.DOTALL,
    )
    updated, count = pattern.subn(replacement, source, count=1)
    if count != 1:
        raise RuntimeError("could not replace the L-course semantic mission initializer")
    L_SOURCE.write_text(updated, encoding="utf-8")


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
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
        print(f"FAIL: Blockly mission extraction failed: {result.get('error')}", file=sys.stderr)
        return 1
    if result.get("invalidRejected") is not True:
        print("FAIL: unsupported Blockly block was not rejected fail-closed", file=sys.stderr)
        return 1
    mission = result.get("mission")
    if not same_mission(mission):
        print(f"FAIL: semantic mission differs from L oracle: {mission!r}", file=sys.stderr)
        return 1

    assert isinstance(mission, list)
    MISSION_PATH.write_text(json.dumps(mission, indent=2) + "\n", encoding="utf-8")
    inject_mission_into_l_course(mission)
    print("PASS: Blockly produced exactly TAKEOFF, FORWARD(1m), TURN(+90deg), FORWARD(1m), LAND.")
    print(f"Mission artifact: {MISSION_PATH.relative_to(ROOT)}")
    print("PASS: the exact semantic list was injected into the existing shared STOP L-course executor source.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
