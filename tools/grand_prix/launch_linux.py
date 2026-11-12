#!/usr/bin/env python3
"""Interactive Linux Grand Prix launcher, with explicit canonical selection.

Native safety remains with the real evaluator/pilot; this launcher cannot grant
READY. GUI, OS file dialogs and the user journey require separate observation.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.grand_prix.layout_u import generate, world_text  # noqa: E402

BLOCKLY = ROOT / "plugins/robot_windows/blockly_v2"
FLIGHT = ROOT / "controllers/grand_prix_u_flight"
EVALUATOR = ROOT / "controllers/grand_prix_u_evaluator/grand_prix_u_evaluator.py"
ROUTE_FLIGHT = ROOT / "controllers/grand_prix_route_flight"
ROUTE_EVALUATOR = ROOT / "controllers/grand_prix_route_evaluator/grand_prix_route_evaluator.py"


def render_legacy_u(seed):
    """Use the existing evaluator, the real robot window and native 8-ms world."""
    source = world_text(
        generate(seed, 2.0),
        controller="grand_prix_u_flight",
        window="grand_prix_u",
        evaluator=True,
    )
    return source.replace(
        "https://raw.githubusercontent.com/cyberbotics/webots/R2025a/",
        "webots://",
    )


def render_route(course):
    """Compose the actual variable world; no alternate geometry or authority."""
    from tools.grand_prix.course_active_world_v2 import active_course_world
    source = active_course_world(course)
    if (source.count('  controller "grand_prix_route_flight"\n') != 1 or
            source.count('  controller "grand_prix_route_evaluator"\n') != 1 or
            source.count('  window "grand_prix_route_v2"\n') != 1 or
            source.count('DEF GP_ROUTE_EVALUATOR Robot {') != 1 or
            source.count('  controller "<none>"\n') != 0):
        raise RuntimeError("identités du monde Grand Prix variable incohérentes")
    return source.replace(
        "https://raw.githubusercontent.com/cyberbotics/webots/R2025a/", "webots://")


def configure_render_fps(scene, fps):
    """Control only the 3D display budget for a #912 A/B, never the 8-ms physics.

    The unmodified launcher remains the control arm; an explicit variant must
    match the canonical, already composed WorldInfo anchor or fail closed.
    """
    if fps is None:
        return scene
    if type(fps) is not int or fps not in (25, 30, 60):
        raise ValueError("fréquence de rendu expérimentale invalide")
    anchor = ("DEF WEBEEBLOCKS_DEDICATED_RUNTIME_WORLD WorldInfo { "
              "basicTimeStep 8 randomSeed 1 ")
    if (scene.count(anchor) != 1 or scene.count("WorldInfo {") != 1 or
            " FPS " in scene.split("}", 1)[0]):
        raise RuntimeError("WorldInfo Grand Prix inattendu : refus de modifier le rendu")
    return scene.replace(anchor, anchor + f"FPS {fps} ", 1)


def prepare_route_native(home):
    """Build the existing production route pilot, never a test/probe binary."""
    if not ROUTE_EVALUATOR.is_file():
        raise RuntimeError(f"Évaluateur Grand Prix variable absent : {ROUTE_EVALUATOR}")
    ensure_webots_assets(home)
    ensure_blockly_assets()
    env = os.environ.copy()
    env["WEBOTS_HOME"] = str(home)
    subprocess.run([sys.executable, str(ROOT / "tools/grand_prix/prepare_route_runtime.py")],
                   cwd=ROOT, env=env, check=True)
    subprocess.run(["make", "-C", str(ROUTE_FLIGHT), "release"], cwd=ROOT, env=env, check=True)
    binary = ROUTE_FLIGHT / "grand_prix_route_flight"
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise RuntimeError(f"Contrôleur Grand Prix variable compilé introuvable : {binary}")
    return env


def reference_configurations():
    """List the 12 reproducible host-only route IDs; never admit a flight.

    This discovery command is deliberately independent of native Webots and
    does not activate the variable world, evaluator or pupil runtime.
    """
    from tools.grand_prix.route_courses_v2 import reference_course
    return tuple((index, reference_course(index).identifier)
                 for index in range(12))


def webots_home(explicit):
    candidate = explicit or os.environ.get("WEBOTS_HOME")
    if not candidate:
        executable = shutil.which("webots")
        if executable:
            candidate = str(Path(executable).resolve().parent)
    if not candidate:
        raise RuntimeError(
            "Webots introuvable : installer R2025a, puis définir WEBOTS_HOME "
            "ou passer --webots-home /chemin/vers/webots"
        )
    home = Path(candidate).expanduser().resolve()
    binary = home / "webots"
    version_file = home / "resources/version.txt"
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise RuntimeError(f"Exécutable Webots absent ou non exécutable : {binary}")
    if not version_file.is_file() or version_file.read_text(encoding="utf-8").strip() != "R2025a":
        raise RuntimeError(f"Webots R2025a strictement requis : {version_file}")
    return home


def ensure_webots_assets(home, lock_path=ROOT / "tools/ci/runtime_v2_outcome_assets.lock.json"):
    """Verify the pinned local R2025a PROTO closure; never fetch at GUI launch."""
    manifest = json.loads(Path(lock_path).read_text(encoding="utf-8"))
    if (manifest.get("schema") != 1 or
            manifest.get("source_commit") != "c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b"):
        raise RuntimeError("Inventaire des ressources Webots non reconnu")
    assets = manifest.get("assets")
    if not isinstance(assets, list) or not 0 < len(assets) <= 64:
        raise RuntimeError("Inventaire des ressources Webots invalide")
    seen = set()
    total = 0
    root = Path(home).resolve()
    for item in assets:
        if not isinstance(item, dict):
            raise RuntimeError("Entrée de ressource Webots invalide")
        name, expected_size, digest = item.get("path"), item.get("bytes"), item.get("sha256")
        if not isinstance(name, str):
            raise RuntimeError("Chemin de ressource Webots invalide")
        relative = PurePosixPath(name)
        if (not relative.parts or relative.parts[0] != "projects" or
                ".." in relative.parts or relative.as_posix() != name or
                "\\" in name or name in seen):
            raise RuntimeError(f"Chemin de ressource Webots interdit : {name}")
        if (type(expected_size) is not int or not 0 < expected_size <= 8 * 1024 * 1024 or
                not isinstance(digest, str) or len(digest) != 64 or
                any(ch not in "0123456789abcdef" for ch in digest)):
            raise RuntimeError(f"Empreinte de ressource Webots invalide : {name}")
        seen.add(name)
        total += expected_size
        if total > 16 * 1024 * 1024:
            raise RuntimeError("Inventaire de ressources Webots excessif")
        target = root.joinpath(*relative.parts)
        try:
            target.resolve().relative_to(root)
        except ValueError as exc:
            raise RuntimeError(f"Ressource Webots hors installation : {name}") from exc
        if not target.is_file():
            raise RuntimeError(
                f"Ressource Webots locale absente : {name} ; installer les "
                "ressources officielles complètes de Webots R2025a"
            )
        if target.stat().st_size != expected_size or hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise RuntimeError(
                f"Ressource Webots locale non conforme à l'inventaire épinglé : {name}"
            )
    return len(assets)


def ensure_blockly_assets():
    required = [
        BLOCKLY / "vendor/VERSION",
        BLOCKLY / "vendor/blockly_compressed.js",
        BLOCKLY / "vendor/blocks_compressed.js",
        BLOCKLY / "vendor/msg/fr.js",
        BLOCKLY / "webots/RobotWindow.js",
        BLOCKLY / "webots/request_methods.js",
    ]
    media = BLOCKLY / "vendor/media"
    version = required[0].read_text(encoding="utf-8").strip() if required[0].is_file() else None
    if version != "13.2.1" or not media.is_dir() or any(not p.is_file() or not p.stat().st_size for p in required[1:]):
        print("Préparation Blockly (Node.js >= 22, npm et accès au registre npm requis au premier lancement)...", flush=True)
        subprocess.run(["bash", str(ROOT / "tools/prepare_runtime_v2.sh")], cwd=ROOT, check=True)
    if required[0].read_text(encoding="utf-8").strip() != "13.2.1":
        raise RuntimeError("Version Blockly préparée incohérente")
    if not media.is_dir() or any(not p.is_file() or not p.stat().st_size for p in required[1:]):
        raise RuntimeError("Ressources Blockly ou RobotWindow absentes après préparation")


def prepare_native(home):
    if not EVALUATOR.is_file():
        raise RuntimeError(f"Évaluateur Grand Prix absent : {EVALUATOR}")
    ensure_webots_assets(home)
    ensure_blockly_assets()
    env = os.environ.copy()
    env["WEBOTS_HOME"] = str(home)
    # Fail closed if the shared runtime composition anchors no longer match.
    subprocess.run([sys.executable, str(ROOT / "tools/grand_prix/prepare_u_runtime.py")],
                   cwd=ROOT, env=env, check=True)
    subprocess.run(["make", "-C", str(FLIGHT), "release"], cwd=ROOT, env=env, check=True)
    binary = FLIGHT / "grand_prix_u_flight"
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise RuntimeError(f"Contrôleur natif compilé introuvable : {binary}")
    return env


def classroom_perspective(root):
    """Use the accepted R2025a classroom presentation for temporary worlds.

    The perspective hides the Camera overlay and development docks while
    keeping the native Camera device and Robot Window unchanged.
    """
    text = (root / "worlds/.crazyflie_runtime_v2.wbproj").read_text(encoding="utf-8")
    required = (
        "Webots Project File version R2025a\n",
        "\nperspectives: ",
        "\nsimulationViewPerspectives: ",
        "\nrenderingDevicePerspectives: Crazyflie WebeeBlocks:camera;0;1;0;0\n",
        "\nrobotWindow: Crazyflie WebeeBlocks\n",
    )
    if (not text.startswith(required[0]) or
            any(marker not in text for marker in required[1:]) or
            text.count("robotWindow:") != 1):
        raise RuntimeError("Perspective scolaire Webots R2025a invalide")
    return text


def launch_graphical(home, world, env, *, mode="pause"):
    """Select Webots mode explicitly. Preview/editor/legacy keep their paused default."""
    if mode not in ("pause", "realtime"):
        raise ValueError(f"unsupported Webots launch mode: {mode}")
    return subprocess.run(
        [str(home / "webots"), f"--mode={mode}", "--stdout", "--stderr", str(world)],
        cwd=ROOT, env=env, check=False,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Simulation GUI Linux : parcours Grand Prix variable canonique ou U historique explicite."
    )
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--index", type=int, choices=range(12),
                           help="parcours variable de référence 0..11")
    selection.add_argument("--course-id", help="identifiant CoursePlan canonique à reproduire")
    selection.add_argument("--legacy-u", action="store_true",
                        help="confirmer l'utilisation du parcours U historique (sans cornières en L)")
    parser.add_argument("--seed", type=int, help="graine U 0..65535 (défaut : 4)")
    parser.add_argument("--webots-home", help="répertoire d'installation Webots R2025a")
    parser.add_argument("--render-fps", type=int, choices=(25, 30, 60),
                        help="EXPÉRIENCE A/B #912 : plafond du rendu Webots (25, 30 ou 60 FPS), "
                             "physique 8 ms inchangée, parcours variable seulement")
    parser.add_argument("--preflight-only", action="store_true",
                        help="préparer les ressources natives, sans prétendre valider le GUI")
    parser.add_argument("--list-configurations", action="store_true",
                        help="afficher les 12 parcours variables reproductibles, sans les lancer")
    args = parser.parse_args(argv)
    if args.list_configurations:
        if (args.legacy_u or args.index is not None or args.course_id is not None or
                args.preflight_only or args.webots_home is not None or args.seed is not None or
                args.render_fps is not None):
            parser.error("--list-configurations ne peut pas être combiné avec les options de lancement")
        print("Parcours Grand Prix variables — identifiants hôtes reproductibles :")
        for index, identifier in reference_configurations():
            print(f"  {index:02d}  {identifier}")
        print("NON QUALIFIÉS : liste descriptive seulement ; aucun monde Webots n'est lancé.")
        return 0
    if not args.legacy_u and args.index is None and args.course_id is None:
        parser.error("choisir --index, --course-id ou explicitement --legacy-u")
    if args.legacy_u and args.render_fps is not None:
        parser.error("--render-fps est réservé au Grand Prix variable")
    if not args.legacy_u and args.seed is not None:
        parser.error("--seed est réservé au U historique ; utiliser --course-id pour une variante")
    seed = 4 if args.seed is None else args.seed
    if not 0 <= seed <= 65535:
        parser.error("--seed doit être compris entre 0 et 65535")
    try:
        # Resolve/validate the complete host selection before any build or GUI.
        if args.legacy_u:
            scene = render_legacy_u(seed)
            label = f"U historique : graine={seed}"
        else:
            from tools.grand_prix.route_courses_v2 import reference_course, course_from_identifier
            course = (reference_course(args.index) if args.index is not None
                      else course_from_identifier(args.course_id))
            scene = render_route(course)
            if args.render_fps is not None:
                scene = configure_render_fps(scene, args.render_fps)
            label = "parcours variable : " + course.identifier
            if args.render_fps is not None:
                label += f" ; plafond rendu {args.render_fps} FPS (A/B #912, non qualifié)"
        if not args.preflight_only and not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
            raise RuntimeError("Session graphique absente : ouvrir une session Linux avec affichage")
        home = webots_home(args.webots_home)
        if not args.preflight_only:
            perspective_text = classroom_perspective(ROOT)
        env = prepare_native(home) if args.legacy_u else prepare_route_native(home)
        if args.preflight_only:
            print("Préflight technique terminé ; aucun test GUI ni vol simulé n'a été exécuté.")
            return 0
        fd, name = tempfile.mkstemp(prefix="gp_u_linux_" if args.legacy_u else "gp_route_linux_",
                                    suffix=".wbt", dir=ROOT / "worlds")
        world = Path(name)
        project = world.with_name("." + world.stem + ".wbproj")
        owns_project = False
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(scene)
            # One fresh per-world perspective; never overwrite a teacher file.
            with project.open("x", encoding="utf-8") as stream:
                owns_project = True
                stream.write(perspective_text)
            print(f"Simulation Grand Prix {label}, monde={world}", flush=True)
            print("La réussite de cette ouverture n'atteste pas encore le cycle GUI/Save/Open.", flush=True)
            # The pupil's route starts READY without clicking the Webots triangle.
            # No TAKEOFF is issued until the pupil starts their Blockly program.
            mode = "pause" if args.legacy_u else "realtime"
            result = launch_graphical(home, world, env, mode=mode)
            return result.returncode
        finally:
            world.unlink(missing_ok=True)
            if owns_project:
                project.unlink(missing_ok=True)
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"ÉCHEC préparation/lancement Grand Prix Linux : {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
