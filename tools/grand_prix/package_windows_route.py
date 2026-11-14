"""Assemble an *experimental* Windows variable Grand Prix from reviewed closures.

The teacher's scene, flight source, native oracles and R2025a PROTOs are not
modified. The U delivery is an input *dependency*, never variable-course proof.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.grand_prix.package_windows_u import verified_files, digest, replace_once
from tools.grand_prix.course_active_world_v2 import active_course_world
from tools.grand_prix.route_courses_v2 import reference_course

PR970_SHA = "6486e73ccc193da3d609e45e73e7c0687b84ecc4"
NAME = "WebeeBlocks-Grand-Prix-Variable-Windows-R2025a"
DEFAULT_FPS = 20
FPS_MIN = 1
FPS_MAX = 60
FPS = (DEFAULT_FPS,)  # only pre-attested base worlds; FPS variants are isolated at launch
WEBOTS_SOURCE_SHA = "c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b"


def exact_sha():
    sha = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                                  text=True).strip()
    if re.fullmatch(r"[0-9a-f]{40}", sha) is None:
        raise ValueError("Exact source SHA required")
    subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor",
                    PR970_SHA, sha], check=True)
    source = (ROOT / "tools/grand_prix/evaluator_publisher_v2.py").read_text(encoding="utf-8")
    if (source.count("SCENE_POLICY_CLASSROOM_STATIC = 'classroom-static-v1'") != 1 or
            "scene_policy=\'classroom-static-v1\'" not in source):
        raise ValueError("Exact #970 classroom-static-v1 admission entry missing")
    return sha


def copy_controller(output, classroom, webots_home):
    binary = ROOT / "controllers/grand_prix_route_flight/grand_prix_route_flight.exe"
    if not binary.is_file() or not binary.stat().st_size:
        raise ValueError("The real native route Windows pilot must be compiled first")
    target = output / "controllers/grand_prix_route_flight"
    target.mkdir(parents=True)
    shutil.copyfile(binary, target / binary.name)
    ini = classroom / "controllers/crazyflie_runtime_v2/runtime.ini"
    if "WEBOTS_LIBRARY_PATH" not in ini.read_text(encoding="utf-8"):
        raise ValueError("Classroom DLL runtime contract missing")
    shutil.copyfile(ini, target / "runtime.ini")


def copy_evaluator(output, evaluated):
    # The historical U evaluator supplies only a verified embedded CPython
    # interpreter, NEVER the U evaluator/geometry/oracle implementation.
    source = evaluated / "runtime/python"
    target = output / "runtime/python"
    shutil.copytree(source, target)
    if not (target / "webeeblocks-gp-python.exe").is_file():
        raise ValueError("Embedded Python executable missing")
    if (target / "python312._pth").read_text() != "python312.zip\n.\n":
        raise ValueError("Embedded Python isolation changed")
    controller = output / "controllers/grand_prix_route_evaluator"
    controller.mkdir(parents=True)
    shutil.copyfile(
        ROOT / "controllers/grand_prix_route_evaluator/grand_prix_route_evaluator.py",
        controller / "evaluator_impl.py")
    shutil.copyfile(ROOT / "packaging/windows/grand_prix_route_evaluator_bootstrap.py",
                    controller / "grand_prix_route_evaluator.py")
    (controller / "runtime.ini").write_text(
        "[python]\nCOMMAND = $(WEBEEBLOCKS_GP_PYTHON_DIR)/webeeblocks-gp-python.exe\nOPTIONS = -I\n",
        encoding="utf-8")
    # The shipped evaluator is the *exact* reviewable source on this SHA,
    # not a generated fork. Restrict the embedded directory to this read-only
    # project-namespace closure; source is small and supports audit/debug.
    gp_src = ROOT / "tools/grand_prix"
    gp_dst = output / "tools/grand_prix"
    gp_dst.mkdir(parents=True)
    for path in sorted(gp_src.glob("*.py")):
        shutil.copyfile(path, gp_dst / path.name)
    shutil.copyfile(ROOT / "packaging/windows/grand_prix_python_lock.json",
                    output / "PYTHON-SOURCE.json")


def stage_native_webots_protos(output, classroom, webots_source):
    """Ship pinned R2025a PROTO + asset closure; do not rewrite physics.

    The official Windows installer alone does not ship these sample-project
    PROTOs. The source checkout is the immutable, sparse-pinned Webots commit.
    """
    source = Path(webots_source).resolve(strict=True)
    actual = subprocess.check_output(
        ["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    if actual != WEBOTS_SOURCE_SHA:
        raise ValueError("Webots PROTO source is not the pinned R2025a commit")
    protos = output / "protos"
    if not (protos / "Crazyflie.proto").is_file():
        raise ValueError("Verified local Crazyflie native PROTO missing")
    sources = {
        "TexturedBackground.proto":
            "objects/backgrounds/protos/TexturedBackground.proto",
        "TexturedBackgroundLight.proto":
            "objects/backgrounds/protos/TexturedBackgroundLight.proto",
        "Floor.proto": "objects/floors/protos/Floor.proto",
        "Parquetry.proto": "appearances/protos/Parquetry.proto",
    }
    for name, subpath in sources.items():
        path = source / "projects" / subpath
        content = path.read_text(encoding="utf-8")
        if not content.startswith("#VRML_SIM R2025a utf8"):
            raise ValueError("Mismatched official R2025a PROTO: " + name)
        if name == "Floor.proto":
            old = 'EXTERNPROTO "webots://projects/appearances/protos/Parquetry.proto"'
            if content.count(old) != 1:
                raise ValueError("Floor default appearance closure changed")
            content = content.replace(old, 'EXTERNPROTO "Parquetry.proto"')
        elif name == "TexturedBackground.proto":
            old = "'webots://projects/default/worlds/textures/cubic'"
            if content.count(old) != 1:
                raise ValueError("Official background skybox resource changed")
            content = content.replace(old, "'textures/cubic'")
        (protos / name).write_text(content, encoding="utf-8")
    parquetry = protos / "textures/parquetry"
    parquetry.mkdir(parents=True)
    for kind in ("base_color", "roughness", "normal", "occlusion"):
        file = f"chequered_parquetry_{kind}.jpg"
        # The classroom builder already certifies these original R2025a images.
        shutil.copyfile(classroom / "worlds/textures/parquetry" / file,
                        parquetry / file)
    cubic = protos / "textures/cubic"
    cubic.mkdir(parents=True)
    for direction in ("back", "bottom", "front", "left", "right", "top"):
        for extension in ("jpg", "hdr"):
            file = f"mountains_{direction}.{extension}"
            shutil.copyfile(
                source / "projects/default/worlds/textures/cubic" / file,
                cubic / file)


def configure_windows_route_fps(scene, fps):
    """Compose only native viewport FPS for the Windows 1..60 slider trial.

    The shared Linux/historical composer and all 8-ms physics stay unchanged.
    """
    if type(fps) is not int or fps < FPS_MIN or fps > FPS_MAX:
        raise ValueError("Unsupported experimental Windows Grand Prix FPS")
    anchor = ("DEF WEBEEBLOCKS_DEDICATED_RUNTIME_WORLD WorldInfo { "
              "basicTimeStep 8 randomSeed 1 ")
    if (scene.count(anchor) != 1 or scene.count("WorldInfo {") != 1 or
            " FPS " in scene.split("}", 1)[0]):
        raise RuntimeError("Unexpected native WorldInfo; refusing FPS composition")
    return scene.replace(anchor, anchor + f"FPS {fps} ", 1)


def route_world(course_index, fps):
    course = reference_course(course_index)
    scene = configure_windows_route_fps(active_course_world(course), fps)
    # Keep every original PROTO node and its geometry. Only bind imports to
    # pinned, verified local R2025a copies, instead of absent installer projects.
    external = {
        "Crazyflie": "robots/bitcraze/crazyflie/protos",
        "TexturedBackground": "objects/backgrounds/protos",
        "TexturedBackgroundLight": "objects/backgrounds/protos",
        "Floor": "objects/floors/protos",
    }
    for name, location in external.items():
        old = f'EXTERNPROTO "webots://projects/{location}/{name}.proto"'
        new = f'EXTERNPROTO "../protos/{name}.proto"'
        if scene.count(old) != 1:
            raise ValueError("Canonical native Webots PROTO reference changed: " + name)
        scene = scene.replace(old, new)
    if (scene.count('controller "grand_prix_route_flight"') != 1 or
            scene.count('controller "grand_prix_route_evaluator"') != 1 or
            scene.count('window "grand_prix_route_v2"') != 1 or
            scene.count('controllerArgs [ "' + course.identifier + '" ]') != 2 or
            scene.count("basicTimeStep 8") != 1 or
            scene.count("FPS " + str(fps) + " ") != 1):
        raise ValueError("Variable-route native scene identity/timestep altered")
    if re.search(r'"(?:https?|webots)://', scene):
        raise ValueError("No remote or missing-project resources in distributed scenes")
    # 'webots://' resolves exclusively in the installed, verified R2025a tree.
    # Keeping the genuine Floor PROTO is required by native attestation.
    if scene.count("Floor {") != 1:
        raise ValueError("Native Floor PROTO must remain intact")
    return scene, course.identifier


def launch_script(text):
    old = "$world = Join-Path $PSScriptRoot 'worlds\\crazyflie_runtime_v2.wbt'"
    new = (
        "$indexText = if ($env:WEBEEBLOCKS_GP_INDEX) { $env:WEBEEBLOCKS_GP_INDEX } else { '5' }\n"
        "$fpsText = if ($env:WEBEEBLOCKS_GP_FPS) { $env:WEBEEBLOCKS_GP_FPS } else { '20' }\n"
        "if ($indexText -cnotmatch '^(?:[0-9]|10|11)$' -or $fpsText -cnotmatch '^(?:[1-9]|[1-5][0-9]|60)$') {\n"
        "  throw 'Configuration Grand Prix ou FPS incorrects : index 0..11, FPS 1..60.'\n"
        "}\n"
        "$index = [int]$indexText\n"
        "$env:WEBEEBLOCKS_GP_PYTHON_DIR = Join-Path $PSScriptRoot 'runtime\\python'\n"
        "$world = Join-Path $PSScriptRoot (('worlds\\grand_prix_route_v2_{0:D2}_fps20.wbt' -f $index))")
    text = replace_once(text, old, new)
    # The .cmd invokes Windows PowerShell 5.1, where Get-Content -Raw
    # decodes UTF-8-without-BOM world files using the system ANSI codepage.
    # Native scene attestation compares the copied UTF-8 text byte-equivalently.
    # Decode both canonical scene/perspective explicitly, without relaxing
    # the existing copy comparison or native identity gate.
    text = replace_once(text,
        "$worldText = Get-Content -LiteralPath $world -Raw",
        "$worldText = [IO.File]::ReadAllText($world, [Text.Encoding]::UTF8)")
    text = replace_once(text,
        "$worldPerspectiveText = Get-Content -LiteralPath $worldPerspective -Raw",
        "$worldPerspectiveText = [IO.File]::ReadAllText($worldPerspective, [Text.Encoding]::UTF8)")
    text = replace_once(text, '$worldText -match \'"(?:https?|webots)://\'',
                        '$worldText -match \'"https?://\'')
    text = replace_once(text, "(blockly_v2_[0-9a-f]{16})", "(grand_prix_route_v2)")
    start = text.index("function New-WebeeBlocksRobotWindowSession {")
    end = text.index("function Get-WebeeBlocksContentType {")
    # Keep Webots' original window="grand_prix_route_v2" byte-for-byte. This is
    # mandatory for the #970 native identity attestation. Isolate the entire
    # installed project (not a modified main-world or shared HTML) per launch.
    replacement = r"""
function New-WebeeBlocksRobotWindowSession {
  param($RobotWindow, [string]$WorldText, [string]$PerspectivePath, [int]$RequestedFps)
  $token = [Guid]::NewGuid().ToString('N').Substring(0, 12)
  $staging = Join-Path $PSScriptRoot ("._gp_route_session_" + $PID + "_" + $token)
  if (Test-Path -LiteralPath $staging) { throw 'Session deja existante.' }
  New-Item -ItemType Directory -Path $staging | Out-Null
  try {
    foreach ($item in Get-ChildItem -LiteralPath $PSScriptRoot -Force) {
      if ($item.Name -like '._gp_route_session_*') { continue }
      Copy-Item -LiteralPath $item.FullName -Destination $staging -Recurse -Force
    }
    # powershell.exe on Windows 10/11 is Windows PowerShell 5.1/.NET Framework,
    # whose System.IO.Path lacks GetRelativePath. Both inputs must stay in the
    # single canonical "worlds" folder: never accept an external file.
    $canonicalWorldDir = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'worlds'))
    $sourceWorldDir = [IO.Path]::GetFullPath((Split-Path -Parent $world))
    $sourcePerspectiveDir = [IO.Path]::GetFullPath((Split-Path -Parent $PerspectivePath))
    if (-not $sourceWorldDir.Equals($canonicalWorldDir, [StringComparison]::OrdinalIgnoreCase) -or
        -not $sourcePerspectiveDir.Equals($canonicalWorldDir, [StringComparison]::OrdinalIgnoreCase)) {
      throw 'World/perspective outside canonical packaged worlds directory.'
    }
    $relativeWorld = Join-Path 'worlds' ([IO.Path]::GetFileName($world))
    $sessionWorld = Join-Path $staging $relativeWorld
    $relativePerspective = Join-Path 'worlds' ([IO.Path]::GetFileName($PerspectivePath))
    $sessionPerspective = Join-Path $staging $relativePerspective
    $contents = [IO.File]::ReadAllText($sessionWorld, [Text.Encoding]::UTF8)
    if ($contents -cne $WorldText -or
        [regex]::Matches($contents, 'window "grand_prix_route_v2"').Count -ne 1) {
      throw 'Scene/identite native modifiee dans la session.'
    }
    # Check the packaged canonical scene first. Mutate the sole FPS field
    # only in this isolated session, before native Webots attestation/READY.
    if ($RequestedFps -lt 1 -or $RequestedFps -gt 60) {
      throw 'FPS de session hors plage 1..60.'
    }
    $anchor = 'DEF WEBEEBLOCKS_DEDICATED_RUNTIME_WORLD WorldInfo { basicTimeStep 8 randomSeed 1 FPS 20 '
    if ([regex]::Matches($contents, [regex]::Escape($anchor)).Count -ne 1 -or
        [regex]::Matches($contents, 'WorldInfo \{').Count -ne 1) {
      throw 'WorldInfo canonique inattendu : modification FPS refusee.'
    }
    $replacement = $anchor.Replace(' FPS 20 ', (' FPS ' + $RequestedFps + ' '))
    $adjusted = $contents.Replace($anchor, $replacement)
    if ($RequestedFps -ne 20) {
      $originalName = [IO.Path]::GetFileName($sessionWorld)
      if (-not $originalName.EndsWith('_fps20.wbt', [StringComparison]::Ordinal)) {
        throw 'Nom du monde canonique inattendu.'
      }
      $name = $originalName.Substring(0, $originalName.Length - 6) + $RequestedFps + '.wbt'
      $targetWorld = Join-Path (Split-Path -Parent $sessionWorld) $name
      $targetPerspective = Join-Path (Split-Path -Parent $sessionPerspective) ('.' + [IO.Path]::GetFileNameWithoutExtension($name) + '.wbproj')
      if ((Test-Path -LiteralPath $targetWorld) -or (Test-Path -LiteralPath $targetPerspective)) {
        throw 'Fichier FPS de session deja present.'
      }
      [IO.File]::WriteAllText($targetWorld, $adjusted, [Text.UTF8Encoding]::new($false))
      Copy-Item -LiteralPath $sessionPerspective -Destination $targetPerspective
      $sessionWorld = $targetWorld
      $sessionPerspective = $targetPerspective
    }
    if ([IO.File]::ReadAllText($sessionWorld, [Text.Encoding]::UTF8) -cne $adjusted -or
        [regex]::Matches($adjusted, 'FPS ' + [regex]::Escape([string]$RequestedFps) + ' ').Count -ne 1) {
      throw 'Modification FPS strictement bornee non verifiee.'
    }
    $view = [IO.File]::ReadAllText($sessionPerspective, [Text.Encoding]::UTF8)
    $clean = [regex]::Replace($view,
       '(?m)^robotWindow:\s+Crazyflie WebeeBlocks\s*\r?\n?', '')
    if ($clean -eq $view -or
        [regex]::Matches($clean, '(?m)^robotWindow:').Count -ne 0) {
      throw 'Perspective native de session non conforme.'
    }
    [IO.File]::WriteAllText($sessionPerspective, $clean, [Text.UTF8Encoding]::new($false))
    $root = Join-Path $staging 'plugins\robot_windows\grand_prix_route_v2'
    $html = Join-Path $root 'grand_prix_route_v2.html'
    if (-not (Test-Path -LiteralPath $html -PathType Leaf)) {
      throw 'Robot Window canonique absente de la session.'
    }
    return [PSCustomObject]@{
      Name = 'grand_prix_route_v2'
      Root = $root
      Html = $html
      World = $sessionWorld
      Perspective = $sessionPerspective
      Staging = $staging
    }
  }
  catch {
    Remove-Item -LiteralPath $staging -Recurse -Force -ErrorAction SilentlyContinue
    throw
  }
}
function Remove-WebeeBlocksRobotWindowSession {
  param($Session)
  if ($null -eq $Session) { return }
  $parent = [IO.Path]::GetFullPath($PSScriptRoot)
  $path = [IO.Path]::GetFullPath($Session.Staging)
  if ((Split-Path -Parent $path) -ne $parent -or
      (Split-Path -Leaf $path) -notmatch '^\._gp_route_session_[0-9]+_[0-9a-f]{12}$') {
    throw 'Refus de nettoyer un dossier de session etranger.'
  }
  if (Test-Path -LiteralPath $path) {
    Remove-Item -LiteralPath $path -Recurse -Force
  }
}
"""
    text = text[:start] + replacement + "\n" + text[end:]
    start = text.index("if ($ValidateOnly) {")
    end = text.index("$server = $null", start)
    replacement = r"""
if ($ValidateOnly) {
  # This must execute the *same* real launcher session preparation as normal,
  # using Windows PowerShell 5.1, without launching Chrome or Webots. Merely
  # checking the world text would miss unsupported .NET methods in the GUI path.
  if ($worldText -cnotmatch 'window "grand_prix_route_v2"' -or
      $worldText -cnotmatch 'basicTimeStep 8' -or
      $worldText -cnotmatch 'FPS 20' -or
      $worldText -cnotmatch 'controller "grand_prix_route_evaluator"') {
    throw 'Scene Grand Prix variable incomplete.'
  }
  $testServer = $null
  $testSession = $null
  try {
    $testServer = Start-WebeeBlocksLocalServer -Root $PSScriptRoot
    $testSession = New-WebeeBlocksRobotWindowSession -RobotWindow $robotWindow -WorldText $worldText -PerspectivePath $worldPerspective -RequestedFps ([int]$fpsText)
    Set-WebeeBlocksSessionHtml -Session $testSession -Port $testServer.Port | Out-Null
    $stagedWorldText = [IO.File]::ReadAllText($testSession.World, [Text.Encoding]::UTF8)
    if ($stagedWorldText -cnotmatch ('FPS ' + [regex]::Escape([string]$fpsText) + ' ') -or
        [IO.Path]::GetFileName($testSession.World) -cnotmatch ('_fps' + [regex]::Escape([string]$fpsText) + '\.wbt$')) {
      throw 'FPS natifs de session incorrects.'
    }
    if (-not (Test-Path -LiteralPath $testSession.World -PathType Leaf) -or
        -not (Test-Path -LiteralPath $testSession.Html -PathType Leaf) -or
        -not (Test-Path -LiteralPath $testSession.Perspective -PathType Leaf) -or
        -not (Test-Path -LiteralPath (Join-Path $testSession.Staging 'runtime\python') -PathType Container) -or
        -not ([IO.File]::ReadAllText($testSession.Html).Contains('http://127.0.0.1:'))) {
      throw 'Real isolated Windows session/HTML/Python preparation incomplete.'
    }
  }
  finally {
    Stop-WebeeBlocksLocalServer -Server $testServer
    Remove-WebeeBlocksRobotWindowSession -Session $testSession
  }
  if ($null -eq $testSession -or (Test-Path -LiteralPath $testSession.Staging)) {
    throw 'Native Windows session cleanup failed.'
  }
  Write-Host 'GP_ROUTE_WINDOWS_LAUNCHER_SESSION_STAGED_OK (not GUI/READY)'
  exit 0
}

"""
    text = text[:start] + replacement + text[end:]
    # The ordinary GUI path must use the same bounded preflight staging.
    text = replace_once(text,
        "  $session = New-WebeeBlocksRobotWindowSession -RobotWindow $robotWindow -WorldText $worldText -PerspectivePath $worldPerspective",
        "  $session = New-WebeeBlocksRobotWindowSession -RobotWindow $robotWindow -WorldText $worldText -PerspectivePath $worldPerspective -RequestedFps ([int]$fpsText)")
    # The actual embedded interpreter must be in the isolated session root.
    text = replace_once(text, "  $webotsProcess = Start-Process -FilePath $webots",
        "  $env:WEBEEBLOCKS_GP_PYTHON_DIR = Join-Path $session.Staging 'runtime\\python'\n"
        "  $webotsProcess = Start-Process -FilePath $webots")
    if ('New-WebeeBlocksRobotWindowSession' not in text or
            'grand_prix_route_v2' not in text or
            'GetRelativePath(' in text or
            'GP_ROUTE_WINDOWS_LAUNCHER_SESSION_STAGED_OK' not in text):
        raise ValueError("Packaged launcher patch failed")
    return text


def compose(classroom, evaluated, webots_home, webots_source, output):
    sha = exact_sha()
    files = {"classroom": verified_files(classroom),
             "python_support": verified_files(evaluated)}
    if (evaluated / "SOURCE_SHA").read_text(encoding="utf-8").strip() != sha:
        raise ValueError("Embedded Python built from a different source SHA")
    if (Path(webots_home) / "resources/version.txt").read_text(encoding="utf-8").strip() != "R2025a":
        raise ValueError("Only installed Webots R2025a is accepted")
    if output.exists():
        raise ValueError("Use a new, empty output path")
    shutil.copytree(classroom, output)
    for name in ("controllers", "worlds", "Activites"):
        shutil.rmtree(output / name)
    (output / "WINDOWS-ACCEPTANCE.md").unlink(missing_ok=True)
    stage_native_webots_protos(output, classroom, webots_source)
    copy_controller(output, classroom, webots_home)
    copy_evaluator(output, evaluated)
    windows = output / "plugins/robot_windows"
    legacy = list(windows.glob("blockly_v2_[0-9a-f]*"))
    if len(legacy) != 1 or (windows / "blockly_v2").exists():
        raise ValueError("Expected exactly one versioned classroom Blockly closure")
    legacy[0].rename(windows / "blockly_v2")
    old_html = windows / "blockly_v2" / (legacy[0].name + ".html")
    old_html.unlink(missing_ok=True)
    target_window = windows / "grand_prix_route_v2"
    target_window.mkdir()
    for name in ("grand_prix_route_v2.html", "setup.js"):
        shutil.copyfile(ROOT / "plugins/robot_windows/grand_prix_route_v2" / name,
                        target_window / name)
    worlds = output / "worlds"
    worlds.mkdir()
    course_ids = []
    for index in range(12):
        course_ids.append(reference_course(index).identifier)
        for fps in FPS:
            scene, _ = route_world(index, fps)
            label = f"grand_prix_route_v2_{index:02d}_fps{fps}"
            (worlds / (label + ".wbt")).write_text(scene, encoding="utf-8")
            shutil.copyfile(ROOT / "worlds/.crazyflie_runtime_v2.wbproj",
                            worlds / ("." + label + ".wbproj"))
    launch = output / "Launch-WebeeBlocks.ps1"
    launch.write_text(launch_script(launch.read_text(encoding="utf-8-sig")),
                      encoding="utf-8-sig")
    (output / "Lancer-Grand-Prix.cmd").write_text(
        '@echo off\r\npowershell.exe -STA -NoProfile -ExecutionPolicy Bypass -File "%~dp0Lancer-Grand-Prix.ps1"\r\n'
        'exit /b %ERRORLEVEL%\r\n', encoding="utf-8")
    shutil.copyfile(ROOT / "packaging/windows/Lancer-Grand-Prix.ps1",
                    output / "Lancer-Grand-Prix.ps1")
    (output / "Activites").mkdir()
    starter = {
        "format": "webeeblocks-project", "version": 1,
        "activity": {"id": "progression-grand-prix-route-v2",
                     "semantics": "webeeblocks-ast-v1"},
        "workspace": {"blocks": {"languageVersion": 0, "blocks": []}}
    }
    (output / "Activites/08-grand-prix-variable.wbb").write_text(
        json.dumps(starter, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "SOURCE_SHA").write_text(sha + "\n", encoding="utf-8")
    (output / "PR970_SHA").write_text(PR970_SHA + "\n", encoding="utf-8")
    (output / "COURSES.json").write_text(json.dumps({
        "profile": "progression-grand-prix-route-v2",
        "course_ids": course_ids, "fps": list(FPS),
        "fps_default": DEFAULT_FPS, "fps_min": FPS_MIN, "fps_max": FPS_MAX,
        "fps_step": 1, "fps_session_only": True, "physics_step_ms": 8
    }, indent=2) + "\n", encoding="utf-8")
    shutil.copyfile(ROOT / "docs/GRAND_PRIX_ROUTE_WINDOWS_EXPERIMENT.md",
                    output / "README-WINDOWS.md")
    provenance = {
        "schema": 1, "source_sha": sha, "dependency_pr": 970,
        "dependency_sha": PR970_SHA, "scene_policy": "classroom-static-v1",
        "webots_source_sha": WEBOTS_SOURCE_SHA,
        "webots": "R2025a", "blockly": "13.2.1",
        "windows_support_manifest": digest(classroom / "MANIFEST.sha256"),
        "python_support_manifest": digest(evaluated / "MANIFEST.sha256"),
        "pilot_binary_sha256": digest(ROOT / "controllers/grand_prix_route_flight/grand_prix_route_flight.exe"),
        "inputs": {key: {"files": len(entries)} for key, entries in files.items()},
        "qualification": "UNPROVEN: native and personal GUI evidence required",
    }
    (output / "COMPOSITION.json").write_text(
        json.dumps(provenance, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    manifest = "\n".join(
        f"{digest(p)}  {p.relative_to(output).as_posix()}"
        for p in sorted(output.rglob("*")) if p.is_file() and p.name != "MANIFEST.sha256")
    (output / "MANIFEST.sha256").write_text(manifest + "\n", encoding="utf-8")
    verified_files(output)
    archive = output.with_suffix(".zip")
    if archive.exists():
        raise ValueError("ZIP target already exists")
    # Stable order, timestamps and permissions. Reproducibility presupposes
    # identical, version-locked input binaries and build tools.
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
    (archive.with_suffix(".zip.sha256")).write_text(
        digest(archive) + "  " + archive.name + "\n", encoding="utf-8")
    return archive


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--classroom", type=Path, required=True)
    parser.add_argument("--python-support", type=Path, required=True)
    parser.add_argument("--webots-home", type=Path, required=True)
    parser.add_argument("--webots-source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    options = parser.parse_args()
    path = compose(options.classroom, options.python_support,
                   options.webots_home, options.webots_source, options.output)
    print("GP_ROUTE_WINDOWS_ZIP", path, digest(path))


if __name__ == "__main__":
    main()
