#!/usr/bin/env python3
"""Local, interactive Linux launcher for the *historical* Grand Prix U.

This does not implement or qualify the variable L-corner courses of #808.
The GUI, OS file dialogs and real user journey still require local observation.
"""
import argparse
import os
from pathlib import Path
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


def ensure_blockly_assets():
    required = [
        BLOCKLY / "vendor/VERSION",
        BLOCKLY / "vendor/blockly_compressed.js",
        BLOCKLY / "vendor/blocks_compressed.js",
        BLOCKLY / "vendor/msg/fr.js",
        BLOCKLY / "webots/RobotWindow.js",
        BLOCKLY / "webots/request_methods.js",
    ]
    version = required[0].read_text(encoding="utf-8").strip() if required[0].is_file() else None
    if version != "13.2.1" or any(not p.is_file() or not p.stat().st_size for p in required[1:]):
        print("Préparation Blockly (Node.js >= 22, npm et accès au registre npm requis au premier lancement)...", flush=True)
        subprocess.run(["bash", str(ROOT / "tools/prepare_runtime_v2.sh")], cwd=ROOT, check=True)
    if required[0].read_text(encoding="utf-8").strip() != "13.2.1":
        raise RuntimeError("Version Blockly préparée incohérente")
    if any(not p.is_file() or not p.stat().st_size for p in required[1:]):
        raise RuntimeError("Ressources Blockly ou RobotWindow absentes après préparation")


def prepare_native(home):
    if not EVALUATOR.is_file():
        raise RuntimeError(f"Évaluateur Grand Prix absent : {EVALUATOR}")
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


def launch_graphical(home, world, env):
    """Start in a deterministic paused state before pupil program creation."""
    return subprocess.run(
        [str(home / "webots"), "--mode=pause", "--stdout", "--stderr", str(world)],
        cwd=ROOT, env=env, check=False,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Simulation GUI Linux du Grand Prix U historique ; pas le nouveau parcours variable."
    )
    parser.add_argument("--legacy-u", action="store_true",
                        help="confirmer l'utilisation du parcours U historique (sans cornières en L)")
    parser.add_argument("--seed", type=int, default=4, help="graine U 0..65535 (défaut : 4)")
    parser.add_argument("--webots-home", help="répertoire d'installation Webots R2025a")
    parser.add_argument("--preflight-only", action="store_true",
                        help="préparer les ressources natives, sans prétendre valider le GUI")
    args = parser.parse_args(argv)
    if not args.legacy_u:
        parser.error("le nouveau parcours variable n'est pas encore implémenté ; choisir explicitement --legacy-u")
    if not 0 <= args.seed <= 65535:
        parser.error("--seed doit être compris entre 0 et 65535")
    try:
        if not args.preflight_only and not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
            raise RuntimeError("Session graphique absente : ouvrir une session Linux avec affichage")
        home = webots_home(args.webots_home)
        env = prepare_native(home)
        if args.preflight_only:
            print("Préflight technique terminé ; aucun test GUI ni vol simulé n'a été exécuté.")
            return 0
        fd, name = tempfile.mkstemp(prefix="gp_u_linux_", suffix=".wbt", dir=ROOT / "worlds")
        world = Path(name)
        project = world.with_name("." + world.stem + ".wbproj")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(render_legacy_u(args.seed))
            print(f"Simulation Grand Prix U historique : graine={args.seed}, monde={world}", flush=True)
            print("La réussite de cette ouverture n'atteste pas encore le cycle GUI/Save/Open.", flush=True)
            result = launch_graphical(home, world, env)
            return result.returncode
        finally:
            world.unlink(missing_ok=True)
            project.unlink(missing_ok=True)
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"ÉCHEC préparation/lancement Grand Prix Linux : {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
