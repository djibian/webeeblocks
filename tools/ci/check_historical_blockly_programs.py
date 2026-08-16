#!/usr/bin/env python3
"""Validate the historical Blockly fixtures against the vendored runtime.

This deliberately does not modernize Blockly. It protects the six programs that
serve as our compatibility oracle while the Webots R2025a migration progresses.
"""

from __future__ import annotations

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

EXPECTED_PROGRAMS = (
    "BoxWithDistSensor.xml",
    "BoxWithEncoders.xml",
    "BoxWithGyroGPS.xml",
    "BoxWithLightSensor.xml",
    "myFile.xml",
    "sensorProbing.xml",
)

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
    for filename in EXPECTED_PROGRAMS:
        path = PROGRAM_DIR / filename
        if not path.is_file():
            failures.append(f"missing historical fixture: {path.relative_to(ROOT)}")
            continue
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
        print(f"  {filename}: {len(types)} types" + (f" -> {', '.join(types)}" if types else ""))

    if failures:
        print("\nFAIL", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("\nPASS: all six historical XML fixtures are well-formed, every loaded JavaScript file parses, and every used block type has a definition and Python generator loaded by blockly.html.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
