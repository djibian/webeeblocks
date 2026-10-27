# WebeeBlocks — Product vision

## Purpose

WebeeBlocks is an educational block-programming environment for robotics, aimed primarily at collège students and used at school. Blockly is a means, not the pedagogical goal. Textual code remains invisible to students.

WebeeBlocks is primarily a **training environment for algorithmic reasoning through robotics**, not an LMS, student-tracking system, assessment platform or intelligent tutor.

Students should progressively learn to decompose a problem, build algorithms, use sequences/parameters/loops/conditions/variables, exploit sensors, reason as **measure → compare → decide → act**, and iterate through **modify → run → observe → understand → correct → rerun**.

## Pupil-program feasibility and classroom delivery (owner decision, 2026-10-22)

### Méthode de conception prioritaire — décision du propriétaire, 27 octobre 2026

**Cette méthode sera appliquée à la prochaine reprise du Grand Prix ; les travaux
Grand Prix restent actuellement suspendus au profit de la santé technique de
WebeeBlocks** (voir #587, décision du 27 octobre). Elle ne crée aucune
nouvelle fonctionnalité, autorisation de vol ou acceptation pédagogique.

- **Concevoir d'abord pour l'élève.** Partir des apprentissages observables :
  concevoir, construire **sans programme complet fourni**, expliquer, observer,
  diagnostiquer et corriger la stratégie. Une solution dont on sait seulement
  charger et exécuter un .wbb expert est une **preuve technique**, pas une
  solution de classe.
- **Explorer des stratégies structurellement différentes** et accepter de
  repartir de zéro lorsque l'amélioration d'un témoin expert ne réduit pas
  substantiellement les décisions, l'état mental et les manipulations.
  Comparer plusieurs approches; documenter pourquoi les alternatives échouent.
- **Chercher les bonnes primitives génériques avant d'ajouter des blocs au
  programme final.** Elles peuvent encapsuler l'exécution bas niveau bornée,
  pas reconnaître un H, un côté, une destination ou consulter l'oracle caché.
  Démontrer leur intérêt sur **au moins une autre situation pédagogique
  indépendante**, leurs limites et leur traçabilité en pas-à-pas.
- **Faire primer une épreuve d'autonomie représentative** : partir d'un
  projet initial et d'acquis enseignés, construire une partie non triviale,
  expliquer les observations et corriger une erreur sans solution fournie.
  Comparer aide nécessaire, erreurs, compréhension et autonomie; ne jamais
  déduire un PASS d'un comptage de blocs, de CI ou de Save/Open simulé.
- **Mesurer sans fabriquer de note pédagogique automatique.** Les nombres de
  blocs, variables, conditions, imbrications et constantes décrivent la
  structure réelle d'un .wbb et orientent une enquête, non un seuil, une
  note cognitive ou un GO. Les 67 blocs de #660 et les 232–234 blocs de
  #703/#705 représentent des stratégies historiquement différentes, mais
  leurs réussites natives ne sont pas interchangeables sur le monde sans murs.

L'ordre d'exploration pédagogique recommandé devient : **objectifs d'apprentissage
→ stratégie élève → besoin éventuel de primitive réutilisable → vrai .wbb
→ construction/debug par l'élève → qualification native obligatoire et
acceptation personnelle**. Un contrôle de sécurité/préflight reste préalable à
toute exécution, quelle que soit la phase de conception. Toutes les règles de
mission, négatifs, RESET et LAND indépendant à 210 secondes restent intacts.


**Deliverable first:** WebeeBlocks must be genuinely teachable and usable by
collège pupils from the first activity through the simulation Grand Prix. A
technically executable reference program and green automated CI establish only
technical properties; they do not establish that pupils can construct,
understand, debug and improve the solution after the preceding lessons.

For each significant activity, and especially the autonomous Grand Prix, use
real student-editable `.wbb` workspaces and record **reproducible evidence of
pupil-program complexity**: total Blockly blocks including procedure bodies,
visible variables and procedures, nesting, length/readability of the main flow,
parameter-tuning burden and editor navigation, step-by-step observation,
correction and Save/Open. Explain which decisions are actually made by the
pupil and which generic blocks legitimately automate only low-level control.
Assess whether the concepts needed by the final program can realistically be
learned cumulatively in Activities 1–7. A screen-height or block count alone
is neither a proof nor a failure criterion.

**Design freedom:** two variables, one procedure, a three-side repeat and
previously proposed block inventories are useful hypotheses, **not syntax,
variable-count or algorithm-shape requirements**. Prefer fewer cognitive
operations and genuine `observe → compare → decide → act` decisions; generic
primitives may hide routine motor control but must not reveal gate identity,
the correct destination, hidden world state or the solution strategy. Do not
optimize only for the smallest number of blocks or impose arbitrary block,
variable, procedure or nesting caps. Explain trade-offs and test alternative
pupil strategies where helpful.

**Acceptance boundary:** the same ordinary pupil-authored program must meet
the unchanged native Webots Grand Prix rules and negative oracles across the
required hidden configurations. Classroom-style usability and the owner's
**explicit personal pedagogical acceptance** remain separate from CI and
independent technical GO. Deliver the accepted simulation progression before
speculatively broadening hardware or features. Independent, safety-qualified
#157/#72 physical work may continue when useful, but no simulation success
authorizes flight. The Phase 2 rule remains: do not redesign Activities 2–7
officially before both endpoint acceptances. V5 and all mission/safety
invariants are unchanged. See #587 and its owner decision of 2026-10-22.

## Student experience

The normal learning loop should remain simple:

`start activity → understand objective → build program → simulate → observe → debug if needed → modify → rerun → succeed → save manually if needed → move on`

The student UI should not require an account, dashboard, progress page, badge system, ranking or class-management workflow.

The student is responsible for project-file management. WebeeBlocks should provide clear **Open** and **Save / Save As** actions for portable project files stored in the student's personal school folder.

**Start activity** and **Open** are two distinct student intents and should remain visibly separate:

- **Start activity** should present a simple ordered chooser of the available activity starters rather than a generic project-file picker. Selecting an activity loads its starter as a template and deliberately leaves no current save target, so the student's first persistence action is **Save As**.
- **Open** should use the normal project-file picker to resume an existing student `.wbb` file and bind that file as the current save target for later **Save** actions.
- Activity starters and student projects may use the same `.wbb` format, validation and loader. Do **not** introduce a second activity-file format merely to distinguish these two workflows.

The activity chooser is a small launch surface for the teacher-guided progression, not a dashboard, catalogue service, unlock system or progress tracker.

Do **not** add permanent automatic saving, attempt history, success/failure history, score history or automatic student progress tracking. Use Blockly's native Undo/Redo if it is adequate; do not build a separate version-history system without a new explicit need.

## Pedagogical progression

The official progression contains **eight substantial activities**:

1. **Activity 1 — first Blockly discovery:** a very simple sequence, blue
   start, non-colliding checkered arrival on the floor, uncluttered scene,
   accessible camera and immediately legible mission outcome.
2. **Activities 2–7 — cumulative acquisition:** six new, concrete problem
   situations, each reusing the relevant previous concepts. Their precise
   concept order and scenarios will be co-designed after both endpoints
   receive explicit owner acceptance.
3. **Activity 8 — autonomous Grand Prix (#587):** the **sole official final
   synthesis** combining earlier notions with a same-program autonomous
   strategy across different unknown gate configurations. The previously
   integrated warehouse-delivery Activity 8 (#529) is historical technical
   material, not an additional official final activity.

Every activity must make its target concept useful through its own world and
mission, with behaviorally observable success. Technical implementation,
passing CI and independent Controller GO do **not** equal the owner's
pedagogical acceptance.

Progression is **teacher-guided**. WebeeBlocks itself does not need per-student unlock state. The teacher decides which activity files/resources are available, for example through Moodle or school storage.

**Each of the eight activities must have a distinct pedagogical world as seen
by pupils**, including mission-specific geometry, objects and camera. Webots
controllers, assets and a base `.wbt` may be shared; **eight standalone `.wbt`
files are not required**. Versioned, isolated scenes/configurations are
appropriate when switching activities, opening a `.wbb`, restarting and
reconnecting correctly restore the selected scene and its world evaluators.
Technical sharing must not make pupil worlds indistinguishable. The Grand Prix
uses **multiple reproducible configurations of its own world**, with constant
dimensions/rules and hidden variations in number and placement of gates.

The **official Activity 8, Grand Prix autonome** (#587), is a simulation-first
final challenge with **one traversal of three consecutive sides of a fixed-size
square**, with **1–3 ordinary open H gates** (at most one per side) placed
reproducibly but unknown to the student program, and a **closed H gate** at the
end of the third side. There is **no fourth side, no final straight, no repeated
laps, no gate bonuses, time penalties or software scoring**. A pupil remembers
completed gate crossings to choose landing before the closed gate: **one = center,
two = 0.50 m left, three = 0.50 m right**, relative to arrival. Wrong landing
means a failed mission; memory is behaviorally useful rather than enforced by
inspecting Blockly syntax.

The candidate geometry starts at **2.00 m side**, about **1.00 m corridors**
and a larger terminal landing area; native Webots R2025a tests must establish
a fixed feasible dimension with comfortable reproducible time and dynamic
clearance margins, rather than assuming or maximizing course size. The
floor remains uniform with **no low obstacles**. Low-altitude flight is legal
only within marked before/after distances around each open H gate, apart from
bounded takeoff, final landing and forced-timeout landing exceptions. Identical
lines **marked on the Webots floor** represent the future physical tape limits;
the observable-world oracle rejects any low flight outside these zones.

A fixed **210-second attempt limit** is an owner-chosen mission rule, not a
measured battery life. Independent simulation authority marks the attempt
failed and orders **immediate landing at any position** upon timeout, even in a
gate; no later pose restores success. Successful completion requires the
correct stable landing **before** the deadline. The UI shows only attempt
success/failure, Webots elapsed time and a failure reason; **no class leaderboard,
score or persistent attempt history**. Only the future teacher-organized real
final challenge may compare **successful flights by time on the same physical
course**, externally to WebeeBlocks. Real-flight capabilities, authority,
monitoring, margins and recovery remain unqualified and gated by #157/#72.

See the falsifiable simulation design in
docs/GRAND_PRIX_SIMULATION_CONTRACT.md and the controlling issue #587. All
historical gp-v2/v3/v4 native results remain scoped to their older worlds,
not acceptance of the new course. Do not redesign intermediate activities before
explicit personal acceptance of both Activity 1 and Activity 8.

**Superseding owner pedagogical decision (#587, 2026-10-15):**
#487 and the integrated progression 1–8 established technical capability,
declarative scenarios and executable oracles, **not pedagogical acceptance**.
Their profiles, missions, negative tests and evidence must remain historically
traceable. The current Activity 8 warehouse delivery (#529) will be removed
from the **official active progression** by a future reviewed implementation
change and replaced by the Grand Prix, without deleting useful evidence.

**Phase 1 — personally validate both endpoints.** Finalize Activity 1 (#589)
and Grand Prix (#591) with real Webots R2025a tests, exact Ready-HEAD CI,
independent V5 reviews and applicable oracles; then obtain the owner's
**explicit personal pedagogical acceptance of each**. Activity 1 received the
owner's [explicit personal pedagogical PASS on #619](https://github.com/djibian/webeeblocks/issues/619#issuecomment-6230830327)
on 2026-10-17 for exact `a38839628c99bf38278ca950ed8e68f363d1b5b3`
(Windows R2025a / Chrome, artifact 12073312927). The distinct startup corrections (#622/#623/#630) subsequently received the
owner's [Windows PASS on #632](https://github.com/djibian/webeeblocks/issues/632#issuecomment-6247199523)
for exact `39b0841c52f9db91ddbc3f80ba3bc1588fab9489`; #621 is closed.
This later result does not transfer #619's acceptance to another artifact and
accepts neither the Grand Prix nor Activities 2–7.
Grand Prix acceptance remains outstanding and requires
the unchanged #587 U course: multiple reproducible hidden configurations of
1–3 open H gates, a single ordinary Blockly/.wbb/AST program across them,
correct center/left/right landing, low-altitude bands, negative cases and the
independent immediate LAND command at exactly 210 s. The complete pupil
start/simulate/observe/debug/Save/Open workflow must be exercised. A green
CI or an independent GO is **not** an owner's pedagogical PASS.

**Phase 2 — mandatory rebuild of Activities 2–7 after both acceptances.**
The currently integrated intermediate scenarios are **technical prototypes
not personally accepted pedagogically**. Their common visually cluttered
environment has already been judged inadequate by the owner. First agree a
single six-activity cumulative concept/world/mission/prerequisite/outcome
matrix with the owner. Then redesign their six distinct pedagogical
environments and cumulative missions, in separately reviewable changes.
Validate each pedagogically and technically, then obtain the owner's explicit
acceptance of the complete eight-activity progression. This is an actual
product dependency, not merely a roadmap preference. It does not block
independent technical repair or qualification of endpoints.

**Possible physical finale:** the Grand Prix may culminate **if possible** in
a real teacher-authorized flight, but only if the exact mission and
capabilities have been separately qualified under #157/#72 with measured
clearances, control, recovery and energy margins. Simulation acceptance never
authorizes a flight or implies real-world endurance at 210 s, and does not
depend on achieving a physical finale.

The progression should build both programming concepts **and legible
understanding of 3D space** from a minimal first activity. The owner's
observations found the common scene of activities 1/2 visually cluttered.

## Mission vs student program

The activity defines the problem; the student builds the solution.

The **student-facing mission** and the **internal pedagogical objective** are distinct. A sentence such as “memorize a measured distance and reuse it” may describe an internal learning objective, but it is not by itself a complete scenario or student mission. The student must receive a concrete, explicit and sufficiently complete problem situation that explains what the robot/drone must accomplish and what observable outcome constitutes success.

A substantial learning activity should define the Webots world/scenario, student mission, initial state, toolbox, numeric bounds, allowed capabilities, required sensors/actuators, compatible real hardware where relevant, observable success rules, optional failure rules, optional time/score and difficulty profile.

The world is part of the pedagogy, not a neutral background. Its geometry, obstacles, zones, events, sensor availability and other constraints should create the need for the target concept. Prefer situations in which the concept is functionally necessary or the natural algorithmic response to the mission rather than merely required by wording.

For each activity, the intended design should be explainable as:

`new concept → world property that makes it necessary → student mission → prior concepts reused → executable success criteria`

Examples of this rule include:

- repetition: the world contains a genuine repeated structure or task;
- condition: materially different situations require different behaviours;
- sensing: information from the world is necessary for a later decision;
- several perceptions: a decision genuinely depends on several observations;
- variable/memory: information is acquired at one time, later becomes unavailable, and must be reused in several later decisions;
- open autonomous strategy: several prior concepts must be combined without encoding the strategy in task-specific magic blocks.

The student may be told which new concept will be useful — for example that a variable will be needed to remember information — without being given the algorithmic solution. Later activities should naturally reuse prior sequences, parameters, repetition, sensing, comparisons, conditions and variables instead of resetting to isolated exercises.

Avoid magic solution blocks such as “avoid obstacle”. Prefer generic primitives that let the student construct the strategy: range sensing, comparisons, conditions, repetition, variables, movement primitives, etc.

Timing/scoring belongs to the activity/world, not to the student algorithm unless the learning objective explicitly requires it.

There is no student-to-student ranking. If an activity uses time or score, it is for the activity itself or for personal optimization, not for a leaderboard.

## Executable activity outcome

A substantial activity should be able to determine whether its **mission** was achieved from observable world/mission state rather than by matching one expected Blockly solution.

The activity contract may therefore define:

- explicit initial state;
- one or more observable success conditions;
- explicit failure conditions when useful;
- unfinished/interrupted state when relevant.

At the end of an execution, WebeeBlocks should provide a simple non-prescriptive outcome such as **mission achieved**, **mission not achieved** or **interrupted**. This feedback belongs to the activity loop and is not an assessment history, automatic tutor or solution diagnosis.

Do **not** infer success from the presence of particular blocks, a specific AST shape or one reference strategy. Do **not** provide pedagogical hints, strategy suggestions or automatic explanations of failure. The student should still learn through observation, reasoning, modification and rerun.

## Generic activity architecture

New activities should be creatable without changing WebeeBlocks core code whenever possible.

The architecture remains:

`activity/profile → Blockly → backend-neutral AST → preflight → shared interpreter → backend`

The same student program should be able to target Webots and, when relevant and safe, a real Crazyflie without rewriting the Blockly program.

An activity starter may remain a `.wbb` project that references a declarative activity/profile and contains the initial Blockly workspace. The complete pedagogical definition of the activity does not need to be duplicated into the starter file; the activity chooser selects the starter/profile workflow, while **Open** resumes an already-created project.

Activity authoring does **not** currently require a teacher-facing graphical editor. Activities may be maintained as declarative, versionable files and created/modified by the project owner with AI/development assistance. Do not build a large “activity studio” without a demonstrated need.

The generic variable vocabulary should support ordinary memory operations coherently, including reading/assigning a variable and **changing a variable by a value** so increment, decrement, counters and accumulators do not require task-specific blocks.

## Reference Crazyflie capability coverage

The reference physical platform is **Crazyflie 2.1 with Flow Deck V2, Multi-ranger and a bottom-mounted Color LED Deck**.

WebeeBlocks should cover as completely as practical the **pedagogically useful capabilities** of this reference hardware through the smallest coherent set of generic, composable Blockly primitives. The objective is capability coverage, not maximum block count or one block per firmware feature.

Capability breadth belongs to the global Blockly/runtime catalogue. Individual activity profiles expose only the subset needed for their learning objective, so a rich platform does not imply a complex beginner toolbox.

For student-facing capabilities, preserve when relevant the same intent through:

`activity/profile → Blockly → backend-neutral AST → preflight → shared interpreter → backend`

A capability intended for both simulation and real hardware should have an observable equivalent in Webots and on the physical backend once that backend is proven safe. Internal estimator diagnostics, firmware tuning parameters and safety mechanisms remain infrastructure unless a demonstrated pedagogical need makes them student-facing.

The Webots reference Crazyflie should eventually represent the bottom-mounted Color LED Deck with a **simple, reasonably recognizable model and a visible controllable light surface**. Simulate the pedagogically observable light effect, not deck electronics, electrical consumption, thermal behavior or photometric fidelity.

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

Real Crazyflie execution is reserved for the **final activity/finality of the module**, if separately proven feasible and safe. The student prepares and validates the program in simulation. Any physical run requires explicit teacher authorization after the independent #157/#72 gates. The Grand Prix is the possible real-world culmination, not a currently qualified flight mission.

The physical execution path must preserve the same backend-neutral student program and must include independent preflight/safety checks appropriate to the hardware. Real flight uses normal execution only: no step debug and no live pedagogical modification of the program during flight.

The final real-flight mission must be achievable over a qualified, uniform-floor
corridor without crossing a raised surface. It may use only physically proven
capabilities, preflight checks, safety margins and failure handling. The broader
simulation progression may include richer scenarios, but the exact student
program selected for physical execution must first be validated in simulation
and then executed unchanged under explicit teacher authorization. A physical
course cannot be product-ready before its relevant safety/capability gates pass.

**Immediate physical milestone (#157; owner decision 2026-10-14):** establish
reliable and safe execution of **one simple, unchanged Blockly program** on the
real reference Crazyflie before expanding physical capabilities. The existing
engineering candidate `tools/physical/hover_range_comparison.wbb` uses the
ordinary project/profile/Blockly/AST/preflight/shared-interpreter path:
take off to 0.50 m, wait 1.00 s, take one `range(front)` reading, then land
on a uniform floor. It must first succeed with the exact same program in
Webots. This is a **qualification witness**, not a released pupil activity or
authorization of a real test or the physical Grand Prix.

Physical acceptance requires separately authorized and externally witnessed
evidence of the actual flight domain: in-flight ranging under thrust, observed
XY/Z/attitude excursions, adequate clearance or containment, operator abort
and terminal recovery under applicable faults, and justified real-world timing
and under-load energy margins. Synthetic calculations, green CI and the
simulation-only 210 s rule do **not** qualify these bounds. Keep single-radio
host authority, trusted teacher approval, fail-closed recovery and independent
V5 review/checkpoint requirements. Failed or unavailable evidence remains
FAIL/UNPROVEN; no automatic retry or hardware action follows from this
decision. Prefer the shortest concrete proof over additional speculative
primitives or infrastructure. Broaden movements, sensors and LED behaviors
incrementally **after** an accepted limited physical result, each within its
own evidenced domain; #72 remains independently gated.

Lab #70 remains optional research toward stable **world-frame altitude** across
floor → table → floor, acceptable X/Y behavior and safe recovery. Terrain-
following ascent/descent is not an acceptable substitute. Research #70 is not
a prerequisite for a uniform-floor final mission, and no unqualified physical
table crossing may be offered to students.

## Files, Moodle and assessment boundary

WebeeBlocks is **autonomous and local/offline-first** for school use.

Here, **offline-first means independent of Internet/external online services for the core classroom runtime, not independent of the school's local infrastructure**. The supported classroom environment may rely on normal school-local services required to open a student session and access the student's personal network folder (for example a mapped `U:` drive). A total loss of the school LAN, when students cannot normally log in or access that storage, is outside the supported runtime condition and must not be used as an acceptance requirement by itself.

Core execution, simulation, project **Open / Save / Save As** and activity use must not require Internet access, Moodle, cloud storage, CDN assets, external APIs or another online service once the supported school session/environment is available. A project target that is itself network-hosted naturally remains subject to availability of that school-local storage.

Moodle integration is optional and lightweight. Moodle may distribute activity resources and may receive a submitted WebeeBlocks project file, but WebeeBlocks does not depend on Moodle for its core runtime.

WebeeBlocks does not maintain student accounts, attempt histories, completion histories, grades or mastery levels.

It is primarily a **training tool**, not an assessment platform. If an assessed activity is desired, the student may simply submit the saved WebeeBlocks project file; the teacher evaluates it externally. No dedicated grading subsystem is required.

Home use and browser-only remote execution without the school Webots environment are out of scope unless a future explicit need appears.

## Interface foundation and principles

The technical student-programming foundation is now **fixed**:

**Blockly 13.2.1 + Zelos**.

Zelos is retained because its block geometry is the Blockly renderer most aligned with the Scratch interaction patterns already familiar to many collège students. This is a pedagogical continuity choice, not a request to copy Scratch or depend on Scratch as a product.

The goal is a distinct WebeeBlocks interface that preserves the useful Scratch-like qualities of block manipulation and nesting while remaining focused on robotics.

The student UI should therefore be judged by pedagogical usability rather than novelty alone:

- clear and low-clutter;
- easy, visually explicit block nesting and manipulation;
- clear distinction between actions, values and boolean/condition expressions;
- accessible zoom, reset/fit and navigation;
- explicit values and units;
- readable toolbox/flyout with restrained category colour use;
- modern but sober typography, spacing and contrast;
- clear separation between editing, normal execution and simulation debug mode;
- keyboard/accessibility support;
- visibly distinct **Start activity**, **Open**, **Save** and **Save As** actions with student-appropriate semantics;
- familiarity with useful Scratch interaction patterns without reproducing all of Scratch.

Renderer comparison is closed: do **not** reopen Thrasos vs Zelos without a new demonstrated need. Future UI work should improve the WebeeBlocks presentation and ergonomics **on top of Zelos** while preserving the backend-neutral AST and Runtime behavior.

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

1. **Compact guided pedagogical progression (about 8–12 substantial problem situations), with quality and cumulative learning taking precedence over activity count**.
2. **Each activity is an explicit student mission in a world designed to make the target concept useful/necessary while reusing prior concepts**.
3. **Executable mission outcomes provide simple success/failure/interruption feedback without solution matching, hints or persistent progress tracking**.
4. **Student autonomy: observe, reason and correct without hints**.
5. **Debugging without altering the student program**.
6. **Simulation-only step-by-step debugging; never in real flight**.
7. **Manual, portable student project files; activity starters are templates and resuming an existing project remains a distinct workflow; no progress/history tracking**.
8. **Simulation ↔ real-hardware continuity for the student program**.
9. **Real flight only as a teacher-authorized final activity**.
10. **Strict separation between pedagogical problem and student solution**.
11. **Generic configurable activities over task-specific product forks**.
12. **WebeeBlocks stays a focused training tool; Moodle and evaluation remain external concerns**.
13. **Blockly 13.2.1 + Zelos is the fixed visual-programming foundation; Scratch familiarity guides ergonomics without turning WebeeBlocks into a Scratch clone**.
14. **Broad reference-hardware capability coverage through a small generic Blockly vocabulary, with simulation/physical continuity where relevant**.
