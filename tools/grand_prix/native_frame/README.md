# Webots R2025a physical observation experiment

The source patch adds an opt-in, read-only Supervisor request. The Controller
queues it with the existing `step(8)` request. The engine samples at the normal
step reply, after ODE and `postPhysicsStep`, only for a synchronous Supervisor
whose requested interval and completed simulation time are exactly 8 ms apart.
An immediate Supervisor RPC cannot publish or consume a queued observation.
The stock Grand Prix evaluator keeps its existing authority.

## Wire format

Message 104 is private to this experimental engine and Controller pair.
Each request adds five bytes to the ordinary step request. A successful reply
adds 187 bytes plus 28 per descendant contact, including the device tag and
message byte. It uses the R2025a controller protocol's little-endian fields on
x86-64 Linux and Windows. There is no mapped-file layout or machine-code hook.

The reply contains the format version, count, 16-byte observation incarnation,
Supervisor and requested Solid IDs, simulated milliseconds, position, row-major
orientation with scale removed, linear and angular velocities, and ODE contact
coordinates with the native Solid ID. The step index is simulated milliseconds
divided by 8. A failed native observation returns count −1, including when
the 128-contact bound is exceeded. An empty contact list has count zero.
The library checks the bounds, version, endpoint IDs and freshness. The test
consumer checks finite coordinates and compares every sample with the official
API. A returned sample can be consumed once. The observer incarnation rotates
on observer reset/restart or a non-increasing clock. It conveys no guarantee
about unobserved changes to the scene or fresh Grand Prix admission.

## Build

Start from the exact upstream Webots tag checkout. Use the R2025a build
prerequisites for the platform. On Linux these are the upstream Ubuntu LTS
compilation dependencies and the Qt setup from
`scripts/install/qt_linux_installer.sh`. On Windows use the upstream
`MINGW64` environment and `scripts/install/msys64_installer.sh`.
The patch targets Webots R2025a source
[`c6793d8f`](https://github.com/cyberbotics/webots/tree/c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b).

```sh
git clone --depth 1 --branch R2025a https://github.com/cyberbotics/webots.git
bash tools/grand_prix/native_frame/build.sh /path/to/webots 8
```

The script checks the exact clean source revision, initializes the pinned
submodules, applies the patch and compiles the engine and Controller library.
Stage them together in a separate copy of the matching R2025a distribution
with its normal assets and dependencies. Keep the official distribution for
the control. The Linux paths are `bin/webots-bin` and
`lib/controller/libController.so`. The Windows output paths are
`msys64/mingw64/bin/webots-bin.exe` and `lib/controller/Controller.dll`.
For a staged Windows build the MinGW/Qt runtime DLLs must match the build.
The Windows source path and export list are prepared. Compilation and
execution on Windows are still to be verified.

## Run the comparison

Use Python 3.11+ and a working Webots graphical session. The Linux run used
Xvfb and Mesa. The optional loopback TCP transport is useful when local
sockets are unavailable. Use the same transport for both distributions.

```sh
python3 tools/grand_prix/native_frame/bench.py --official /path/to/stock \
  --patched /path/to/patched --output /path/to/new-fast-run --tcp-port 1328 \
  --steps 400
python3 tools/grand_prix/native_frame/bench.py --official /path/to/stock \
  --patched /path/to/patched --output /path/to/new-render-run --tcp-port 1329 \
  --steps 400 --render --fps 25
```

The small falling-body world tests the transport using real ODE contacts.
It compares every shadow frame with the ordinary Supervisor readings on the
same tick, then checks the observed trajectory and contacts against a stock
engine. It also checks duplicate reads, an unrequested frame, a 16-ms step,
a missing node and an immediate RPC while a frame is queued. Timed A/B
runs use the same patched binary in alternating order. The stock engine
is a separate physics control. Every run retains its world, logs, raw
observations and wall-clock timings. `--mode realtime` without
`--render` is available for an isolated render A/B.

## Linux result

Debian 13, x86-64 AMD EPYC 7763, GCC 14, Xvfb at 1280×800, software Mesa
and a TCP loopback Controller. Each of the two experiments compared 400
shadow steps and included 576 descendant-contact records. The independent
stock run matched within 1e-8, and all comparisons against the patched
engine's ordinary Supervisor reads were exact. Each timed arm used 275
steps after a 125-step warmup.

| Mode | Four ordinary physics reads | Compact frame |
| --- | ---: | ---: |
| Fast, no rendering, simulated/wall speed | 23.45–28.10× | 42.34–62.03× |
| Fast, no rendering, read p99 | 0.427–1.480 ms | 0.066–0.106 ms |
| Realtime, software rendering, simulated/wall speed | 0.844–0.888× | 0.853–0.887× |
| Realtime, software rendering, whole-cycle p99 | 61.9–68.3 ms | 63.4–69.5 ms |

The frame removes the four immediate position, orientation, velocity and
contacts RPCs. The read timing starts after the step reply, so it excludes
capture and transport. The whole-cycle measurement includes both. With
rendering enabled the gains in read cost did not remove the observed
long-tail stalls. See [the raw per-run summaries](results-linux.json)
for the measured endpoints and hashes.

The fixture does not run the Grand Prix evaluator, the actual Crazyflie
or Blockly. #910 still needs the route shadow matrix, #911 the mutation
coverage and atomic fence, #912 the rendered Grand Prix bottleneck, and
#914 the personal Windows laptop qualification. The transport supplies no
READY/ALIVE verdict, mutation counter, RESET admission or LAND command.
