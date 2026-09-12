# Firefox Qt provider continuity qualification for #87

Research only. Do not merge this harness. It repairs the observation boundary of
closed PR #301; it is not a restart of the C8–C26 causal-discriminator series and
it does not implement Open, Save As or Save.

The preserved #301 result already proves that the real PIC-built Qt provider can
start under official Webots R2025a, expose a real `QFileDialog`, receive an XTEST
Escape cancellation and return from the provider without the historical Qt COPY
relocation crash. What remained UNPROVEN was controller continuation because the
old oracle depended on aggregate stdout after eight steps and on markers emitted
after Webots shutdown had already been requested.

This re-evaluation keeps the same frozen provider, official runtime, PIC/no-COPY
static checks, Xvfb/QPA boundary, exact process ancestry and real X11 cancellation.
The only measurement change is a controller-owned journal in the evidence
directory. The controller synchronously records and `fdatasync()`s its return from
`wb_robot_init()`, provider call/return, each of eight `wb_robot_step(32)` results
and simulation times, the capabilities response, provider destruction and a
`PRE_SHUTDOWN_READY` marker. It then continues stepping and **cannot call**
`wb_supervisor_simulation_quit(0)` until the external harness has read and
validated that journal while Webots is still alive and has created a durable
acknowledgement file.

Pre-registered interpretation:

- **PASS**: all #301 static/runtime/dialog identity conditions hold, the real dialog
  is exposed and cancelled, the controller-owned journal is read while Webots is
  alive and proves eight ordered successful 32 ms steps (0.256 s total), the
  expected `operationsReady:false` capabilities response and provider destruction,
  the project-file inventory is unchanged, and the subsequent Webots shutdown is
  normal.
- **FAIL**: after the qualified real provider is reached, a fatal error occurs, or
  complete observations refute unchanged project files, successful pre-shutdown
  continuation, or normal Webots shutdown.
- **UNPROVEN**: any indispensable static identity, X11 witness, live process
  identity, controller-journal record or pre-shutdown observation is missing or
  ambiguous.

A PASS establishes only the remaining provider/controller continuity prerequisite.
It does not establish browser WWI round-trip semantics, project-file operations,
full Firefox parity or Windows support. After the result is preserved on #87,
close the research PR without merge; do not start another causal reduction chain.
