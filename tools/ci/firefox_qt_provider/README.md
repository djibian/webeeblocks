# One Qt provider qualification for #87

Research only. Do not merge this harness. The architecture decision in
[#87](https://github.com/djibian/webeeblocks/issues/87#issuecomment-5607115679)
requests one qualification of the useful provider, not more C8–C26 reductions.

The existing `crazyflie-runtime-wwi` preparation calls this harness only on
`research/firefox-qt-provider-qualification`. It adds no workflow or dependency
on another candidate, changes no CI selection/oracle/timeout, and preserves the
ordinary job's product checks. Its evidence is included by the existing always-on
`crazyflie-runtime-wwi-r2025a` artifact upload. A green synthetic oracle test is not
a live qualification.

The harness reproduces the pinned R2025a desktop archive and official runtime
recipe used in the preserved controls. It downloads the exact C10 provider and
`runtime.ini`, verifies all four Git blobs, and adds only a research dialog hook
to a temporary copy. Both C++ units are compiled `-fPIC`, then linked as PIE.
The executable must contain the real factory, `QCoreApplication::instance()`,
qobject/metaobject paths and called dialog hook; `readelf` must show no Qt COPY
relocation and no added RPATH/RUNPATH. Linked and live libraries must resolve to
the Webots bundle. There is no standalone arm, dummy provider, debugger, system Qt,
QPA/DISPLAY switch or project-file operation.

One minimal supervisor/controller is launched by official Webots under the
preserved Xvfb/software-rendering environment. It calls `wb_robot_init()`, invokes
the real provider and enters `QFileDialog::exec()`. A Qt timer captures the exposed
window as PNG. An independent Xlib/XTEST observer verifies the exact controller
executable and its ancestry under the launched Webots process, the window's title,
`_NET_WM_PID`, `IsViewable` geometry and focus before sending one Escape press and
release. It never calls `reject()` or fabricates an accepted dialog result.

After `Rejected`, the controller must return from the provider, execute eight
real Webots steps (0.256 s of simulation time), receive the preserved broker's
capabilities response with `operationsReady:false`, destroy the provider and
complete. This proves a return to the controller loop; it does **not** claim a
browser WWI round-trip or Open/Save/Save As implementation. The isolated directory
sentinel and file inventory must remain unchanged.

Pre-registered interpretation:

- PASS: all static/provenance preconditions, Qt screenshot, independently bound
  X11 exposure/cancellation and ordered controller return evidence hold, Webots
  exits normally and the test-file inventory is unchanged.
- FAIL: with the qualified executable and real provider reached, a fatal failure
  occurs; or a complete observed sequence demonstrates changed project files,
  unsuccessful completion or no actual simulation advancement.
- UNPROVEN: preparation, launch, runtime identity or indispensable observations
  are missing/ambiguous. A missing frame or malformed observer is never a pass.

The 15 s dialog deadline and 45 s launch bound are diagnostic limits, not product
latency claims. Preserve whatever result this single qualification produces and
stop; do not start another causal-discriminator chain or silently retune it.
Full Firefox same-file semantics and Windows compatibility remain unproven even
if this provider qualification succeeds.

Local checks:

```sh
python3 tools/ci/firefox_qt_provider/test_qualification.py
bash -n tools/ci/run_firefox_qt_provider_qualification.sh
```

API references: [Qt 6.5 QFileDialog](https://doc.qt.io/qt-6.5/qfiledialog.html),
[QWindow exposure](https://doc.qt.io/qt-6.5/qwindow.html#isExposed),
[XTEST](https://xorg.freedesktop.org/archive/X11R7.7/doc/libXtst/xtestlib.html).
