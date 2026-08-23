# WebeeBlocks — Product vision

## Purpose

WebeeBlocks is an educational block-programming environment for robotics, aimed primarily at collège students. Blockly is a means, not the pedagogical goal. Textual code remains invisible to students.

Students should progressively learn to decompose a problem, build algorithms, use sequences/parameters/loops/conditions/variables, exploit sensors, reason as **measure → compare → decide → act**, and iterate through **modify → run → observe → understand → correct → rerun**.

## Pedagogical progression

Activities should introduce concepts progressively rather than merely changing scenery. A typical progression is:

1. sequences;
2. parameters;
3. repetition;
4. sensors;
5. conditions;
6. sensor + condition;
7. nested loops/conditions;
8. variables;
9. autonomous strategy.

A world may support several activity profiles or difficulty levels.

## Mission vs student program

The activity defines the problem; the student builds the solution.

An activity may define the Webots world, instructions, toolbox, numeric bounds, allowed capabilities, required sensors/actuators, compatible real hardware, success/failure rules, optional time/score, and difficulty profile.

Avoid magic solution blocks such as “avoid obstacle”. Prefer generic primitives that let the student construct the strategy: range sensing, comparisons, conditions, repetition, variables, movement primitives, etc.

Timing/scoring belongs to the activity/world, not to the student algorithm unless the learning objective explicitly requires it.

## Generic activity architecture

New activities should be creatable without changing WebeeBlocks core code whenever possible.

The architecture remains:

`activity/profile → Blockly → backend-neutral AST → preflight → shared interpreter → backend`

The same student program should be able to target Webots and, when relevant and safe, a real Crazyflie without rewriting the Blockly program.

## Execution observability

WebeeBlocks should help students understand what their program is doing, without exposing developer-oriented logs.

Target observability includes:

- highlight the currently executed block;
- show relevant sensor values;
- show current variable values;
- show the result of conditions;
- show a short pedagogical decision trace, e.g. `0.42 < 0.50 → true → then branch → move left`.

The trace must remain concise, readable and pedagogical.

## Simulation-only debug mode

WebeeBlocks should provide a simple **simulation-only** debugging mode.

The goal is to avoid the common Scratch workaround where students insert `wait 1 s` blocks only to see what is happening. Debugging belongs to the environment, not to the student program.

In Webots simulation, debug mode should support only the simple high-value controls:

- active block highlighting;
- current sensor/variable/condition values;
- **Next step**;
- **Continue**;
- **Pause / Resume** if useful;
- restart the simulated mission if useful.

Do **not** add sophisticated debugger functions such as user-configurable breakpoints, watch expressions, call stacks or developer-style debugging panels unless a future explicit pedagogical need justifies them.

**Debug/step-by-step execution is never available on the real Crazyflie in flight.** Real-hardware execution remains normal runtime only, subject to its own safety/arming/failsafe rules.

## Main activity families

The first major family remains autonomous navigation:

- simple known trajectory;
- known fixed obstacles;
- reactive obstacle avoidance using sensor decisions;
- unknown/variable obstacles;
- autonomous strategy and optional optimization/time trial.

A second family should demonstrate that WebeeBlocks is not only an obstacle-course tool, for example light-show/choreography activities using sequences, repetition, variables, movements, colors/LEDs and synchronization where supported.

## Interface principles

The student UI should be judged by pedagogical usability rather than novelty alone:

- clear and low-clutter;
- easy block nesting and manipulation;
- accessible zoom and navigation;
- explicit values and units;
- clear separation between editing, normal execution and simulation debug mode;
- keyboard/accessibility support;
- familiarity with useful Scratch interaction patterns without trying to reproduce all of Scratch.

Renderer/theme decisions (for example Thrasos vs Zelos) should be based on these criteria and real student-use scenarios, not only on which renderer looks newer.

## Explicit non-goals

WebeeBlocks is not intended to become:

- a Python-teaching environment;
- a textual-code-first IDE;
- a complete Scratch clone;
- a collection of magic task-specific blocks;
- a complex student-facing Webots world editor;
- a multi-robot platform merely for breadth;
- an LMS/class-management system;
- a professional debugger.

## Product principles

1. **Pedagogical progression**.
2. **Understanding execution and decisions**.
3. **Debugging without altering the student program**.
4. **Simulation-only step-by-step debugging; never in real flight**.
5. **Simulation ↔ real-hardware continuity for the student program**.
6. **Strict separation between pedagogical problem and student solution**.
7. **Generic configurable activities over task-specific product forks**.
