# Native Webots rendering experiment

This experiment targets R2025a source
[`c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b`](https://github.com/cyberbotics/webots/tree/c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b).
The trace patch extends the upstream `--log-performance` mechanism. With
`WEBOTS_RENDER_TRACE=1`, it retains bounded monotonic wall-clock spans in memory
and writes them on clean process exit to `<performance-log>.render.csv`.
A saturated trace is rejected by the bench. Sections include the physics core,
the Qt controller-ready signal, the wait before replying to controllers,
the reply, WREN preparation and drawing, and OpenGL buffer swapping.
Qt signal spans contain nested drawing spans. They must not be summed.
Swap completions measure the return from OpenGL, not monitor presentation.

The scale patch separates the main 3D framebuffer's draw dimensions from the
destination rectangle of the onscreen blit. Setting
`WEBOTS_EXPERIMENT_MAIN_RENDER_SCALE=50` halves each source dimension and keeps
the same Qt window and aspect to within integer rounding. The option affects
only the main view. No collision geometry, world time, controller cadence,
sensor rendering target, evaluator or authorization is changed. The default
draws at the ordinary resolution. The experimental screenshot path upscales
from the real source dimensions and video initialization requests native
resolution. Native movie capture, screenshot appearance, HiDPI, picking and
Windows/VR are outside the verified scope of this bench.

## Build from pinned sources

Prepare the matching Webots R2025a compiler/Qt dependencies, initialize the
upstream submodules and apply `tools/grand_prix/native_frame/webots-r2025a.patch`
from [#922](https://github.com/djibian/webeeblocks/pull/922) at
`64a67570bca00ed5f6a58394f78c832f3d23681a`. For the recorded runs, also apply
`tools/grand_prix/native_revision/webots-r2025a-revision.patch` from
[#923](https://github.com/djibian/webeeblocks/pull/923) at
`249678c7fe9c0ca11f2a3f06fc430382bb2c2ac4`.
The rendering patches themselves do not require a mutation counter.
Apply the trace patch first, and the scale patch for the resolution trial.

```sh
git -C "$WEBOTS_HOME" apply --check "$PWD/tools/grand_prix/native_render/webots-r2025a-render-trace.patch"
git -C "$WEBOTS_HOME" apply "$PWD/tools/grand_prix/native_render/webots-r2025a-render-trace.patch"
git -C "$WEBOTS_HOME" apply --check "$PWD/tools/grand_prix/native_render/webots-r2025a-main-render-scale.patch"
git -C "$WEBOTS_HOME" apply "$PWD/tools/grand_prix/native_render/webots-r2025a-main-render-scale.patch"
make -j8 -C "$WEBOTS_HOME/src/wren" release
make -j8 -C "$WEBOTS_HOME/src/webots" release
make -j8 -C "$WEBOTS_HOME/src/controller/c" release
```

On Linux use the pinned R2025a prerequisites. On Windows use the upstream
R2025a MinGW64/MSYS2 build environment with its matching Qt runtime. Under
MINGW64 set `WEBOTS_HOME` using `pwd -W` from the Webots source root, then run
the same targets. Stage `msys64/mingw64/bin/webots-bin.exe` and
`lib/controller/Controller.dll` together, with the Qt/MinGW DLLs that match
the build. Keep a separate copy of the official distribution. The Windows
engine build, package and real device measurements remain to be verified.

## Paired runs

Use the existing compact-frame fixture and capture scripts from #922.
Run in an isolated lab with a working graphical display. This fixture uses
Webots' TCP external Supervisor transport on loopback. The upstream TCP server
can listen beyond loopback.

```sh
python3 tools/grand_prix/native_render/run.py \
  --patched /path/to/staged-patched-r2025a \
  --frame-tools /path/to/922/tools/grand_prix/native_frame \
  --output /path/to/new-output --source-sha "$(git rev-parse HEAD)" \
  --host-id lab-machine --display-mode visible-renderer --scale-ab --steps 1500
```

The scale run alternates three pairs in the same binary at a 60-FPS cap,
checks the actual source and destination dimensions, verifies every sampled
trajectory and contact against its reference and writes the complete engine
and Supervisor traces. With `--scale-ab` omitted, it compares the 60/25 caps
using the repository's `StepWallProbe` and `compare_render_ab.py`.
The stage attribution measures the overlap of WREN drawing with the slowest
physical cycles. It refuses absent stages or an incompatible monotonic
clock interval. Both trials use the same visibly lit ODE fixture.
The benchmark does not open the Grand Prix or Blockly.

## Linux result

On Debian 13, AMD EPYC 9V74, Xvfb 1280×800 and software OpenGL, the
scale run requested 60 FPS in both arms. It measured 1,374 consecutive cycles
per arm and repetition after the warm-up. The viewport stayed at 736×479
and its obstacle was visible. The 50% arm drew at 368×239.

| Range across three runs | 100% source | 50% source |
| --- | ---: | ---: |
| Physical cycle p99 | 65.42–66.63 ms | 19.69–24.39 ms |
| WREN draw p99 | 64.58–68.95 ms | 18.32–26.24 ms |
| OpenGL swap completions per wall second | 14.17–14.51 | 27.26–28.20 |
| Simulated time / wall time | 0.996–1.031× | 0.957–0.965× |

In the 100% arm, drawing overlaps at least half of every cycle in the worst
1%. The physics stage itself remains below 0.12 ms at p99 in both arms.
The source-scale change reduces the physical-step stalls and increases swap
throughput at the cost of image resolution and a lower average simulation
speed on this fixture. The trace does not distinguish shader execution from
driver work inside the WREN span. See [results-linux.json](results-linux.json)
for each paired run and the separate frame-cap control.

## Windows qualification boundary

Reuse the [Windows host and A/B protocol](../../../docs/GRAND_PRIX_WINDOWS_BENCH.md).
Once a Windows artifact has been built and qualified for a checkpoint,
compare 100% and 50% source dimensions in separate, alternating runs of
the **same exact binary**. Keep visible Webots and Blockly windows, viewport,
OpenGL renderer, course, program, power policy and cap fixed. Retain
`--log-performance=<fresh-file>,0` with `WEBOTS_RENDER_TRACE=1`, the evaluator
step-wall trace, host capture and actual presentation measurements. Check
readability and the GUI workflow as well as ≥0.95× and p99 ≤25 ms on the
full attempt phases. A diagnostic ODE run does not establish that result.
