# M2 private Windows R2025a B — deterministic D/W acceptance

**Status: PROCEDURE ONLY; NOT TEST_REQUIRED, NOT PASS.** This protocol does not authorize a direct notification, informal human verdict, or transfer of earlier W1/W2 results. V5 must bind an exact release and candidate HEAD before requesting a human test.

## Immutable release

- Producing run: https://github.com/djibian/webeeblocks/actions/runs/41442076181 ; source 4896eda180e8cc0678adc345edde10d69ff35514.
- GitHub Actions artifact 13140547162, name m2-windows-private-product-candidate, inner file M2-private-product.zip.
- Inner ZIP SHA-256: 9f3093082c5155ab3b77dfd902199350b7cecf9a67ceced139fcba03fb77194c.
- Retained OCI by immutable digest: ghcr.io/djibian/webeeblocks-m2-private-windows-r2025a@sha256:b9785b1ef93ef5801e8bc76c773e71c8766b8d674df402125122efd2b315e1af.
- Producer and independent constrained-Windows checks: https://github.com/djibian/webeeblocks/actions/runs/41448179986 ; 11,369 private files checked, OCI ZIP roundtrip identical.
- Qt Windows C++ parent lifetime: https://github.com/djibian/webeeblocks/actions/runs/41447418701.
- This is the exact M1 + M2 product release. Its provenance is not recalculated from whichever source HEAD happens to trigger a later independent review.

## Deterministic preparation

1. Record interactive Windows 11 host OS build, CPU/RAM, GPU, driver, display, Windows session, browser and browser version, whether old system Webots is installed, and network state.
2. Download the exact inner ZIP and compare PowerShell Get-FileHash -Algorithm SHA256 with the value above. Abort on mismatch. Keep the original untouched.
3. Extract to a user-writable local directory. The release must contain Webots, controllers, worlds, Launch-WebeeBlocks.ps1, Launch-WebeeBlocks.cmd, PRIVATE_RUNTIME.sha256 and MANIFEST.sha256 together. Neither Webots R2025a nor MSYS2 is installed as a separate prerequisite.
4. Run the shipped Launch-WebeeBlocks.ps1 -ValidateOnly. Require WEBEEBLOCKS_WINDOWS_LAUNCHER_OK, R2025a, and the webotsw.exe path strictly under this extracted release's Webots/msys64/mingw64/bin. Any fallback to Program Files, a globally installed SDK, PATH, or ambient DLL is FAIL.
5. In a disposable extracted COPY only, move a critical private Qt DLL temporarily aside: ValidateOnly must fail. Restore its original bytes and repeat successful ValidateOnly; confirm the DLL SHA matches PRIVATE_RUNTIME.sha256.

## Real interactive D/W, same ZIP

6. Disconnect the internet; local loopback may remain available. Launch via shipped Launch-WebeeBlocks.cmd. Observe a genuine interactive Webots 3D scene; drag/zoom/rotate camera and confirm rendering changes, without replacing Webots with a browser screenshot or headless simulation.
7. Verify real Blockly Robot Window PRÊT/READY and WWI handshake, then run a normal student-edited Blockly program. Observe physical 3D drone motion and reported outcome.
8. Exercise STOP, RESET while running, RESET after completion, step-by-step and Continuer. Confirm neutral world restoration and absence of abnormal process/fatal logs.
9. Start from an activity template and Save As a new .wbb in a school-style writable personal directory. Modify, Save to the same target, close/reopen via Open and compare the workspace and behavior. Open an existing .wbb, edit and Save again. No synthetic file dialog or automatic save may substitute for these actions.
10. Check coexistence of Webots, Chrome/Firefox supported browser session, native foreground dialogs and user file operations. Repeat at least one full run/reset/open/save cycle offline.
11. Close by ordinary UI controls. Record native exit status, parent/child process tree, surviving processes and any Qt fatal. The student browser must not kill unrelated Webots or foreign processes.
12. Repeat a bounded cycle on the low-end classroom reference PC with precisely the same ZIP SHA-256.

## Evidence and authority

Attach screenshots of 3D and Blockly simultaneously with timestamps, SHA-256 of the used ZIP and sample .wbb, exact OS/browser/GPU, loaded module paths, console and native exit status, full test actions, and PASS/FAIL/UNPROVEN per observation.

The existing GitHub V5 human-checkpoint profile windows-low-end produces a different non-M2 artifact and MUST NOT be reused for this release. A new exact-artifact-aware preparation must be implemented and verified before invoking TEST_REQUIRED through the authorized GitHub mechanism. Do not send ntfy directly or post a premature human request. The interactive result is UNPROVEN until that checkpoint completes.
