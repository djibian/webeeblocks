"""Real Windows R2025a smoke for extracted A1–A7, not a GUI or teacher PASS.

Reuse the existing independent WWI/native backend probe without changing its
flight, RESET, negative-oracle expectations or Webots clock. A red outcome is
evidence to diagnose, never a reason to skip a physical/safety assertion.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.ci.test_grand_prix_progression_windows_package import verify
from tools.ci.run_grand_prix_route_windows_native import run_one


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--webots-home", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if sys.platform != "win32":
        raise RuntimeError("Native Windows R2025a only")
    package, home, output = (p.resolve() for p in (
        args.package, args.webots_home, args.output))
    if (home / "resources/version.txt").read_text().strip() != "R2025a":
        raise ValueError("Official Webots R2025a required")
    package_evidence = verify(package)
    output.mkdir(parents=True, exist_ok=False)
    runs = []
    try:
        # A1 one-variant, A6 H-free last variant and A7 seven-variant end.
        # These are smoke samples, never a 23/23 physical qualification.
        for index in (0, 15, 22):
            runs.append(run_one(package, home, output, index))
            (output / "campaign.json").write_text(json.dumps({
                "package": package_evidence, "results": runs,
                "native_smoke": "3/23", "teacher_windows": "UNPROVEN"
            }, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        print("GP_PROGRESSION_WINDOWS_NATIVE_SMOKE_PASS 3/23; GUI=UNPROVEN")
    finally:
        (output / "status.json").write_text(json.dumps({
            "tested": len(runs), "required": 3, "gui": "UNPROVEN",
            "teacher_windows": "UNPROVEN"
        }, sort_keys=True, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
