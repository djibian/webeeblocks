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
from tools.grand_prix.package_windows_route import PR970_SHA, exact_sha, route_world
from tools.grand_prix.package_windows_progression import (
    ACCEPTANCE, ACCEPTANCE_ALL, COUNTS, COURSE_IDS, ALL_COUNTS, ALL_COURSE_IDS, FRONTEND, PROFILES,
    all_frontend, progression_world,
    require_approved_geometry, require_native_admission,
)


def verify(root, include_a8=False):
    require_approved_geometry()  # reject stale source even when ZIP/manifest agree
    require_native_admission()  # reject unadmitted A5–A7 sources, even if checksums match
    root = Path(root).resolve(strict=True)
    files = verified_files(root)
    source = (root / "SOURCE_SHA").read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"[0-9a-f]{40}", source):
        raise ValueError("Missing exact source SHA")
    if (root / "PR970_SHA").read_text(encoding="utf-8").strip() != PR970_SHA:
        raise ValueError("Source policy ancestry marker not pinned to merged #970")
    counts = ALL_COUNTS if include_a8 else COUNTS
    ids = ALL_COURSE_IDS if include_a8 else COURSE_IDS
    delivery = "progression-a1-a8" if include_a8 else "progression-a1-a7"
    if include_a8 and (source != exact_sha() or len(set(ids)) != 35):
        raise ValueError("Unified archive must be checked from its exact source checkout")
    meta = json.loads((root / "COMPOSITION.json").read_text(encoding="utf-8"))
    if (meta.get("source_sha") != source or
            meta.get("dependency_sha") != PR970_SHA or
            meta.get("delivery") != delivery or
            meta.get("scene_policy") != "classroom-static-v1" or
            meta.get("webots") != "R2025a" or
            meta.get("blockly") != "13.2.1" or
            "DRAFT" not in meta.get("qualification", "")):
        raise ValueError("Progression package source, Webots or policy mismatch")
    catalogue = json.loads((root / "COURSES.json").read_text(encoding="utf-8"))
    if (catalogue.get("course_ids") != list(ids) or
            catalogue.get("variant_counts") != list(counts) or
            catalogue.get("physics_step_ms") != 8 or
            catalogue.get("fps_default") != 20 or
            catalogue.get("gui_pass") != "UNPROVEN"):
        raise ValueError("Grand Prix A1–A7 admission inventory mismatch")
    worlds = root / "worlds"
    stems = [f"grand_prix_route_v2_{index:02d}_fps20"
             for index in range(len(ids))]
    if {path.name for path in worlds.iterdir()} != {
            name for stem in stems for name in (stem + ".wbt", "." + stem + ".wbproj")}:
        raise ValueError("Incorrect exact world/perspective inventory")
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

    if include_a8:
        for native_index in range(12):
            stem = stems[index]
            expected, identifier = route_world(native_index, 20)
            if ((worlds / (stem + ".wbt")).read_text(encoding="utf-8") != expected or
                    identifier != ids[index] or
                    "Webots Project File version R2025a" not in
                    (worlds / ("." + stem + ".wbproj")).read_text(encoding="utf-8")):
                raise ValueError(f"Canonical A8 variant {native_index + 1} changed")
            index += 1
        pilot = root / "controllers/grand_prix_route_flight/grand_prix_route_flight.exe"
        if (not pilot.is_file() or not pilot.stat().st_size or
                digest(pilot) != meta.get("pilot_binary_sha256") or
                not (root / "controllers/grand_prix_route_evaluator/grand_prix_route_evaluator.py").is_file()):
            raise ValueError("Native compiled pilot/evaluator provenance absent")
    activities = root / "Activites"
    starter_names = {f"{activity:02d}-activite.wbb" for activity in range(1, 8)}
    if include_a8:
        starter_names.add("08-grand-prix-variable.wbb")
    if {p.name for p in activities.iterdir()} != starter_names:
        raise ValueError("Incorrect blank student project inventory")
    for activity in range(1, 8):
        starter = json.loads((activities / f"{activity:02d}-activite.wbb").read_text(encoding="utf-8"))
        if (starter.get("format") != "webeeblocks-project" or starter.get("version") != 1 or
                starter.get("activity", {}).get("id") != f"progression-grand-prix-a{activity}-v1" or
                starter.get("activity", {}).get("semantics") != "webeeblocks-ast-v1" or
                starter.get("workspace", {}).get("blocks", {}).get("blocks") != []):
            raise ValueError("Invalid A1–A7 blank .wbb starter")
    if include_a8:
        starter = json.loads((activities / "08-grand-prix-variable.wbb").read_text(encoding="utf-8"))
        if (starter.get("format") != "webeeblocks-project" or starter.get("version") != 1 or
                starter.get("activity", {}).get("id") != "progression-grand-prix-route-v2" or
                starter.get("activity", {}).get("semantics") != "webeeblocks-ast-v1" or
                starter.get("workspace", {}).get("blocks", {}).get("blocks") != []):
            raise ValueError("Invalid canonical A8 blank .wbb starter")
    window = root / "plugins/robot_windows/grand_prix_route_v2"
    if ((window.parent / "blockly/webeeblocks/grand_prix_progression.js").read_bytes()
            != PROFILES.read_bytes() or (window / "progression_profile.js").exists()):
        raise ValueError("Wrong or duplicate pinned cumulative Blockly profile")
    acceptance = ACCEPTANCE_ALL if include_a8 else ACCEPTANCE
    if (root / "ACCEPTATION-WINDOWS.md").read_bytes() != acceptance.read_bytes():
        raise ValueError("Windows teacher acceptance guide missing or incorrect")
    html = (window / "grand_prix_route_v2.html").read_text(encoding="utf-8")
    profile_tag = '<script src="../blockly/webeeblocks/grand_prix_progression.js"></script>'
    setup_tag = '<script src="setup.js?rev=20261126-portable-open"></script>'
    if (html.count(setup_tag) != 1 or html.count(profile_tag) != 1 or
            html.index(profile_tag) > html.index(setup_tag) or
            'data-progression-activity' in html):
        raise ValueError("Host profile must be injected per Windows session, not global")
    script = (root / "Launch-WebeeBlocks.ps1").read_text(encoding="utf-8-sig")
    for contract in (
            ("^(?:[0-9]|[12][0-9]|3[0-4])$" if include_a8 else "^(?:[0-9]|1[0-9]|2[0-2])$"), "data-progression-activity",
            'setup.js?rev=20261126-portable-open', "grand_prix_progression.js", "Association activité/parcours incohérente.",
            "WEBEEBLOCKS_GP_ACTIVITY", "GP_ROUTE_WINDOWS_LAUNCHER_SESSION_STAGED_OK",
            "RequestedFps -lt 1", "RequestedFps -gt 60"):
        if contract not in script:
            raise ValueError("Session launcher lost a required preflight: " + contract)
    if 'src="progression_profile.js"' in script:
        raise ValueError("Session launcher must not reload the shared catalogue")
    front = (root / "Lancer-Progression.ps1").read_text(encoding="utf-8-sig")
    if front != (all_frontend() if include_a8 else FRONTEND) or not (root / "Lancer-Progression.cmd").is_file():
        raise ValueError("Incorrect student Windows course chooser")
    if any((root / name).exists() for name in ("Lancer-Grand-Prix.cmd", "Lancer-Grand-Prix.ps1")):
        raise ValueError("A8-only entry point leaked into progression selector")
    if include_a8 and any(anchor not in script for anchor in (
            "@(0,1,2,3,6,11,16,23)", "@(1,1,1,3,5,5,7,12)",
            "if ($lesson -ne '8') { $html = $html.Replace($tag, $replacement) }")):
        raise ValueError("Unified selector lost explicit A8 mapping or profile boundary")
    if (root / "plugins/robot_windows/blockly_v2/vendor/VERSION").read_text().strip() != "13.2.1":
        raise ValueError("Shipped Blockly version changed")
    return {"source_sha": source, "courses": index, "profiles": len(counts),
            "sha256_manifest": digest(root / "MANIFEST.sha256"),
            "native": "UNPROVEN", "teacher_windows": "UNPROVEN",
            "files": len(files)}


def verify_zip(archive, output, include_a8=False):
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
    return verify(output, include_a8)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--archive", required=True, type=Path)
    p.add_argument("--extract-to", required=True, type=Path)
    p.add_argument("--include-a8", action="store_true")
    args = p.parse_args()
    print(json.dumps(verify_zip(args.archive, args.extract_to, args.include_a8), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
