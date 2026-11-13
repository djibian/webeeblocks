"""Fail-closed inspection of the extracted variable GP Windows delivery.

Static verification is NOT native Windows/Webots admission, GUI or teacher PASS.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.grand_prix.route_courses_v2 import reference_course
from tools.grand_prix.package_windows_u import verified_files, digest

PR970 = "6486e73ccc193da3d609e45e73e7c0687b84ecc4"


def verify(root):
    root = Path(root).resolve(strict=True)
    files = verified_files(root)
    metadata = json.loads((root / "COMPOSITION.json").read_text(encoding="utf-8"))
    if (metadata.get("dependency_sha") != PR970 or
            metadata.get("scene_policy") != "classroom-static-v1" or
            metadata.get("webots") != "R2025a" or
            metadata.get("webots_source_sha") != "c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b" or
            metadata.get("blockly") != "13.2.1" or
            metadata.get("source_sha") != (root / "SOURCE_SHA").read_text().strip() or
            (root / "PR970_SHA").read_text().strip() != PR970):
        raise ValueError("Source provenance or #970 dependency mismatch")
    worlds = sorted((root / "worlds").glob("*.wbt"))
    if len(worlds) != 36:
        raise ValueError("Exactly 12 canonical routes x 3 FPS worlds required")
    profile = json.loads((root / "Activites/08-grand-prix-variable.wbb").read_text(encoding="utf-8"))
    if (profile["format"] != "webeeblocks-project" or
            profile["activity"]["id"] != "progression-grand-prix-route-v2"):
        raise ValueError("Unexpected pupil project/activity identity")
    ids = json.loads((root / "COURSES.json").read_text(encoding="utf-8"))
    if ids.get("course_ids") != [reference_course(i).identifier for i in range(12)]:
        raise ValueError("Host-only course inventory mismatch")
    if ids.get("fps") != [60, 30, 25] or ids.get("physics_step_ms") != 8:
        raise ValueError("Physics/render policy corrupted")
    expected = set()
    for i in range(12):
        for fps in (60, 30, 25):
            stem = f"grand_prix_route_v2_{i:02d}_fps{fps}"
            expected.add(stem + ".wbt")
            path = root / "worlds" / (stem + ".wbt")
            scene = path.read_text(encoding="utf-8")
            identifier = reference_course(i).identifier
            if (scene.count('controller "grand_prix_route_flight"') != 1 or
                    scene.count('controller "grand_prix_route_evaluator"') != 1 or
                    scene.count('window "grand_prix_route_v2"') != 1 or
                    scene.count(f'controllerArgs [ "{identifier}" ]') != 2 or
                    scene.count('basicTimeStep 8') != 1 or
                    scene.count(f'FPS {fps} ') != 1 or
                    scene.count("Floor {") != 1 or
                    re.search(r'"(?:https?|webots)://', scene) or
                    any(scene.count(f'EXTERNPROTO "../protos/{proto}.proto"') != 1
                        for proto in ("Crazyflie", "Floor", "TexturedBackground",
                                      "TexturedBackgroundLight"))):
                raise ValueError("Canonical scene contract mismatch: " + stem)
            if not (root / "worlds" / ("." + stem + ".wbproj")).is_file():
                raise ValueError("Native R2025a project perspective missing")
    for name in ("Crazyflie", "Floor", "Parquetry", "TexturedBackground", "TexturedBackgroundLight"):
        if not (root / "protos" / (name + ".proto")).is_file():
            raise ValueError("Offline native R2025a PROTO absent: " + name)
    for direction in ("back", "bottom", "front", "left", "right", "top"):
        for ext in ("jpg", "hdr"):
            if not (root / "protos/textures/cubic" / f"mountains_{direction}.{ext}").is_file():
                raise ValueError("Offline native original skybox texture missing")
    for kind in ("base_color", "roughness", "normal", "occlusion"):
        if not (root / "protos/textures/parquetry" / f"chequered_parquetry_{kind}.jpg").is_file():
            raise ValueError("Native Floor appearance texture missing")
    if {p.name for p in worlds} != expected:
        raise ValueError("Unexpected route worlds")
    if not (root / "controllers/grand_prix_route_flight/grand_prix_route_flight.exe").is_file():
        raise ValueError("Real compiled Windows flight binary missing")
    if not (root / "controllers/grand_prix_route_evaluator/grand_prix_route_evaluator.py").is_file():
        raise ValueError("Native evaluator bootstrap missing")
    if "SCENE_POLICY_CLASSROOM_STATIC" not in (root / "tools/grand_prix/evaluator_publisher_v2.py").read_text():
        raise ValueError("Static policy not shipped")
    if not (root / "plugins/robot_windows/grand_prix_route_v2/setup.js").is_file():
        raise ValueError("Blockly variable profile missing")
    if not (root / "plugins/robot_windows/blockly_v2/vendor/VERSION").is_file():
        raise ValueError("Blockly version asset missing")
    if (root / "plugins/robot_windows/blockly_v2/vendor/VERSION").read_text().strip() != "13.2.1":
        raise ValueError("Wrong Blockly build")
    launcher = (root / "Launch-WebeeBlocks.ps1").read_text(encoding="utf-8-sig")
    if ("grand_prix_route_v2" not in launcher or
            "._gp_route_session_" not in launcher or
            "WEBEEBLOCKS_GP_FPS" not in launcher or
            "WEBEEBLOCKS_GP_INDEX" not in launcher or
            "GetRelativePath(" in launcher or
            "GP_ROUTE_WINDOWS_LAUNCHER_SESSION_STAGED_OK" not in launcher or
            "Stop-WebeeBlocksLocalServer -Server $testServer" not in launcher):
        raise ValueError("Windows launcher not routed to isolated static identity")
    if any("grand_prix_u" in x.lower() for x in expected):
        raise ValueError("Historical U geometry leaked into delivery")
    return dict(source_sha=metadata["source_sha"], dependency_sha=PR970,
                file_count=len(files), worlds=len(worlds), sha256_manifest=digest(root / "MANIFEST.sha256"),
                modes=[25, 30, 60], native_status="UNPROVEN", gui_status="UNPROVEN")


def verify_zip(archive, output):
    archive, output = Path(archive).resolve(strict=True), Path(output).resolve()
    if output.exists():
        raise ValueError("Extract only into a fresh directory")
    with zipfile.ZipFile(archive) as zf:
        names = zf.namelist()
        if not names or len(names) != len(set(names)):
            raise ValueError("Empty or duplicate ZIP entries")
        if any(not re.fullmatch(r"[A-Za-z0-9_.\-/ ]+", name) or
               name.startswith(("/", "../")) or "/../" in name or
               "\\" in name for name in names):
            raise ValueError("Unsafe ZIP entry")
        for member in zf.infolist():
            if member.is_dir() or ((member.external_attr >> 16) & 0o170000) == 0o120000:
                raise ValueError("Directory/symlink ZIP entry refused")
        zf.extractall(output)
    return verify(output)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--extract-to", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify_zip(args.archive, args.extract_to), indent=2))


if __name__ == "__main__":
    main()
