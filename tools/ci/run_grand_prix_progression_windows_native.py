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
from tools.ci.run_grand_prix_route_windows_native import run_one, probe_windows_entropy


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--webots-home", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--include-a8", action="store_true")
    args = parser.parse_args()
    if sys.platform != "win32":
        raise RuntimeError("Native Windows R2025a only")
    package, home, output = (p.resolve() for p in (
        args.package, args.webots_home, args.output))
    if (home / "resources/version.txt").read_text().strip() != "R2025a":
        raise ValueError("Official Webots R2025a required")
    package_evidence = verify(package, args.include_a8)
    indices = (0, 15, 22, 34) if args.include_a8 else (0, 15, 22)
    count = 35 if args.include_a8 else 23
    smoke = f"{len(indices)}/{count}"
    output.mkdir(parents=True, exist_ok=False)
    probe_windows_entropy(home, output)
    runs = []
    try:
        # A1/V1, A6/V5, A7/V7 and optionally A8/V12. Smoke only.
        for index in indices:
            runs.append(run_one(package, home, output, index))
            (output / "campaign.json").write_text(json.dumps({
                "package": package_evidence, "results": runs,
                "native_smoke": smoke if len(runs) == len(indices) else f"{len(runs)}/{count}",
                "teacher_windows": "UNPROVEN"
            }, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        print(f"GP_PROGRESSION_WINDOWS_NATIVE_SMOKE_PASS {smoke}; GUI=UNPROVEN")
    finally:
        (output / "status.json").write_text(json.dumps({
            "tested": len(runs), "required": len(indices), "gui": "UNPROVEN",
            "teacher_windows": "UNPROVEN"
        }, sort_keys=True, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
