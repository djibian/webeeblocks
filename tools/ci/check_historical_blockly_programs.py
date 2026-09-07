#!/usr/bin/env python3
"""Validate the historical Blockly fixtures against the vendored runtime.

This deliberately does not modernize Blockly. It protects the six programs that
serve as our compatibility oracle while the Webots R2025a migration progresses.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROGRAM_DIR = ROOT / "controllers" / "Blockly_Programs"
ROBOT_WINDOW_DIR = ROOT / "plugins" / "robot_windows" / "blockly"
HTML_PATH = ROBOT_WINDOW_DIR / "blockly.html"

# Git blob IDs of the untouched historical fixtures. If a pedagogical example
# needs to evolve, add a new fixture rather than silently rewriting this oracle.
EXPECTED_PROGRAM_BLOBS = {
    "BoxWithDistSensor.xml": "790a65387c1694e9751873da4b093ed1fa89808a",
    "BoxWithEncoders.xml": "c1a7275701cd9cecb6f3e4364b45ece87c13e0cd",
    "BoxWithGyroGPS.xml": "0e4cc6d9a09c957cab88f927d289e66c07ebf8b4",
    "BoxWithLightSensor.xml": "da68a043b7f18883a8e02748e531a0e1ce1d2b73",
    "myFile.xml": "cd87c89464700deba7b900aee0baf615881730d5",
    "sensorProbing.xml": "e836921a2d81e7726375e2cedd98e9cf4a0b1816",
}
EXPECTED_PROGRAMS = tuple(EXPECTED_PROGRAM_BLOBS)

TYPE_JSON_RE = re.compile(r"[\"']type[\"']\s*:\s*[\"']([^\"']+)[\"']")
BLOCK_REGISTRY_RE = re.compile(r"Blockly\.Blocks\s*\[\s*[\"']([^\"']+)[\"']\s*\]")
PYTHON_REGISTRY_RE = re.compile(r"Blockly\.Python\s*\[\s*[\"']([^\"']+)[\"']\s*\]")


class ScriptParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.sources: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "script":
            return
        src = dict(attrs).get("src")
        if src:
            self.sources.append(src)


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    header = f"blob {len(data)}\0".encode()
    return hashlib.sha1(header + data).hexdigest()


def loaded_script_paths() -> list[Path]:
    parser = ScriptParser()
    parser.feed(HTML_PATH.read_text(encoding="utf-8"))
    paths: list[Path] = []
    for source in parser.sources:
        path = (ROBOT_WINDOW_DIR / source).resolve()
        try:
            path.relative_to(ROBOT_WINDOW_DIR.resolve())
        except ValueError as exc:
            raise RuntimeError(f"script escapes Robot Window directory: {source}") from exc
        paths.append(path)
    return paths


def categorized_sources(paths: list[Path]) -> tuple[list[Path], list[Path]]:
    block_sources = [path for path in paths if "/blocks/" in path.as_posix()]
    generator_sources = [path for path in paths if "/generators/python/" in path.as_posix()]
    return block_sources, generator_sources


def block_types_in_program(path: Path) -> set[str]:
    root = ET.parse(path).getroot()
    types: set[str] = set()
    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1]
        if tag in {"block", "shadow"}:
            block_type = element.attrib.get("type")
            if not block_type:
                raise RuntimeError(f"{path}: block/shadow without type")
            types.add(block_type)
    return types


def definitions_in_sources(paths: list[Path]) -> set[str]:
    definitions: set[str] = set()
    for path in paths:
        text = path.read_text(encoding="utf-8")
        definitions.update(TYPE_JSON_RE.findall(text))
        definitions.update(BLOCK_REGISTRY_RE.findall(text))
    return definitions


def generators_in_sources(paths: list[Path]) -> set[str]:
    generators: set[str] = set()
    for path in paths:
        generators.update(PYTHON_REGISTRY_RE.findall(path.read_text(encoding="utf-8")))
    return generators


def javascript_syntax_failures(paths: list[Path]) -> list[str]:
    failures: list[str] = []
    for path in paths:
        if not path.is_file() or path.suffix != ".js":
            continue
        result = subprocess.run(
            ["node", "--check", str(path)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        if result.returncode:
            output = result.stdout.strip().replace("\n", " | ")
            failures.append(f"JavaScript syntax error in {path.relative_to(ROOT)}: {output}")
    return failures


def main() -> int:
    failures: list[str] = []

    if not HTML_PATH.is_file():
        failures.append(f"missing Robot Window entry point: {HTML_PATH.relative_to(ROOT)}")
        loaded_sources: list[Path] = []
    else:
        loaded_sources = loaded_script_paths()
    block_sources, generator_sources = categorized_sources(loaded_sources)

    for label, sources in (("block", block_sources), ("Python generator", generator_sources)):
        if not sources:
            failures.append(f"blockly.html references no {label} source files")
        for source in sources:
            if not source.is_file():
                failures.append(f"referenced {label} source is missing: {source.relative_to(ROOT)}")

    for source in loaded_sources:
        if not source.is_file():
            failures.append(f"script loaded by blockly.html is missing: {source.relative_to(ROOT)}")
    failures.extend(javascript_syntax_failures(loaded_sources))

    used_by_program: dict[str, set[str]] = {}
    all_used: set[str] = set()
    fixture_blobs: dict[str, str] = {}
    for filename in EXPECTED_PROGRAMS:
        path = PROGRAM_DIR / filename
        if not path.is_file():
            failures.append(f"missing historical fixture: {path.relative_to(ROOT)}")
            continue

        actual_blob = git_blob_sha(path)
        fixture_blobs[filename] = actual_blob
        expected_blob = EXPECTED_PROGRAM_BLOBS[filename]
        if actual_blob != expected_blob:
            failures.append(
                f"historical fixture changed: {filename} has blob {actual_blob}, expected {expected_blob}"
            )

        try:
            types = block_types_in_program(path)
        except (ET.ParseError, RuntimeError) as exc:
            failures.append(f"invalid historical fixture {filename}: {exc}")
            continue
        used_by_program[filename] = types
        all_used.update(types)

    existing_block_sources = [path for path in block_sources if path.is_file()]
    existing_generator_sources = [path for path in generator_sources if path.is_file()]
    definitions = definitions_in_sources(existing_block_sources)
    generators = generators_in_sources(existing_generator_sources)

    missing_definitions = sorted(all_used - definitions)
    missing_generators = sorted(all_used - generators)
    if missing_definitions:
        failures.append("used block types without a loaded definition: " + ", ".join(missing_definitions))
    if missing_generators:
        failures.append("used block types without a loaded Python generator: " + ", ".join(missing_generators))

    print("Historical Blockly compatibility inventory")
    print(f"  fixtures required: {len(EXPECTED_PROGRAMS)}")
    print(f"  fixtures parsed:   {len(used_by_program)}")
    print(f"  unique block types used: {len(all_used)}")
    print(f"  JavaScript files loaded by blockly.html: {len([p for p in loaded_sources if p.suffix == '.js'])}")
    print(f"  loaded block source files: {len(existing_block_sources)}")
    print(f"  loaded Python generator files: {len(existing_generator_sources)}")
    for filename in EXPECTED_PROGRAMS:
        types = sorted(used_by_program.get(filename, set()))
        blob = fixture_blobs.get(filename, "missing")
        print(f"  {filename}: blob={blob}, {len(types)} types" + (f" -> {', '.join(types)}" if types else ""))

    if failures:
        print("\nFAIL", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("\nPASS: the six original XML fixtures are byte-for-byte preserved, well-formed, every loaded JavaScript file parses, and every used block type has a definition and Python generator loaded by blockly.html.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
