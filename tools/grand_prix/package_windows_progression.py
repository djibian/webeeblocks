"""Isolated A1–A7 Windows lesson ZIP from a *verified* R2025a support closure.

Never changes the 12-course A8 package, evaluator, pilot, physics or oracles.
This is Draft packaging evidence, not a Windows GUI/teacher PASS.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.grand_prix.package_windows_route import (
    PR970_SHA, configure_windows_route_fps, exact_sha, route_world,
)
from tools.grand_prix.package_windows_u import verified_files, digest, replace_once
from tools.grand_prix.course_active_world_v2 import active_course_world
from tools.grand_prix.progression_courses import progression_course
from tools.grand_prix.route_courses_v2 import active_course_from_identifier, reference_course
from tools.ci.test_grand_prix_route_windows_package import verify as verify_a8

COUNTS = (1, 1, 1, 3, 5, 5, 7)
NAME = "WebeeBlocks-Progression-A1-A7-Windows-R2025a"
COURSE_IDS = tuple(
    progression_course(a, v).identifier
    for a, count in enumerate(COUNTS, 1)
    for v in range(1, count + 1)
)
ALL_COUNTS = COUNTS + (12,)
ALL_COURSE_IDS = COURSE_IDS + tuple(reference_course(i).identifier for i in range(12))
PROFILES = ROOT / "plugins/robot_windows/blockly/webeeblocks/grand_prix_progression.js"
ACCEPTANCE = ROOT / "docs/GRAND_PRIX_A1_A7_WINDOWS_ACCEPTANCE.md"
ACCEPTANCE_ALL = ROOT / "docs/GRAND_PRIX_A1_A8_WINDOWS_ACCEPTANCE.md"

# Fixed owner-approved A6 delivery contract (2026-11-20 and 2026-11-24, #587/#1100).
# Check the native source data; never substitute or rewrite activity geometry.
# This deliberately fails closed on the obsolete stacked #1075 A6 values.
APPROVED_A6 = (
    (2.25, (0.75,)),
    (2.90, (1.40,)),
    (3.00, (1.50,)),
    (1.40, ()),
    (1.50, ()),
)


def require_approved_a6():
    """Reject a Windows product assembled from superseded native A6 courses."""
    for variant, (length, open_gates) in enumerate(APPROVED_A6, start=1):
        course = progression_course(6, variant)
        observed_lengths = tuple(round(leg.length, 3) for leg in course.route.legs)
        observed_gates = tuple((gate.leg_index, round(gate.along, 3))
                               for gate in course.gates)
        expected_gates = tuple((0, along) for along in open_gates)
        if (observed_lengths != (length,) or
                observed_gates != expected_gates or
                course.count != len(open_gates) or
                course.pad_distance_from_h != 0.50 or
                course.pads != (1,) or course.required_pad != 1):
            raise ValueError(
                f"A6/V{variant} is not the owner-approved A6 geometry (including 2026-11-24 pad distance); "
                "recompose the native stack from current main before packaging")


def require_approved_geometry():
    """Reject superseded owner geometry before any delivery tree is copied."""
    from tools.grand_prix.route_courses_v2 import LOW_BEFORE, LOW_AFTER
    from tools.grand_prix.oracle_terminal_dwell_v2 import LANDING_TOL
    from tools.grand_prix.route_terminal_v2 import LANDING_TILE
    require_approved_a6()
    for activity, count in enumerate(ALL_COUNTS, 1):
        for variant in range(1, count + 1):
            course = (reference_course(variant - 1) if activity == 8 else
                      progression_course(activity, variant))
            expected = .30 if activity <= 5 else .50
            if abs(course.pad_distance_from_h - expected) > 1e-9:
                raise ValueError(f"A{activity}/V{variant} lacks owner-approved pad geometry")
    a3 = progression_course(3, 1)
    if (a3.route.lengths != (2.5, 2.5, 2.8) or
            tuple((g.leg_index, g.along) for g in a3.gates) !=
            ((0, 1.25), (1, 1.25), (2, 1.25)) or
            (LOW_BEFORE, LOW_AFTER) != (.45, .45) or
            abs(LANDING_TOL - .07) > 1e-9 or abs(LANDING_TILE - .28) > 1e-9):
        raise ValueError("Missing owner-approved A3, low band or landing geometry")


def require_native_pilot_admission():
    """The C++ runtime must explicitly accept every Python-admitted lesson ID.

    Python geometry alone cannot authorize delivery. The static C++ admission
    list is another necessary check; native compilation and real R2025a
    qualification remain separately required before release.
    """
    source = (ROOT / "controllers/grand_prix_u_flight/grand_prix_u_deadline.cpp"
              ).read_text(encoding="utf-8")
    native_ids = set(re.findall(
        r'std::strcmp\(raw,\s*"(gp-progression-v1-a[1-7]-v[1-9][0-9]*)"\)',
        source))
    for identifier in COURSE_IDS:
        if identifier not in native_ids:
            raise ValueError(
                f"{identifier} not yet admitted by the native C++ pilot; no Windows ZIP")


def require_native_admission():
    """All 23 variant IDs must be admitted by the actual native pilot/evaluator.

    A geometric CoursePlan existing in Python does not establish admission.
    The new delivery is deliberately unbuildable on an incomplete native stack.
    """
    for activity, count in enumerate(COUNTS, 1):
        for variant in range(1, count + 1):
            candidate = progression_course(activity, variant)
            try:
                admitted = active_course_from_identifier(candidate.identifier)
            except ValueError as error:
                raise ValueError(
                    f"A{activity}/V{variant} not yet admitted by the native Grand Prix; "
                    "wait for qualified A5–A7 integration") from error
            if admitted != candidate:
                raise ValueError(f"A{activity}/V{variant} native admission differs from source geometry")
    require_native_pilot_admission()


# Only the presentation labels and default window choices are in this file.
# Native CoursePlan and controllerArgs retain sole authority over geometry.
FRONTEND = r"""[CmdletBinding()]
param(
  [int]$Activite = 0,
  [int]$Variante = 0,
  [string]$WebotsHome = $env:WEBOTS_HOME,
  [switch]$ValidateOnly
)
$ErrorActionPreference = 'Stop'
$counts = @(1,1,1,3,5,5,7)
$names = @(
  'Parcourir un circuit',
  'Franchir un H ouvert',
  'Répéter un trajet',
  'Observer pour adapter le déplacement',
  'Mémoriser le virage',
  'Discriminer un H ouvert',
  'Mini Grand Prix'
)
if ($Activite -eq 0) {
  Write-Host 'WebeeBlocks — choisir une activité'
  for ($a = 1; $a -le 7; $a++) {
    Write-Host ('A{0} — {1} ({2} parcours)' -f $a, $names[$a - 1], $counts[$a - 1])
  }
  $raw = Read-Host 'Activité (1 à 7)'
  if ($raw -cnotmatch '^[1-7]$') { throw 'Activité invalide (1 à 7).' }
  $Activite = [int]$raw
}
if ($Activite -lt 1 -or $Activite -gt 7) {
  throw 'Activité invalide (1 à 7).'
}
if ($Variante -eq 0) {
  if ($counts[$Activite - 1] -eq 1) {
    $Variante = 1
  } else {
    $raw = Read-Host ('Parcours A{0} (1 à {1}, Entrée = 1)' -f $Activite, $counts[$Activite - 1])
    if ([string]::IsNullOrWhiteSpace($raw)) { $raw = '1' }
    if ($raw -cnotmatch '^[1-9][0-9]*$') { throw 'Numéro de parcours invalide.' }
    $Variante = [int]$raw
  }
}
if ($Variante -lt 1 -or $Variante -gt $counts[$Activite - 1]) {
  throw 'Ce parcours est indisponible pour cette activite.'
}
$index = $Variante - 1
for ($a = 1; $a -lt $Activite; $a++) { $index += $counts[$a - 1] }
if ($index -lt 0 -or $index -ge 23) { throw 'Index de parcours non admis.' }
$env:WEBEEBLOCKS_GP_INDEX = [string]$index
$env:WEBEEBLOCKS_GP_ACTIVITY = [string]$Activite
$env:WEBEEBLOCKS_GP_FPS = '20'
Write-Host ('Activité A{0}, parcours {1}/{2}. Enregistrez votre .wbb avant de quitter.' -f $Activite,$Variante,$counts[$Activite - 1])
& (Join-Path $PSScriptRoot 'Launch-WebeeBlocks.ps1') -WebotsHome $WebotsHome -ValidateOnly:$ValidateOnly
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
"""


def all_frontend():
    text = replace_once(FRONTEND, "$counts = @(1,1,1,3,5,5,7)", "$counts = @(1,1,1,3,5,5,7,12)")
    text = replace_once(text, "  'Mini Grand Prix'\n", "  'Mini Grand Prix',\n  'Grand Prix autonome'\n")
    text = replace_once(text, "$a -le 7;", "$a -le 8;")
    text = replace_once(text, "'^[1-7]$'", "'^[1-8]$'")
    text = text.replace("1 à 7", "1 à 8")
    text = replace_once(text, "$Activite -gt 7", "$Activite -gt 8")
    text = replace_once(text, "$index -ge 23", "$index -ge 35")
    return text


def progression_world(activity, variant):
    """Only swap official offline PROTO imports on the shared native world."""
    course = active_course_from_identifier(progression_course(activity, variant).identifier)
    scene = configure_windows_route_fps(active_course_world(course), 20)
    sources = {
        "Crazyflie": "robots/bitcraze/crazyflie/protos",
        "TexturedBackground": "objects/backgrounds/protos",
        "TexturedBackgroundLight": "objects/backgrounds/protos",
        "Floor": "objects/floors/protos",
    }
    for name, prefix in sources.items():
        scene = replace_once(
            scene, f'EXTERNPROTO "webots://projects/{prefix}/{name}.proto"',
            f'EXTERNPROTO "../protos/{name}.proto"')
    if (scene.count('controller "grand_prix_route_flight"') != 1 or
            scene.count('controller "grand_prix_route_evaluator"') != 1 or
            scene.count('window "grand_prix_route_v2"') != 1 or
            scene.count(f'controllerArgs [ "{course.identifier}" ]') != 2 or
            scene.count("basicTimeStep 8") != 1 or
            scene.count("FPS 20 ") != 1 or
            scene.count("Floor {") != 1 or
            re.search(r'"(?:https?|webots)://', scene)):
        raise ValueError("Progression native world identity/geometry changed")
    return scene


def progression_launcher(launcher, include_a8=False):
    text = launcher.read_text(encoding="utf-8-sig")
    text = replace_once(text, "'^(?:[0-9]|10|11)$'", "'^(?:[0-9]|1[0-9]|2[0-2])$'")
    text = replace_once(text, "index 0..11, FPS 1..60", "index 0..22, FPS 1..60")
    # Bind native course index to host-selected lesson. No learner file owns it.
    text = replace_once(text, "$index = [int]$indexText\n",
        "$index = [int]$indexText\n"
        "$lesson = [string]$env:WEBEEBLOCKS_GP_ACTIVITY\n"
        "if ($lesson -cnotmatch '^[1-7]$') { throw 'Activité absente ou invalide.' }\n"
        "$lessonNumber = [int]$lesson\n"
        "$first = @(0,1,2,3,6,11,16)[$lessonNumber - 1]\n"
        "$counts = @(1,1,1,3,5,5,7)\n"
        "if ($index -lt $first -or $index -ge ($first + $counts[$lessonNumber - 1])) {\n"
        "  throw 'Association activité/parcours incohérente.'\n"
        "}\n")
    # The activity is selected by the host, not inferred from any pupil .wbb,
    # Blockly AST, route length, oracle data or hidden variant.
    anchor = "  $html = [System.IO.File]::ReadAllText($Session.Html, [System.Text.Encoding]::UTF8)\n"
    insertion = r"""  $lesson = [string]$env:WEBEEBLOCKS_GP_ACTIVITY
  if ($lesson -cnotmatch '^[1-7]$') {
    throw 'Activité pédagogique absente ou invalide.'
  }
  $tag = '<script src="setup.js?rev=20261126-portable-open"></script>'
  if ([regex]::Matches($html, [regex]::Escape($tag)).Count -ne 1) {
    throw 'Entrée Blockly pédagogique non conforme.'
  }
  $profileTag = '<script src="../blockly/webeeblocks/grand_prix_progression.js"></script>'
  if ([regex]::Matches($html, [regex]::Escape($profileTag)).Count -ne 1 -or
      $html.IndexOf($profileTag) -gt $html.IndexOf($tag)) {
    throw 'Catalogue de profils Grand Prix absent ou duplique.'
  }
  $replacement = '<script src="setup.js?rev=20261126-portable-open" data-progression-activity="' + $lesson + '"></script>'
  $html = $html.Replace($tag, $replacement)
"""
    text = replace_once(text, anchor, anchor + insertion)
    if include_a8:
        text = replace_once(text, "'^(?:[0-9]|1[0-9]|2[0-2])$'", "'^(?:[0-9]|[12][0-9]|3[0-4])$'")
        text = replace_once(text, "index 0..22, FPS 1..60", "index 0..34, FPS 1..60")
        if text.count("'^[1-7]$'") != 2:
            raise ValueError("Unexpected activity checks in progression launcher")
        text = text.replace("'^[1-7]$'", "'^[1-8]$'")
        text = replace_once(text, "@(0,1,2,3,6,11,16)", "@(0,1,2,3,6,11,16,23)")
        text = replace_once(text, "@(1,1,1,3,5,5,7)", "@(1,1,1,3,5,5,7,12)")
        # A8 uses the original setup.js default profile; never invent a lesson 8 profile.
        text = replace_once(text, "  $html = $html.Replace($tag, $replacement)",
            "  if ($lesson -ne '8') { $html = $html.Replace($tag, $replacement) }")
    return text


def compose(source, output, include_a8=False):
    """Copy verified Windows support into a new A1–A7 or unified A1–A8 tree."""
    require_approved_geometry()  # before copying files or creating any ZIP
    require_native_admission()  # never ship designed-but-unadmitted courses
    sha = exact_sha()
    verified = verify_a8(source)
    if verified["source_sha"] != sha or verified["dependency_sha"] != PR970_SHA:
        raise ValueError("A8 support source or integration provenance mismatch")
    if output.exists():
        raise ValueError("Use a new output path")
    if not PROFILES.is_file():
        raise ValueError("Progression Blockly profiles absent")
    acceptance = ACCEPTANCE_ALL if include_a8 else ACCEPTANCE
    if not acceptance.is_file():
        raise ValueError("Windows acceptance procedure absent")

    shutil.copytree(source, output)
    worlds = output / "worlds"
    shutil.rmtree(worlds)
    worlds.mkdir()
    source_perspective = ROOT / "worlds/.crazyflie_runtime_v2.wbproj"
    if not source_perspective.is_file():
        raise ValueError("Native classroom perspective missing")
    index = 0
    for activity, count in enumerate(COUNTS, 1):
        for variant in range(1, count + 1):
            label = f"grand_prix_route_v2_{index:02d}_fps20"
            (worlds / (label + ".wbt")).write_text(
                progression_world(activity, variant), encoding="utf-8")
            shutil.copyfile(source_perspective, worlds / ("." + label + ".wbproj"))
            index += 1
    if index != len(COURSE_IDS):
        raise ValueError("Incomplete progression course inventory")

    if include_a8:
        if len(set(ALL_COURSE_IDS)) != 35:
            raise ValueError("Unified course IDs are not unique")
        # Reindex only the filenames. Preserve the exact canonical A8 scene bytes.
        for native_index in range(12):
            old_stem = f"grand_prix_route_v2_{native_index:02d}_fps20"
            new_stem = f"grand_prix_route_v2_{index:02d}_fps20"
            old_world = source / "worlds" / (old_stem + ".wbt")
            expected, identifier = route_world(native_index, 20)
            if (old_world.read_text(encoding="utf-8") != expected or
                    identifier != ALL_COURSE_IDS[index]):
                raise ValueError("A8 support world differs from exact candidate: " + old_stem)
            shutil.copyfile(old_world, worlds / (new_stem + ".wbt"))
            shutil.copyfile(source / "worlds" / ("." + old_stem + ".wbproj"),
                            worlds / ("." + new_stem + ".wbproj"))
            index += 1
        if index != len(ALL_COURSE_IDS):
            raise ValueError("Incomplete unified course inventory")

    window = output / "plugins/robot_windows/grand_prix_route_v2"
    shipped_profiles = window.parent / "blockly/webeeblocks/grand_prix_progression.js"
    if shipped_profiles.read_bytes() != PROFILES.read_bytes():
        raise ValueError("A8 support progression catalogue differs from source")
    launch = output / "Launch-WebeeBlocks.ps1"
    launch.write_text(progression_launcher(launch, include_a8), encoding="utf-8-sig")
    (output / "Lancer-Grand-Prix.ps1").unlink()
    (output / "Lancer-Grand-Prix.cmd").unlink()
    (output / "Lancer-Progression.ps1").write_text(all_frontend() if include_a8 else FRONTEND, encoding="utf-8-sig")
    (output / "Lancer-Progression.cmd").write_text(
        '@echo off\r\npowershell.exe -STA -NoProfile -ExecutionPolicy Bypass -File "%~dp0Lancer-Progression.ps1" %*\r\n'
        'exit /b %ERRORLEVEL%\r\n', encoding="utf-8")
    activities = output / "Activites"
    shutil.rmtree(activities)
    activities.mkdir()
    original = json.loads((source / "Activites/08-grand-prix-variable.wbb").read_text(encoding="utf-8"))
    for activity in range(1, 8):
        starter = json.loads(json.dumps(original))
        starter["activity"]["id"] = f"progression-grand-prix-a{activity}-v1"
        (activities / f"{activity:02d}-activite.wbb").write_text(
            json.dumps(starter, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if include_a8:
        shutil.copyfile(source / "Activites/08-grand-prix-variable.wbb",
                        activities / "08-grand-prix-variable.wbb")
    (output / "COURSES.json").write_text(json.dumps({
        "profile": "progression-grand-prix-a1-a8-v1" if include_a8 else "progression-grand-prix-a1-a7-v1",
        "course_ids": list(ALL_COURSE_IDS if include_a8 else COURSE_IDS),
        "variant_counts": list(ALL_COUNTS if include_a8 else COUNTS), "physics_step_ms": 8,
        "fps_default": 20, "gui_pass": "UNPROVEN"
    }, indent=2) + "\n", encoding="utf-8")
    provenance = json.loads((source / "COMPOSITION.json").read_text(encoding="utf-8"))
    provenance["delivery"] = "progression-a1-a8" if include_a8 else "progression-a1-a7"
    provenance["qualification"] = (
        "DRAFT: 35 native routes and Windows teacher GUI require separate evidence" if include_a8
        else "DRAFT: 23 native routes and Windows teacher GUI require separate evidence")
    (output / "COMPOSITION.json").write_text(
        json.dumps(provenance, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    (output / "README-WINDOWS.md").write_text(
        "# WebeeBlocks — progression A1–A7 (livrable expérimental)\n\n"
        "Exécuter Lancer-Progression.cmd, sélectionner l'activité et le parcours, "
        "puis utiliser Démarrer une activité pour créer le programme Blockly vierge.\n"
        "Pour changer de variante : enregistrer sous .wbb, fermer Webots, "
        "relancer le même numéro d'activité avec un autre parcours, ouvrir le même .wbb.\n"
        "STOP, RESET, décollage et pose sont régis par le pilote natif. "
        "La validation Windows enseignant et l'acceptation pédagogique restent requises. "
        "Voir ACCEPTATION-WINDOWS.md pour les préflights, les 23 essais et les verdicts.\n",
        encoding="utf-8")
    if include_a8:
        (output / "README-WINDOWS.md").write_text(
            "# WebeeBlocks — progression A1–A8 (qualification uniquement)\n\n"
            "Lancer-Progression.cmd : choisir explicitement A1 à A8, puis le parcours. "
            "Les variantes A8 1 à 12 correspondent aux indices canoniques 0 à 11. "
            "Enregistrer le .wbb avant de quitter, puis relancer l'activité voulue. "
            "Ouvrir un projet ne sélectionne pas la scène. Le préflight de l'activité reste obligatoire.\n\n"
            "ACCEPTATION-WINDOWS.md couvre les 35 variantes A1–A8, "
            "les huit fichiers .wbb, les négatifs, STOP/RESET/LAND et le délai 210 s. "
            "Aucun PASS enseignant ni autorisation de publication.\n", encoding="utf-8")
    shutil.copyfile(acceptance, output / "ACCEPTATION-WINDOWS.md")
    (output / "MANIFEST.sha256").unlink()
    manifest = "\n".join(
        f"{digest(p)}  {p.relative_to(output).as_posix()}"
        for p in sorted(output.rglob("*"))
        if p.is_file() and p.name != "MANIFEST.sha256")
    (output / "MANIFEST.sha256").write_text(manifest + "\n", encoding="utf-8")
    verified_files(output)
    archive = output.with_suffix(".zip")
    if archive.exists():
        raise ValueError("ZIP target exists")
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=9) as target:
        for path in sorted(output.rglob("*")):
            if path.is_file():
                member = zipfile.ZipInfo(path.relative_to(output).as_posix(),
                                         date_time=(1980, 1, 1, 0, 0, 0))
                member.create_system = 3
                member.external_attr = 0o100644 << 16
                member.compress_type = zipfile.ZIP_DEFLATED
                target.writestr(member, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED,
                                compresslevel=9)
    archive.with_suffix(".zip.sha256").write_text(
        digest(archive) + "  " + archive.name + "\n", encoding="utf-8")
    return archive


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--include-a8", action="store_true", help="Unify all 35 exact native variants")
    args = parser.parse_args()
    archive = compose(args.source, args.output, args.include_a8)
    print("GP_PROGRESSION_WINDOWS_DRAFT_ZIP", archive, digest(archive))


if __name__ == "__main__":
    main()
