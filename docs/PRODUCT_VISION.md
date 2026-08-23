# WebeeBlocks — Product vision

## Purpose

WebeeBlocks is an educational block-programming environment for robotics, aimed primarily at collège students and used at school. Blockly is a means, not the pedagogical goal. Textual code remains invisible to students.

WebeeBlocks is primarily a **training environment for algorithmic reasoning through robotics**, not an LMS, student-tracking system, assessment platform or intelligent tutor.

Students should progressively learn to decompose a problem, build algorithms, use sequences/parameters/loops/conditions/variables, exploit sensors, reason as **measure → compare → decide → act**, and iterate through **modify → run → observe → understand → correct → rerun**.

## Student experience

The normal learning loop should remain simple:

`open activity → understand objective → build program → simulate → observe → debug if needed → modify → rerun → succeed → save manually if needed → move on`

The student UI should not require an account, dashboard, progress page, badge system, ranking or class-management workflow.

The student is responsible for project-file management. WebeeBlocks should provide clear **Open** and **Save / Save As** actions for portable project files stored in the student's personal school folder.

Do **not** add permanent automatic saving, attempt history, success/failure history, score history or automatic student progress tracking. Use Blockly's native Undo/Redo if it is adequate; do not build a separate version-history system without a new explicit need.

## Pedagogical progression

Target a compact guided progression of approximately **8 to 12 substantial activities**, rather than many repetitive micro-exercises.

A reference progression is:

1. sequences and first movements;
2. parameters and precise movement;
3. repetition;
4. sensing;
5. conditions;
6. sensor + condition inside repeated/reactive behavior;
7. several perceptions / nested control flow;
8. variables and memory;
9. open autonomous strategy;
10. final challenge, prepared in simulation and ultimately executed on the real Crazyflie when the physical backend is proven safe and reliable.

The exact number and worlds may evolve, but activities should accumulate prior concepts instead of isolating each concept artificially.

Progression is **teacher-guided**. WebeeBlocks itself does not need per-student unlock state. The teacher decides which activity files/resources are available, for example through Moodle or school storage.

A world may support several activity profiles or difficulty levels where useful.

## Mission vs student program

The activity defines the problem; the student builds the solution.

An activity may define the Webots world, instructions, toolbox, numeric bounds, allowed capabilities, required sensors/actuators, compatible real hardware, success/failure rules, optional time/score, and difficulty profile.

Avoid magic solution blocks such as “avoid obstacle”. Prefer generic primitives that let the student construct the strategy: range sensing, comparisons, conditions, repetition, variables, movement primitives, etc.

Timing/scoring belongs to the activity/world, not to the student algorithm unless the learning objective explicitly requires it.

There is no student-to-student ranking. If an activity uses time or score, it is for the activity itself or for personal optimization, not for a leaderboard.

## Generic activity architecture

New activities should be creatable without changing WebeeBlocks core code whenever possible.

The architecture remains:

`activity/profile → Blockly → backend-neutral AST → preflight → shared interpreter → backend`

The same student program should be able to target Webots and, when relevant and safe, a real Crazyflie without rewriting the Blockly program.

Activity authoring does **not** currently require a teacher-facing graphical editor. Activities may be maintained as declarative, versionable files and created/modified by the project owner with AI/development assistance. Do not build a large “activity studio” without a demonstrated need.

## Execution observability

WebeeBlocks should make program execution observable **without helping the student solve the algorithm**.

Target observability is deliberately limited to:

- highlight the currently executed Blockly block;
- show relevant current sensor values;
- show current variable values.

Do **not** provide pedagogical hints, strategy suggestions, automatic explanations of mistakes, condition-result coaching or decision traces that interpret the program for the student. The student must infer what is wrong by observing the program and the simulated robot.

## Simulation-only debug mode

WebeeBlocks should provide a simple **simulation-only** debugging mode.

The goal is to avoid modifying the student algorithm with artificial `wait` blocks merely to observe execution. Debugging belongs to the environment, not to the student program.

In Webots simulation, debug mode may support only simple high-value controls:

- active block highlighting;
- current sensor values;
- current variable values;
- **Next step**;
- **Continue**;
- **Pause / Resume** if useful;
- restart the simulated mission if useful.

Do **not** add hints, automatic diagnosis, solution guidance, user-configurable breakpoints, watch expressions, call stacks or developer-style debugging panels unless a future explicit pedagogical need justifies them.

**Debug/step-by-step execution is never available on the real Crazyflie in flight.**

## Simulation and real Crazyflie

For almost the entire module, WebeeBlocks is a simulation environment using Webots.

Real flight is not a routine student action and there is no “request a flight” workflow or software queue. The project assumes **one physical Crazyflie** and teacher-managed classroom organization.

Real Crazyflie execution is reserved for the **final activity/finality of the module**. The student prepares and validates the program in simulation. The teacher explicitly authorizes the physical run.

The physical execution path must preserve the same backend-neutral student program and must include independent preflight/safety checks appropriate to the hardware. Real flight uses normal execution only: no step debug and no live pedagogical modification of the program during flight.

The exact final challenge remains dependent on demonstrated physical capabilities. In particular, the table/surface-discontinuity altitude problem tracked by Lab must be resolved before detailed 3D final-course design is treated as product-ready.

## Files, Moodle and assessment boundary

WebeeBlocks is **autonomous and local/offline-first** for school use.

Moodle integration is optional and lightweight. Moodle may distribute activity resources and may receive a submitted WebeeBlocks project file, but WebeeBlocks does not depend on Moodle for its core runtime.

WebeeBlocks does not maintain student accounts, attempt histories, completion histories, grades or mastery levels.

It is primarily an **training tool**, not an assessment platform. If an assessed activity is desired, the student may simply submit the saved WebeeBlocks project file; the teacher evaluates it externally. No dedicated grading subsystem is required.

Home use and browser-only remote execution without the school Webots environment are out of scope unless a future explicit need appears.

## Interface principles

The student UI should be judged by pedagogical usability rather than novelty alone:

- clear and low-clutter;
- easy block nesting and manipulation;
- accessible zoom and navigation;
- explicit values and units;
- clear separation between editing, normal execution and simulation debug mode;
- keyboard/accessibility support;
- simple visible Open / Save actions;
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
- a student account/progress-tracking system;
- an attempt/history analytics platform;
- an automatic tutor or hint system;
- a grading/competency-management platform;
- a leaderboard;
- a permanent autosave/version-history service;
- a teacher-facing activity-authoring suite without demonstrated need;
- a professional debugger.

## Product principles

1. **Compact guided pedagogical progression (about 8–12 activities)**.
2. **Student autonomy: observe, reason and correct without hints**.
3. **Debugging without altering the student program**.
4. **Simulation-only step-by-step debugging; never in real flight**.
5. **Manual, portable student project files; no progress/history tracking**.
6. **Simulation ↔ real-hardware continuity for the student program**.
7. **Real flight only as a teacher-authorized final activity**.
8. **Strict separation between pedagogical problem and student solution**.
9. **Generic configurable activities over task-specific product forks**.
10. **WebeeBlocks stays a focused training tool; Moodle and evaluation remain external concerns**.
