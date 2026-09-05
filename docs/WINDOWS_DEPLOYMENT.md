# Windows classroom deployment

## Supported target

The currently supported classroom path is **Windows 10 or 11 64-bit + Webots
R2025a + Google Chrome**.

Chrome is the reference browser because the product project-file path uses the
native File System Access API for Open / Save As / Save on the selected file and
that exact path has passed the real low-end classroom acceptance recorded on
issue #81.

Do not infer broader browser support from the Windows claim:

- Edge is not part of the currently validated classroom boundary;
- Firefox project-file parity is not currently supported and remains tracked
  separately by #87;
- no download-as-copy fallback is claimed as equivalent to native same-file
  Open / Save / Save As semantics.

A later browser can enter the supported boundary only through its own applicable
product evidence. The student machine does not need Git, Node.js, npm, Bash,
Python or a compiler; those tools exist only on the release builder.

## Build boundary

The complete gate runs `tools/build_windows_classroom_release.ps1` on a
`windows-2022` runner after:

1. verifying the official `webots-R2025a_setup.exe` SHA-256;
2. installing Webots R2025a and using its bundled MSYS2/MinGW toolchain to build
   `crazyflie_runtime_v2.exe`;
3. preparing Blockly 13.2.1 through the exact npm lock file;
4. copying the pinned local Robot Window bridge;
5. replacing the four remote world dependencies with a local Crazyflie PROTO,
   two meshes, one texture and built-in floor/background nodes;
6. emitting a ZIP plus `MANIFEST.sha256`.

The archive validator expands the ZIP under a path containing spaces, verifies
every checksum, rejects development-only files and runtime URLs, checks every
JavaScript file, confirms a Windows PE controller and exercises the launcher in
validation mode.

The Webots installer is cached to avoid repeated large downloads. The complete
Windows build runs for full gates, nightly validation and promotion to `main`;
the lightweight Windows Blockly/AST/project-file contract remains on every
Runtime change.

## Teacher and student path

The teacher installs Webots R2025a, extracts
`WebeeBlocks-Windows-R2025a.zip` into a writable folder and uses Google Chrome
as the classroom browser. The network may then be disconnected.

The student double-clicks `Launch-WebeeBlocks.cmd`. The launcher finds Webots
through `WEBOTS_HOME`, the standard Program Files location or `PATH`, starts
the packaged world in real-time mode, and Webots opens the Robot Window. The
student waits for `PRÊT`, then uses the WebeeBlocks controls; no manual Webots
play action is part of the validated path.

## Current human acceptance boundary

Issue #81 records two completed real-machine gates on the lowest-spec reference
Dell OptiPlex 3050 with Windows 11, Webots R2025a and Chrome:

- **W1 PASS** — offline one-action startup, `PRÊT`, normal and step execution,
  coherent execution controls, student-correctable invalid-program handling,
  and Open / Save As / Save / reopen;
- **W2 PASS** — 30 minutes offline with repeated run, step, Continue, reset,
  Open, Save As and Save cycles without progressive loss of responsiveness,
  simulation usability or Robot Window/runtime connectivity.

Those passes establish the current Chrome low-end baseline. They do not prove
Edge, Firefox, or every future materially changed release artifact.

`packaging/windows/WINDOWS-ACCEPTANCE.md` is therefore a **revalidation
template** for a future release whose changes make renewed real-machine
acceptance decision-relevant; it is not evidence that the already-proven Chrome
baseline is still unvalidated.
