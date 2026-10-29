"""Re-run exact failed composed ELF in the regular pinned PROTO environment.

NON-GATE: no rebuild, product modification, requalification of historical crash or self-GO.
"""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import tools.ci.run_grand_prix_u_prototype as gp
from tools.ci.run_grand_prix_u_geometry import IMAGE, SOURCE

ELF_SHA = "2742d90041fccb4b24fba4558662ecf17d15c092bf28dd93bf014f748cf01c9f"
FAILED_RUN = 40907399724
FAILED_ARTIFACT = 12912812964
OUT = ROOT / "ci-artifacts/qt665-composed"
PROVENANCE = ROOT / "ci-artifacts/qt665-prebuilt-replay"

def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def main():
    assert IMAGE == "cyberbotics/webots@sha256:f0023e30daf38b172e4e6ad24ed345909bcd9551df34d63d824e121a7cebf099"
    assert SOURCE == "c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b"
    assert gp.IMAGE == IMAGE
    binary = OUT / "webots-bin"
    assert binary.is_file() and digest(binary) == ELF_SHA, "wrong ELF from failed run"
    assert not (OUT / "native").exists(), "previous failed trials contaminate the inventory"
    PROVENANCE.mkdir(parents=True, exist_ok=True)
    original = gp.native_container_command
    marker = ("timeout -k 5s 1400s python3 -u tools/ci/run_grand_prix_u_prototype.py "
              "--native --suite unavailable --seed 0 --side 2.0")
    substitute = (
        "cp ci-artifacts/qt665-composed/webots-bin /usr/local/webots/bin/webots-bin\n"
        "echo '2742d90041fccb4b24fba4558662ecf17d15c092bf28dd93bf014f748cf01c9f  /usr/local/webots/bin/webots-bin' | sha256sum -c -\n"
        "timeout -k 5s 1400s python3 -u experiments/qt665-composed/run_composed.py"
    )
    def launch_with_exact_elf(*args, **kwargs):
        assert len(args) >= 4
        assets = Path(args[1])
        assert (assets / ".git").exists(), "missing assets checkout"
        assert subprocess.check_output(["git","-C",str(assets),"rev-parse","HEAD"],text=True).strip() == SOURCE
        for relative in (
            "projects/robots/bitcraze/crazyflie/protos/Crazyflie.proto",
            "projects/objects/backgrounds/protos/TexturedBackground.proto",
            "projects/objects/backgrounds/protos/TexturedBackgroundLight.proto",
            "projects/objects/floors/protos/Floor.proto",
        ):
            assert (assets / relative).is_file(), "required PROTO absent: "+relative
        cmd = original(*args, **kwargs)
        assert cmd[-1].count(marker) == 1, "original negative selector changed"
        assert cmd.count(IMAGE) == 1, "image selector mismatch"
        assert any(str(assets / "projects") in arg and ":ro" in arg for arg in cmd), "read-only PROTO bind absent"
        cmd[-1] = cmd[-1].replace(marker, substitute)
        return cmd
    gp.native_container_command = launch_with_exact_elf
    gp.OUT = PROVENANCE / "outer"
    sys.argv = [str(gp.__file__), "--suite","unavailable","--seed","0","--side","2.0"]
    gp.main()
    result = json.loads((OUT / "RESULT.json").read_text())
    assert result["status"] == "PASS_BOUND_COMPOSED_NATIVE", result
    assert result["composed_loaded_elf_sha256"] == ELF_SHA
    assert result["signal_entries"] >= 1 and result["allocator_events_in_signal"] == 0
    assert result["native_result"]["status"] == "not-achieved"
    assert result["native_result"]["reason"] == "runtime"
    assert result["native_result"]["mode"] == "unavailable"
    verdict = {
        "status":"PASS_BOUND_COMPOSED_PREBUILT_PROTOS",
        "original_failed_run": FAILED_RUN,
        "original_failed_artifact": FAILED_ARTIFACT,
        "replayed_unchanged_elf_sha256": ELF_SHA,
        "only_environment_fix": "Canonical pinned R2025a projects/ bind mounted read-only",
        "native_result": result,
        "limits": [
            "One unavailable negative only; no full native regression",
            "Historical Qt console SIGSEGV cause and repair remain UNPROVEN",
            "No release/Windows/Ready/CI Gate/GO",
        ],
    }
    (PROVENANCE / "RESULT.json").write_text(json.dumps(verdict,indent=2)+"\n")
    print("QT665_COMPOSED_PREBUILT_PROTO_WITNESS=PASS",flush=True)

if __name__=="__main__":
    main()
