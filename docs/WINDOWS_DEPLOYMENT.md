# Windows classroom deployment

## Supported target

The release target is Windows 10 or 11 64-bit with Webots R2025a and a supported
system browser. Edge or Chrome is recommended for native Open/Save/Save As.
Firefox keeps the explicit fallback download path; it must clearly produce a
new copy rather than pretending to update the selected file.

The student machine does not need Git, Node.js, npm, Bash, Python or a compiler.
Those tools exist only on the release builder.

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
`WebeeBlocks-Windows-R2025a.zip` into a writable folder and may disconnect the
network. The student then double-clicks `Launch-WebeeBlocks.cmd`. The launcher
finds Webots through `WEBOTS_HOME`, the standard Program Files location or
`PATH`, opens the packaged world paused and lets Webots open the Robot Window in
the configured browser.

## Human acceptance boundary

Hosted CI proves build, contents, paths, core semantics and launch resolution.
It does not prove a visible Windows/Webots/browser classroom session. Before a
Windows-support claim, copy and complete `WINDOWS-ACCEPTANCE.md` from the
archive on the least powerful target PC, including the 30-minute offline
stability and Chrome/Edge plus Firefox file paths required by #81.
