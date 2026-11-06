#!/usr/bin/env python3
"""Linux Blockly/file-dialog sandbox on a canonical variable Grand Prix world.

This is NOT a route mission launcher. The evaluator controller is deliberately
disabled even if a native publisher is installed, so TAKEOFF cannot acquire
the mandatory native READY. Native GUI/Save/Open remains to be observed.
"""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.grand_prix.course_active_world_v2 import (
    active_course_world, EVALUATOR_CONTROLLER,
)
from tools.grand_prix.route_courses_v2 import (
    course_from_identifier, reference_course,
)
from tools.grand_prix.launch_linux import (
    ensure_webots_assets, ensure_blockly_assets, launch_graphical, webots_home,
)

FLIGHT = ROOT / "controllers/grand_prix_route_flight"
PREPARE = ROOT / "tools/grand_prix/prepare_route_runtime.py"


def render_editor_sandbox(course):
    """Preserve the entire active scene except the evaluator's execution.

    Flight still uses the real native runtime and Robot Window, but cannot
    obtain READY. Never silently turn this educational file-preview into a
    mission or sensor/flight qualification.
    """
    source = active_course_world(course)
    evaluator = f'  controller "{EVALUATOR_CONTROLLER}"\n'
    if (source.count(evaluator) != 1 or
            source.count('  controller "grand_prix_route_flight"\n') != 1 or
            source.count('  window "grand_prix_route_v2"\n') != 1 or
            source.count('DEF GP_ROUTE_EVALUATOR Robot {') != 1 or
            source.count('  controller "<none>"\n') != 0):
        raise RuntimeError("variable course execution identities changed")
    source = source.replace(evaluator, '  controller "<none>"\n', 1)
    return source


def prepare_editor(home):
    """Prepare strict official R2025a/Blockly and build the route flight binary."""
    ensure_webots_assets(home)
    ensure_blockly_assets()
    env = os.environ.copy()
    env["WEBOTS_HOME"] = str(home)
    subprocess.run([sys.executable, str(PREPARE)], cwd=ROOT, env=env, check=True)
    subprocess.run(["make", "-C", str(FLIGHT), "release"], cwd=ROOT, env=env, check=True)
    binary = FLIGHT / "grand_prix_route_flight"
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise RuntimeError("contrôleur Grand Prix variable compilé introuvable")
    return env


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="SANDBOX Blockly Linux : monde variable canonique, vol interdit (pas de READY)."
    )
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--index", type=int, choices=range(12),
                           help="configuration de référence 0..11")
    selection.add_argument("--course-id", help="CoursePlan canonique, fourni par l'hôte")
    parser.add_argument("--webots-home", help="répertoire Webots R2025a officiel")
    parser.add_argument("--preflight-only", action="store_true",
                        help="vérifier et compiler sans ouvrir Webots")
    parser.add_argument("--editor-sandbox", action="store_true",
                        help="confirmer le mode expérimental, sans autorisation TAKEOFF")
    args = parser.parse_args(argv)
    if not args.preflight_only and not args.editor_sandbox:
        parser.error("le GUI expérimental exige --editor-sandbox ; aucun vol n'est autorisé")
    try:
        # Decode the host-only selection BEFORE any Webots or build side effect.
        course = (reference_course(args.index) if args.index is not None
                  else course_from_identifier(args.course_id))
        scene = render_editor_sandbox(course)
        if not args.preflight_only and not (
                os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
            raise RuntimeError("session graphique Linux absente")
        home = webots_home(args.webots_home)
        env = prepare_editor(home)
        if args.preflight_only:
            print("SANDBOX : préflight/compilation seulement, sans READY ni preuve GUI.")
            return 0
        fd, filename = tempfile.mkstemp(prefix="gp_v2_editor_", suffix=".wbt",
                                        dir=ROOT / "worlds")
        world = Path(filename)
        project = world.with_name("." + world.stem + ".wbproj")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as output:
                output.write(scene)
            print("SANDBOX Blockly Grand Prix variable : " + course.identifier, flush=True)
            print("AUCUN VOL : évaluateur volontairement désactivé ; Save/Open GUI NON QUALIFIÉ.",
                  flush=True)
            return launch_graphical(home, world, env).returncode
        finally:
            world.unlink(missing_ok=True)
            project.unlink(missing_ok=True)
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print("ÉCHEC sandbox Blockly variable : " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
