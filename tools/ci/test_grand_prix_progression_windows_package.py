"""Independent extracted ZIP verification for the new Grand Prix A1–A7 lessons.

Inspect source SHA, exact 23 native world bytes, per-lesson blank starters,
Windows profile binding and both native/PowerShell launcher contracts.
This cannot prove graphical usability, STOP buttons or teacher acceptance.
"""
import argparse
import json
from pathlib import Path
import re
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.grand_prix.package_windows_u import verified_files, digest
from tools.grand_prix.package_windows_route import PR970_SHA
from tools.grand_prix.package_windows_progression import (
    COUNTS, COURSE_IDS, FRONTEND, PROFILES, progression_world,
)


def verify(root):
    root = Path(root).resolve(strict=True)
    files = verified_files(root)
    source = (root / "SOURCE_SHA").read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"[0-9a-f]{40}", source):
        raise ValueError("Missing exact source SHA")
    if (root / "PR970_SHA").read_text(encoding="utf-8").strip() != PR970_SHA:
        raise ValueError("Source policy ancestry marker not pinned to merged #970")
    meta = json.loads((root / "COMPOSITION.json").read_text(encoding="utf-8"))
    if (meta.get("source_sha") != source or
            meta.get("dependency_sha") != PR970_SHA or
            meta.get("delivery") != "progression-a1-a7" or
            meta.get("scene_policy") != "classroom-static-v1" or
            meta.get("webots") != "R2025a" or
            meta.get("blockly") != "13.2.1" or
            "DRAFT" not in meta.get("qualification", "")):
        raise ValueError("Progression package source, Webots or policy mismatch")
    catalogue = json.loads((root / "COURSES.json").read_text(encoding="utf-8"))
    if (catalogue.get("course_ids") != list(COURSE_IDS) or
            catalogue.get("variant_counts") != list(COUNTS) or
            catalogue.get("physics_step_ms") != 8 or
            catalogue.get("fps_default") != 20 or
            catalogue.get("gui_pass") != "UNPROVEN"):
        raise ValueError("Grand Prix A1–A7 admission inventory mismatch")
    worlds = root / "worlds"
    stems = [f"grand_prix_route_v2_{index:02d}_fps20"
             for index in range(len(COURSE_IDS))]
    if {path.name for path in worlds.iterdir()} != {
            name for stem in stems for name in (stem + ".wbt", "." + stem + ".wbproj")}:
        raise ValueError("Expected exactly 23 world/perspective pairs, no A8 worlds")
    index = 0
    for activity, count in enumerate(COUNTS, 1):
        for variant in range(1, count + 1):
            stem = stems[index]
            actual = (worlds / (stem + ".wbt")).read_text(encoding="utf-8")
            expected = progression_world(activity, variant)
            if actual != expected or COURSE_IDS[index] not in actual:
                raise ValueError(f"Native A{activity} variant {variant} changed")
            perspective = (worlds / ("." + stem + ".wbproj")).read_text(encoding="utf-8")
            if "Webots Project File version R2025a" not in perspective:
                raise ValueError("Windows native perspective absent")
            index += 1

    activities = root / "Activites"
    if {p.name for p in activities.iterdir()} != {
            f"{activity:02d}-activite.wbb" for activity in range(1, 8)}:
        raise ValueError("Expected exactly seven blank student projects")
    for activity in range(1, 8):
        starter = json.loads((activities / f"{activity:02d}-activite.wbb").read_text(encoding="utf-8"))
        if (starter.get("format") != "webeeblocks-project" or starter.get("version") != 1 or
                starter.get("activity", {}).get("id") != f"progression-grand-prix-a{activity}-v1" or
                starter.get("workspace", {}).get("blocks", {}).get("blocks") != []):
            raise ValueError("Invalid A1–A7 blank .wbb starter")
    window = root / "plugins/robot_windows/grand_prix_route_v2"
    if (window / "progression_profile.js").read_bytes() != PROFILES.read_bytes():
        raise ValueError("Wrong pinned cumulative Blockly profile")
    html = (window / "grand_prix_route_v2.html").read_text(encoding="utf-8")
    if (html.count('<script src="setup.js"></script>') != 1 or
            'data-progression-activity' in html):
        raise ValueError("Host profile must be injected per Windows session, not global")
    script = (root / "Launch-WebeeBlocks.ps1").read_text(encoding="utf-8-sig")
    for contract in (
            "^(?:[0-9]|1[0-9]|2[0-2])$", "data-progression-activity",
            "progression_profile.js", "Association activité/parcours incohérente.",
            "WEBEEBLOCKS_GP_ACTIVITY", "GP_ROUTE_WINDOWS_LAUNCHER_SESSION_STAGED_OK",
            "RequestedFps -lt 1", "RequestedFps -gt 60"):
        if contract not in script:
            raise ValueError("Session launcher lost a required preflight: " + contract)
    front = (root / "Lancer-Progression.ps1").read_text(encoding="utf-8-sig")
    if front != FRONTEND or not (root / "Lancer-Progression.cmd").is_file():
        raise ValueError("Incorrect student Windows course chooser")
    if any((root / name).exists() for name in (
            "Lancer-Grand-Prix.cmd", "Lancer-Grand-Prix.ps1",
            "Activites/08-grand-prix-variable.wbb")):
        raise ValueError("A8-only entry point leaked into A1–A7 package")
    if (root / "plugins/robot_windows/blockly_v2/vendor/VERSION").read_text().strip() != "13.2.1":
        raise ValueError("Shipped Blockly version changed")
    return {"source_sha": source, "courses": index, "profiles": 7,
            "sha256_manifest": digest(root / "MANIFEST.sha256"),
            "native": "UNPROVEN", "teacher_windows": "UNPROVEN",
            "files": len(files)}


def verify_zip(archive, output):
    archive = Path(archive).resolve(strict=True)
    output = Path(output).resolve()
    if output.exists():
        raise ValueError("Extract only into a fresh directory")
    with zipfile.ZipFile(archive) as zf:
        names = zf.namelist()
        if (not names or len(set(names)) != len(names) or
                any(name.startswith("/") or "\\" in name or
                    ".." in Path(name).parts or name.endswith("/")
                    for name in names)):
            raise ValueError("Unsafe ZIP entry name")
        zf.extractall(output)
    return verify(output)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--archive", required=True, type=Path)
    p.add_argument("--extract-to", required=True, type=Path)
    args = p.parse_args()
    print(json.dumps(verify_zip(args.archive, args.extract_to), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
