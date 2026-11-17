# Activity 5 — independent H-fixed / G-binary first hypothesis

**NOT QUALIFIED for pupils — Draft-only evidence, not an activity, GO or native pupil PASS.** The four H×G motor flights plus blind-G and blind-H physical refusals passed R2025a in [run #44161235547](https://github.com/djibian/webeeblocks/actions/runs/44161235547) on earlier HEAD `15ae2da`; those proofs concern the **private two-reading JS pilot only**, not any Blockly `.wbb` or an accessible activity 5.

The approved activity 5 introduces repeated observation and then one useful state
variable. Historical #980 and #1025 show that a second L or a late detour can
reveal the initial destination clue without stored state. The next design must
separate the information roles rather than hide evidence or enforce Blockly AST
syntax.

## Physical proposal (first of two independent factors)

H is an identical, real L-shaped initial cue in BOTH experimental scenes:
arm (0.00,+0.58), tip (+0.20,+0.78), height 1.10 m.
It determines the **future landing destination** only. Two identical visible pads
at (4.15,+0.62) and (4.15,-0.62) avoid giving the destination away locally.
The starting point (0,0) and common approach marker (2.50,0) are identical.

G lies downstream around x=3.10, out of the 2 m frontal sensor range at
the start. Its 1.10 m tall collision-box walls leave a 0.62 m-class aperture
around y=+0.60 (G-left) or y=-0.60 (G-right), with common side boundaries
at y=±1.45. A physical side arm at x=2.45,y=-0.58 / +0.58 should make
the G variant observable from the approach via the **left** range sensor
without changing the original H measurement. The chosen aperture is independent
of the initial H; no virtual labels or hidden course metadata reach Blockly.

The actual aperture clearances, sensor readings and achievable trajectories are
**proposals** until measured. The authored source WBOs do not create a valid
activity or independently validate collision avoidance. The experimental
classroom Floor must be enlarged by an isolated CI world composer before
motorized trials, not by changing the official Grand Prix world.


## Extension 2×2 H proche/loin × G gauche/droite — hypothèse, pas PASS

Deux nouvelles scènes CI (`hfar-gleft`, `hfar-gright`) conservent
**strictement les mêmes** obstacles G et les deux damiers que leurs
homologues H proches. Les deux `Solid` H seuls sont décalés de +0,60 m
en y (0,58/0,78 vers 1,18/1,38). Le contrôleur télémétrique natif
R2025a vérifie les boîtes physiques exactes et le Crazyflie original.

Le nouveau test 2×2 doit établir simultanément : H proche/lointain
distinct depuis le départ par `range_left` ; G gauche/droite invisible
depuis ce même départ à H constant ; H non distinguable localement par
`front/left/right` aux trois positions de décision G ; et G discriminable
à l'approche et aux deux ouvertures, quelle que soit la valeur de H.
Tolérance d'égalité **0,035 m**, contraste **strictement supérieur à
0,35 m**. Un échec garde la campagne native rouge et archive les
valeurs brutes plutôt que de modifier une assertion.

**Ce test est strictement une expérimentation par poses Supervisor et
télémètres d'origine**, pas un vol motorisé sur H loin ni un test de
l'impossibilité d'un retour pour relire H. Les vols moteur existants ne
qualifient que H proche ; il manque toujours un vrai projet élève
Blockly `.wbb` identique sur les quatre mondes, le test des solutions
sans variable, le contact/atterrissage et l'acceptation personnelle
4e/3e. L'alias local à trois rayons ne prouve pas l'alias global de
toutes les stratégies motorisées possibles.


## H×G private motor cross-validation (unqualified until native results)

The four physical 2×2 scenes passed the isolated native Multi-ranger
sensor matrix on `346ae789`, but **H-far flights were not yet proven**.
The next private R2025a Chrome/Robot Window witness uses *one identical
JavaScript pilot* in all four worlds: read H once from the real left
sensor after takeoff (destination = left/right), travel the shared
approach, read G again (opening = left/right), follow the physically
correct opening, and turn toward the H-indicated checkered pad.
A scene identity is used only to select the private fixture;
**the route and destination must come from the two actual range returns**.

All four flights must obtain native MOVE/TAKEOFF/TURN/LAND acknowledgments,
independent physical Floor contact at the correct H destination and all
seven authentic Solid contacts/swept intersections checked at every
32-ms step. The old blind-right negative remains mandatory. A second CI-only adversary
on H-far/G-left deliberately ignores the genuine initial H reading and
selects the left damier; independent native Floor contact must certify this
as the **wrong pad** and fail terminally, without any positive LAND verdict.
This refutes only a simple blind destination strategy. The native
`premature_floor_contact` is mission failure even when the normal
`LAND` primitive returns an ACK and the private JS script finishes
successfully. The CI counterexample requires the *real* wrong-pad Floor
contact, the irrevocable native failure and absence of any independent
successful native pad marker; a `LAND` ACK is never a mission oracle.
It does **not** rule out late re-reading or control-flow branching
without a variable.
The native-only A/B feeder regression remains mandatory; no physical product,
public activity starter, safety threshold or Grand Prix A8 is changed.
A green run proves feasibility of this private JS *only*, not a
student-editable Blockly `.wbb`, a reactive loop, a mission oracle,
a memory requirement or a 4e/3e PASS. Re-reading H by an accessible
detour and duplicating branches remain adversaries to test explicitly.

## Private genuine Blockly 13 model witness — not the pupil mission

The experimental job runs `tools/ci/build_a5_private_blockly_witness.js`
using the actual project's Blockly 13.2.1, semantic AST compiler, activity
preflight, interpreter and canonical `.wbb` serializer. It constructs the
same **single private project** for all four combinations, with a bounded
`while` loop repeatedly measuring `front` during approach, and one
variable storing the starting H-distance. The late G choice always reads
`left` afresh. The canonical serialization must be reloaded and reproduce
the identical checked AST; without conditional-loop backend capability,
execution must refuse **before takeoff**. The emitted `.wbb` and
`summary.json` are private CI artifacts, not activity starters.

**The four Node model checks in this stage use a DETERMINISTIC VIRTUAL
SENSOR/MOTION MODEL**, deliberately labelled `native_2x2_from_this_wbb:false`.
They establish expressibility and Save/Open serialization within Node, not
genuine Webots R2025a collisions, real Robot Window, native scene
selection, native oracle verdicts, Chrome or OS Save/Open dialogs. The
historical `progression-reactive-v1` profile remains hidden, still
describes a warehouse mission, and cannot be treated as the new A5.
The original H×G motor sensor evidence remains an **independent** chain.

### Separate native Webots R2025a experiment for these exact .wbb bytes

The same Draft workflow additionally serves the **canonical private .wbb
bytes** over a single fixed loopback-only endpoint and reopens them inside
the original Webots Robot Window. A private browser module uses the genuine
Blockly 13.2.1 AST interpreter and authentic Webots WWI backend. Four worlds
are launched using only the pre-existing CI-only native scene selector;
the student's AST receives **neither** the variant ID, evaluator answer,
Supervisor pose nor source WBO. The browser reports measured sensor events
for diagnostics, while the independent C monitor is the only authority
for physical 32-ms step continuity, seven collider/swept streams and
physical Floor landing. The Python runner refuses a false success unless
all source SHA, fresh front-loop readings, two real left measurements,
correct physical pad, and native-land conditions agree.

**A passing Node model test is not proof of this native experiment.**
The native four-world CI step is required to reach
`WEBEEBLOCKS_A5_PRIVATE_FOUR_REAL_WBB_NATIVE_PASS`; any failure
remains a physical or integration falsification, not permission to change
the oracle or skip a variant. Even a later Webots PASS would not establish
the intended activity 5's repeated L-corner-following world, the need
for a particular AST syntax, an OS Save/Open dialog, a public pupil
profile, the alternative return/backtracking strategy, or a teacher
acceptance.

Changing L-length/direction, return/backtracking adversary and teacher
usability remain unproven until tested directly. No AST syntax is imposed as a
condition of future mission success.

## Native R2025a falsification checkpoints, in order

1. Embed each WBO in an isolated original-Crazyflie Webots R2025a world and
   attest its real Solids and bounding boxes. Keep H and pads byte-identical.
2. From the identical start (0,0,z≈0.50), require equal front/left sensor
   observations across both G variants and a valid initial H reading. Refuse
   a gate already visible or a missing/nonfinite native sensor.
3. Near x≈2.50,y=0, require a real **left** range difference (G-right physical
   arm versus G-left boundary), then compare the front rays from positions
   (2.50,+0.80) and (2.50,-0.80). A G-fixed blind choice must fail at one gate.
4. Drive actual PID paths through both apertures, with native continuous
   contact/swept-geometry evidence, correct Floor landing and negative oracles.
   Test out-of-corridor, high-flight bypass, no sensing and return/backtracking.
5. Only after the H-fixed/G-variable native pair passes, design an H-near/H-far
   pair with G fixed, then compose the **four variants** H×G. Compare strategies
   with stored state, branch duplication, late clue re-reading and return.
   Build and reopen a single actual **Blockly** .wbb across all variants.

**Scientific limitation:** with finitely many variants, control-flow branching
can carry a remembered choice without a variable; functional usefulness means
reducing duplication and sharing a reactive loop, not universal necessity
of a specific AST block. The native tests and the teacher's 4e/3e acceptance
remain separate. This Draft changes no activity 8 world, oracle, performance,
physical firmware, or classroom published starter.
