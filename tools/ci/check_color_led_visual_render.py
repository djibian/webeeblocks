#!/usr/bin/env python3
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "ci-artifacts/runtime-v2-webots/color-led-render"
LOG = ARTIFACTS / "webots-render.log"
VIEWS = ("top", "three-quarter", "side")
MIN_CHANGED_FRACTION = 0.002

if not LOG.is_file():
    raise AssertionError(f"missing render log: {LOG}")
log = LOG.read_text(encoding="utf-8", errors="replace")

pairs = []
for view in VIEWS:
    off = ARTIFACTS / f"{view}-off.jpg"
    blue = ARTIFACTS / f"{view}-blue.jpg"
    for image in (off, blue):
        if not image.is_file() or image.stat().st_size == 0:
            raise AssertionError(f"missing render evidence: {image}")
    if f"COLOR_LED_RENDER view={view} state=off value=0x000000" not in log:
        raise AssertionError(f"OFF LED device trace missing for {view}")
    if f"COLOR_LED_RENDER view={view} state=blue value=0x0000ff" not in log:
        raise AssertionError(f"BLUE LED device trace missing for {view}")

    identify = subprocess.run(
        ["identify", "-format", "%m %wx%h", str(off), str(blue)],
        check=True, text=True, capture_output=True
    ).stdout
    if identify.count("JPEG") != 2:
        raise AssertionError(f"unexpected rendered image format for {view}: {identify!r}")

    off_crop = Path("/tmp") / f"webeeblocks-{view}-off.png"
    blue_crop = Path("/tmp") / f"webeeblocks-{view}-blue.png"
    for source, target in ((off, off_crop), (blue, blue_crop)):
        subprocess.run(
            ["convert", str(source), "-gravity", "center", "-crop", "70%x70%+0+0", "+repage", str(target)],
            check=True
        )
    fraction_text = subprocess.run(
        [
            "convert", str(off_crop), str(blue_crop),
            "-compose", "difference", "-composite",
            "-colorspace", "Gray", "-threshold", "10%",
            "-format", "%[fx:mean]", "info:",
        ],
        check=True, text=True, capture_output=True
    ).stdout.strip()
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", fraction_text):
        raise AssertionError(f"unexpected ImageMagick fraction for {view}: {fraction_text!r}")
    fraction = float(fraction_text)
    if fraction < MIN_CHANGED_FRACTION:
        raise AssertionError(
            f"{view}: active Color LED changed only {fraction:.6f} of central rendered pixels; "
            f"need >= {MIN_CHANGED_FRACTION:.6f}"
        )
    print(f"PASS {view}: active Color LED visibly changes {fraction:.6f} of central rendered pixels")
    pairs.extend((str(off), str(blue)))

contact_sheet = ARTIFACTS / "fixed-view-evidence.jpg"
subprocess.run(
    ["montage", *pairs, "-tile", "2x3", "-geometry", "480x360+8+8", str(contact_sheet)],
    check=True
)
if not contact_sheet.is_file() or contact_sheet.stat().st_size == 0:
    raise AssertionError("fixed-view Color LED evidence contact sheet was not created")
print(f"PASS fixed Color LED evidence: {contact_sheet}")
