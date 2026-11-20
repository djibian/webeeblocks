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
    PR970_SHA, configure_windows_route_fps, exact_sha,
)
from tools.grand_prix.package_windows_u import verified_files, digest, replace_once
from tools.grand_prix.course_active_world_v2 import active_course_world
from tools.grand_prix.progression_courses import progression_course
from tools.ci.test_grand_prix_route_windows_package import verify as verify_a8

COUNTS = (1, 1, 1, 3, 5, 5, 7)
NAME = "WebeeBlocks-Progression-A1-A7-Windows-R2025a"
COURSE_IDS = tuple(
    progression_course(a, v).identifier
    for a, count in enumerate(COUNTS, 1)
    for v in range(1, count + 1)
)
PROFILES = ROOT / "plugins/robot_windows/blockly/webeeblocks/grand_prix_progression.js"

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
  throw 'Ce parcours n’existe pas pour l’activité choisie.'
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


def progression_world(activity, variant):
    """Only swap official offline PROTO imports on the shared native world."""
    course = progression_course(activity, variant)
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


def progression_launcher(launcher):
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
  $tag = '<script src="setup.js"></script>'
  if ([regex]::Matches($html, [regex]::Escape($tag)).Count -ne 1) {
    throw 'Entrée Blockly pédagogique non conforme.'
  }
  $replacement = '<script src="progression_profile.js"></script>' + "`n" +
    '<script src="setup.js" data-progression-activity="' + $lesson + '"></script>'
  $html = $html.Replace($tag, $replacement)
"""
    text = replace_once(text, anchor, anchor + insertion)
    return text


def compose(source, output):
    """Copy verified Windows support into a *new*, exclusively A1–A7 tree."""
    sha = exact_sha()
    verified = verify_a8(source)
    if verified["source_sha"] != sha or verified["dependency_sha"] != PR970_SHA:
        raise ValueError("A8 support source or integration provenance mismatch")
    if output.exists():
        raise ValueError("Use a new output path")
    if not PROFILES.is_file():
        raise ValueError("Progression Blockly profiles absent")

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

    window = output / "plugins/robot_windows/grand_prix_route_v2"
    shutil.copyfile(PROFILES, window / "progression_profile.js")
    launch = output / "Launch-WebeeBlocks.ps1"
    launch.write_text(progression_launcher(launch), encoding="utf-8-sig")
    (output / "Lancer-Grand-Prix.ps1").unlink()
    (output / "Lancer-Grand-Prix.cmd").unlink()
    (output / "Lancer-Progression.ps1").write_text(FRONTEND, encoding="utf-8-sig")
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
    (output / "COURSES.json").write_text(json.dumps({
        "profile": "progression-grand-prix-a1-a7-v1", "course_ids": list(COURSE_IDS),
        "variant_counts": list(COUNTS), "physics_step_ms": 8,
        "fps_default": 20, "gui_pass": "UNPROVEN"
    }, indent=2) + "\n", encoding="utf-8")
    provenance = json.loads((source / "COMPOSITION.json").read_text(encoding="utf-8"))
    provenance["delivery"] = "progression-a1-a7"
    provenance["qualification"] = "DRAFT: 23 native routes and Windows teacher GUI require separate evidence"
    (output / "COMPOSITION.json").write_text(
        json.dumps(provenance, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    (output / "README-WINDOWS.md").write_text(
        "# WebeeBlocks — progression A1–A7 (livrable expérimental)\n\n"
        "Exécuter Lancer-Progression.cmd, sélectionner l'activité et le parcours, "
        "puis utiliser Démarrer une activité pour créer le programme Blockly vierge.\n"
        "Pour changer de variante : enregistrer sous .wbb, fermer Webots, "
        "relancer le même numéro d'activité avec un autre parcours, ouvrir le même .wbb.\n"
        "STOP, RESET, décollage et pose sont régis par le pilote natif. "
        "La validation Windows enseignant et l'acceptation pédagogique restent requises.\n",
        encoding="utf-8")
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
    args = parser.parse_args()
    archive = compose(args.source, args.output)
    print("GP_PROGRESSION_WINDOWS_DRAFT_ZIP", archive, digest(archive))


if __name__ == "__main__":
    main()
