#!/usr/bin/env python3
"""Validate the historical Blockly fixtures against the vendored runtime.

This deliberately does not modernize Blockly. It protects the six programs that
serve as our compatibility oracle while the Webots R2025a migration progresses.
"""

from __future__ import annotations

import re
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
        attributes = dict(attrs)
        src = attributes.get("src")
        if src:
            self.sources.append(src)


def local_script_paths() -> tuple[list[Path], list[Path]]:
    parser = ScriptParser()
    parser.feed(HTML_PATH.read_text(encoding="utf-8"))

    block_sources: list[Path] = []
    generator_sources: list[Path] = []
    for source in parser.sources:
        normalized = source.replace("\\", "/")
        path = (ROBOT_WINDOW_DIR / source).resolve()
        try:
            path.relative_to(ROBOT_WINDOW_DIR.resolve())
        except ValueError as exc:
            raise RuntimeError(f"script escapes Robot Window directory: {source}") from exc

        if "/blocks/" in normalized:
            block_sources.append(path)
        if "/generators/python/" in normalized:
            generator_sources.append(path)

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
        text = path.read_text(encoding="utf-8")
        generators.update(PYTHON_REGISTRY_RE.findall(text))
    return generators


def main() -> int:
    failures: list[str] = []

    if not HTML_PATH.is_file():
        failures.append(f"missing Robot Window entry point: {HTML_PATH.relative_to(ROOT)}")
        block_sources: list[Path] = []
        generator_sources: list[Path] = []
    else:
        block_sources, generator_sources = local_script_paths()

    for label, sources in (("block", block_sources), ("Python generator", generator_sources)):
        if not sources:
            failures.append(f"blockly.html references no {label} source files")
        for source in sources:
            if not source.is_file():
                failures.append(f"referenced {label} source is missing: {source.relative_to(ROOT)}")

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

    print("\nPASS: all six historical XML fixtures are well-formed and every used block type has a definition and Python generator loaded by blockly.html.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
