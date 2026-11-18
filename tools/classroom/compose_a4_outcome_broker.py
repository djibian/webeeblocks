"""Deterministic A1/A2/A3/A4/A7 school-only broker composition; NEVER mutate physical broker."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.grand_prix.route_broker_outcome_v2 import compose_route_outcome_broker

SHARED = ROOT / "controllers/crazyflie_runtime_v2/file_broker_runtime.cpp"
OUTPUT = ROOT / "controllers/crazyflie_classroom_v2/build/file_broker_classroom.cpp"

def compose_classroom_outcome_broker(source: str) -> str:
    if type(source) is not str:
        raise TypeError("broker input must be source text")
    generated = compose_route_outcome_broker(source)
    start = '  if (!reason.empty()) {\n    if (oracle != "grand-prix-route-v2"'
    end = '  // Reject trailing bytes, malformed suffixes and noncanonical attempt tokens.'
    if generated.count(start) != 1 or generated.count(end) != 1:
        raise RuntimeError("school reason broker anchor changed")
    before, remaining = generated.split(start, 1)
    discarded, after = remaining.split(end, 1)
    for required in ("reason != \"envelope-contact\"",
                     "reason != \"course-boundary\"", "reason != \"altitude\"",
                     "reason != \"low-outside-zone\"", "reason != \"wrong-landing\"",
                     "reason != \"time-limit\"", "return false;", "\n  }\n"):
        if required not in discarded:
            raise RuntimeError("unrecognized route reason allowlist")
    replacement = """  if (!reason.empty()) {
    const bool route =
      oracle == "grand-prix-route-v2" &&
      (reason == "envelope-contact" || reason == "course-boundary" ||
       reason == "altitude" || reason == "low-outside-zone" ||
       reason == "wrong-landing" || reason == "time-limit");
    const bool classroom =
      oracle == "progression-decision-h-v1" &&
      (reason == "obstacle-contact" || reason == "unsafe-clearance" ||
       reason == "route-incomplete" || reason == "early-finish" ||
       reason == "landing-timeout" || reason == "wrong-pad" ||
       reason == "invalid-start");
    const bool altitude =
      oracle == "progression-altitude-3d-v1" &&
      (reason == "obstacle-contact" || reason == "unsafe-clearance" ||
       reason == "early-finish" || reason == "landing-timeout" ||
       reason == "wrong-pad");
    const bool orientation =
      oracle == "progression-orientation-3d-v1" &&
      (reason == "route-incomplete" || reason == "landing-timeout");
    const bool sequence =
      oracle == "progression-sequence-3d-v1" &&
      (reason == "flight-not-observed" || reason == "wrong-pad" ||
       reason == "landing-timeout");
    const bool mini =
      oracle == "progression-mini-grand-prix-v1" &&
      (reason == "obstacle-contact" || reason == "invalid-start" ||
       reason == "unsafe-h-crossing" || reason == "route-incomplete" ||
       reason == "wrong-heading" || reason == "course-boundary" ||
       reason == "early-finish" || reason == "landing-timeout" ||
       reason == "wrong-pad");
    if (status != "not-achieved" ||
        (!route && !classroom && !altitude && !orientation && !sequence && !mini))
      return false;
  }
"""
    return before + replacement + end + after

def main() -> None:
    text = compose_classroom_outcome_broker(SHARED.read_text(encoding="utf-8"))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(text, encoding="utf-8")

if __name__ == "__main__":
    main()
