# Direct engine actuator observation — #637

Preregistered before acquisition, on main a64ec6015aeba33ed2b761e49b4bf8f50d1a05a7.
This is an experiment, not production instrumentation or a repair candidate.

H1: after an ordinary autonomous collision, residual *current* motor speeds and
the resulting propeller forces persist through body RESET and prevent its
unchanged 250 ms physical stability window within five simulated seconds.
The 600 rad/s fixture proves possibility, not the representative domain.

Exactly ONE complete original internal-controller/RobotWindow/browser autonomous
acquisition is allowed, with original positive, collision-negative and freshness
oracles, 14 RESETs, 32 ms, seed/thread=1 and 1500 host-second budget. No trajectory,
request delay, threshold, acceptance rule or production actuator operation changes.
Stop on first preparation/measurement/oracle failure or completion; retain every
started output and do not replace or extend the acquisition.

The physics plugin reads native ODE pose/velocity/contact candidates and cached
pointers to the four WbMotor and WbPropeller objects. It reads currentVelocity,
currentThrust and currentTorque directly, unlike the controller's cached target
getters. Object identity is checked by native RTTI, unique device name and four
distinct node IDs. Exact R2025a headers and binary are required; compiled accessor
offsets must agree with the shipped binary's disassembly before launch.
No binary patch, debugger, actuator setter, body setter or extra Supervisor query.
Collision callback always returns 0. Contacts remain candidates, not measured
forces. Existing buffered cached Runtime samples/predicates are reused.

Confirming observation: real RESET_TIMEOUT, continued native motion/pose error,
nonzero measured propeller forces with zero targets, and a subsequent paired
actuator-only intervention eliminating that mechanism from equivalent conditions.
That intervention requires a separately fixed protocol after inspecting the
failure. A success of B without a failed A establishes no causal repair.

Refuting observation: a real timeout with current velocity/thrust/torque already
zero and native/consumed post-reset trajectories showing another mechanism.
If this run succeeds, quantify the directly measured actuator domain, including
collision 7 and RESET delivery. This is a finite control, neither universal
refutation of H1 nor evidence that historical #637 is cured. Do not launch an
identical second acquisition or infer an unobserved historical motor state.

Local platform: official Linux R2025a release tar, exact source/assets c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b,
verified known Chrome155 deb/executable, local Xvfb/software rendering. Native
adapter retains the original runner's business oracles verbatim. Ubuntu24 and
Node24 differ from canonical Docker/Ubuntu22/Node22; this is not CI Gate evidence.
Header reads and plugin logging may affect scheduling; that limit survives a PASS.

No production correction follows without a relevant failed reference and causal
intervention. Preserve #637 open, 5 s/250 ms, negative oracles and fail-closed.
