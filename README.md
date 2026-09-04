# 🐝 WebeeBlocks

### Learn algorithms with blocks. Test them on a drone.

> **We be blocks. Bee free!**

WebeeBlocks is an **offline-first educational robotics environment** for learning
algorithmic reasoning with a Crazyflie drone.

Students build programs visually with **Blockly**, run and debug them in
**Webots**, observe the simulated drone, correct their algorithm and try again.
The long-term physical path preserves the same backend-neutral student program:
real flight is reserved for a final, teacher-authorized activity once the
hardware backend is proven safe and reliable.

**Simulation first. Reasoning first. No textual code required for students.**

[![Webots](https://img.shields.io/badge/Webots-R2025a-blue)](https://cyberbotics.com/)
[![Blockly](https://img.shields.io/badge/Blockly-13.2.1-blue)](https://developers.google.com/blockly)
[![Renderer](https://img.shields.io/badge/Renderer-Zelos-blue)](https://developers.google.com/blockly)
[![Classroom](https://img.shields.io/badge/Classroom-offline--first-success)](#classroom-ready-foundation)

## Why “WebeeBlocks”?

- **🐝 Bee** — a nod to the characteristic buzz of a Crazyflie in flight;
- **🌐 Web** — the project lives inside the Webots simulation environment;
- **🧱 Blocks** — students program with Blockly blocks rather than textual code;
- **🤝 We be** — “we be blocks”: small reusable pieces combine into richer algorithms.

The goal is not to make programming disappear. It is to let students focus on
**decomposing a problem, expressing an algorithm, observing its effects and correcting it**.

## The student learning loop

```text
open an activity
      ↓
understand the objective
      ↓
build a Blockly program
      ↓
simulate in Webots
      ↓
observe / debug
      ↓
modify → rerun → understand
      ↓
succeed and save the .wbb project
```

A compact progression of roughly **8–12 substantial activities** is the target:
sequences, parameters, loops, sensing, conditions, reactive behaviour, variables,
memory and finally open autonomous strategies.

WebeeBlocks deliberately avoids automatic hints, student accounts, progress
dashboards, rankings and grading workflows. It is a **training environment for
reasoning**, not an LMS or an automatic tutor.

## What WebeeBlocks provides

- **🧩 Blockly 13.2.1 + Zelos** — a clear Scratch-familiar visual foundation;
- **🚁 Crazyflie simulation in Webots R2025a** — the normal classroom execution environment;
- **🇫🇷 French student interface** — including custom robotics blocks;
- **▶️ normal and step-by-step simulation execution** — with active-block highlighting;
- **📡 sensor-based programming** — _measure → compare → decide → act_;
- **💾 portable `.wbb` projects** — explicit Open, Save and Save As;
- **🔌 offline-first classroom operation** — no cloud dependency for the normal learning loop;
- **🧠 backend-neutral student programs** — Blockly feeds an AST, preflight and shared interpreter.

## Reference Crazyflie platform

The reference hardware target is:

**Crazyflie 2.1 + Flow Deck V2 + Multi-ranger + bottom-mounted Color LED Deck**

WebeeBlocks aims to cover as completely as practical the **pedagogically useful
capabilities** of this configuration with the **smallest coherent set of generic,
composable Blockly primitives**.

```text
broad capability coverage
        ≠
maximum number of blocks
```

Activities expose only the capabilities appropriate to their learning objective.
A beginner toolbox can therefore remain simple while the global WebeeBlocks
vocabulary becomes progressively richer.

Where relevant, a student-facing capability should preserve the same intent in
simulation and on real hardware. The planned Color LED support, for example,
uses a simple, reasonably recognizable bottom-deck representation in Webots with
a visible controllable light surface rather than a detailed electronics simulation.

See [issue #157](https://github.com/djibian/webeeblocks/issues/157) for the
capability-coverage objective.

## Classroom-ready foundation

The current reference classroom path already includes:

- Webots R2025a + automatically opened Robot Window;
- Blockly 13.2.1 with Zelos;
- French student-facing controls;
- normal and step execution;
- reset/replay behaviour;
- Open / Save / Save As for portable projects;
- an offline Windows classroom artifact path;
- validated low-end Windows classroom operation with Chrome.

Simulation remains the normal mode for almost the whole module. Physical flight
is intentionally **not** a routine student action.

## Simulation → real hardware

```text
activity / profile
        ↓
      Blockly
        ↓
backend-neutral AST
        ↓
      preflight
        ↓
 shared interpreter
      ↙       ↘
   Webots    physical backend
   today     when proven safe
```

The future real-flight activity uses the **same student program** previously
validated in simulation, with independent capability, preflight and safety checks
plus explicit teacher authorization.

Detailed physical capability work remains evidence-driven. In particular,
world-altitude behaviour over floor/table/floor surface changes is tracked in
[#70](https://github.com/djibian/webeeblocks/issues/70).

## Product direction

The durable product intent is maintained in
[`docs/PRODUCT_VISION.md`](docs/PRODUCT_VISION.md), with a compact dependency
projection in [`docs/ROADMAP.md`](docs/ROADMAP.md).

Current direction includes:

- a coherent teacher-guided **8–12 activity progression**;
- declarative activity profiles exposing only the right blocks and constraints;
- broad capability coverage for the reference Crazyflie + decks;
- continued simulation/physical continuity;
- a final real-flight activity only after the physical backend and safety path are proven.

## Prepare the current Runtime

These are **developer preparation commands**. Students do not run them.

Linux:

```bash
./tools/prepare_runtime_v2.sh
```

Windows PowerShell:

```powershell
./tools/prepare_runtime_v2.ps1
```

The Windows classroom artifact additionally contains the compiled controller,
local R2025a Robot Window bridge, offline Crazyflie assets, one-click launcher
and integrity manifest.

See [`docs/WINDOWS_DEPLOYMENT.md`](docs/WINDOWS_DEPLOYMENT.md).

## Repository map

| Path | Purpose |
| --- | --- |
| `plugins/robot_windows/blockly_v2/` | current Blockly Robot Window UI |
| `plugins/robot_windows/blockly/webeeblocks/` | AST, interpreter and product contracts |
| `controllers/crazyflie_runtime_v2/` | current Webots Runtime controller |
| `worlds/` | Webots activities and regression worlds |
| `tools/ci/` | executable acceptance oracles and preparation tools |
| `experiments/` | explicitly non-product research artifacts |

## Development model

WebeeBlocks uses a small, trunk-based V4 development contract:

- `main` is the single healthy integration trunk;
- independent Controller executions may work concurrently from isolated branches/worktrees;
- Draft means mutable work; Ready offers the current exact HEAD for validation and is expected to remain stable, but is not a coordination lock;
- positive decision evidence applies only to the exact candidate SHA;
- applicable authoritative refutations remain relevant until an independent review establishes them as resolved or no longer applicable;
- `CI Gate`, independent exact-candidate review and exact-head conditional merge protect integration;
- real-world validation crosses one explicit boundary: `TEST_REQUIRED`.

See [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) and [`AGENTS.md`](AGENTS.md).

## Contributing

WebeeBlocks is developed in public. Issues and pull requests are welcome as
evidence, proposals or contributions; integration follows the current product,
CI and review contract.

For product intent, start with [`docs/PRODUCT_VISION.md`](docs/PRODUCT_VISION.md).

## License

The project declares GPL-3.0. Bundled third-party components retain their own
license notices; a classroom release must preserve them.
