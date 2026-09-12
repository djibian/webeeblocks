# Firefox provider/controller continuity — retained #317 evidence

Exact research candidate: `e8aecd14e7988a6772d780062f8cf83060657dff`.
Base: `07e7bd20870f11a05676bd00f240af07a0c3402b`.
Canonical run `34672121094`, attempt 1, job `103495351811`.
The original artifact `10291545764` is retained unchanged alongside all 30
extracted files. `SOURCE.json` records every size and SHA-256. The downloaded
ZIP digest agrees with GitHub's artifact metadata:
`2623c757872cc2789d30d86275087f8f4c99508c7bf432015c2829ebc6f7a8a0`.

The owner result is [PASS for provider/controller continuity only](https://github.com/djibian/webeeblocks/issues/87#issuecomment-5643382930),
under the [pre-registered oracle](https://github.com/djibian/webeeblocks/issues/87#issuecomment-5643350301).
The research PR is closed without merge. This evidence branch preserves the
exact source and observations; it does not integrate the research harness.

## Independently readable observations

The `raw/crazyflie-runtime-wwi/firefox-qt-provider-continuity/` directory contains
`result.json`, `static-proof.json`, `controller-continuity.log`,
`pre-shutdown-observation.json`, `x11-witness.json`, `webots.log`, `dialog.png`,
and the complete compiler/linker/runtime observations.

The controller journal retains eight successful 32 ms steps, reaching 0.256 s,
then a local broker capabilities response (`operationsReady:false`), provider
destruction and `PRE_SHUTDOWN_READY`. The harness observed these records while
Webots remained alive and only then acknowledged shutdown. The observation's
journal digest `fe106309425f4b84e58215cf667e614ff16a662a5d83927267c4e1e52c0098e4`
matches the exact first 17 journal records. The final file additionally contains
`SHUTDOWN_ACK_OBSERVED`; its different full-file digest is expected.

The binary characterized by the static/runtime evidence has SHA-256
`e1ce1f822659e1a5b084354ba56ed193c0a3923805215b3f0cb5db8aa8780dc8`.
The raw aggregate Webots log still omits the post-dialog loop markers; the
separate pre-shutdown journal supplies the missing observation from #301.

## Limits

This preserves an existing result; it executes no new Qt/Webots experiment.
No Open, Save As or Save operation was exercised. The capabilities call is
local to the frozen broker, not a browser/WWI file-operation round trip.
Same-file semantics, full Firefox parity and Windows remain UNPROVEN.
The old #301 UNPROVEN result remains historical; this separate exact candidate
supplies the repaired continuity evidence. No physical checkpoint is involved.
