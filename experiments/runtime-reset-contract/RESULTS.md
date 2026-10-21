# Bounded RESET contract result — 21 October 2026

**Verdict: INDETERMINATE concerning a WebeeBlocks defect; the observed Webots
motor persistence conforms to the public contract. No production correction,
historical attribution, #637 closure or restored main health.**

Main revalidated as b478f9dd1854d83345abe13ed20fcf7baeffaca5. V5/vision/roadmap
blobs c1b0078103507e7b0132af948b34a5cbd7b5950a /
df0b3b8591562f13f879db5c3f5ab78286b84cde /
e8c4e246df15f223728f94743c958374176fccac remain unchanged.
See SOURCE_CONTRACT.md for the exact API/engine/ODE audit and its consequences.

## New offline information from previously acquired real data

Reverified original artifact12303527298 with its exact verifier at evidence
0ec829ea60754bebc779100f4d9e3a057b5b03d1: complete ZIP/CRC,35 manifested files,
original/instrumented sources, world transform, native ABI, original business
oracles,14 strict RESETs and141 post-transient comparisons. This was an offline
verification, NOT a new native campaign.

PRIOR_POST_ACK.json now records all14 observed ACK/current/extinction/next-target
intervals. Largest residual at an ACK:34.37361302687335 rad/s and0.18894913441621902 N
(38.5% of model weight). For RESET246: receipt357.472 s, ACK357.792 s,
extinction358.944 s, first subsequently observed nonzero target359.584 s.
After the collision RESET299: ACK533.216 s, extinction533.600 s,
next nonzero target535.648 s. The receipt/ACK distinction is retained.

All13 observable later motor activations occur after actual extinction; after
the final fourteenth ACK there is no further activation in the archive. Thus
these controls do NOT test immediate post-ACK motor activation. This was a
real evidence gap rather than a reason to repeat the full autonomous cohort.
The accompanying labelled post-ACK raw subsets preserve the used native/current
and consumed/target intervals, not the entire original autonomous trajectory.

## Preregistered minimal public-API experiment, then stop

The source at b78d5f1dd525fc5b0590ff16541188c719b68485 fixes the hypothesis,
selected measured vector, four fresh cases, predictions, criteria and stop rule.
Actual production C/PID/activity_scene code is included unchanged; wrappers
provide input/observations/preparation only. Dedicated minimal stock Crazyflie
world and public API motor save/loadState; no ODE mutation or private ABI.
Its prepared motor current is source-derived, NOT a new direct current read.
Full historical collision, browser and negative/evaluator oracles are not
claimed to be recreated by this minimal fixture.

| Case actually started | Original production RESET | Retained post-ACK observation | Evidence result |
| --- | --- | --- | --- |
| A-idle, body reset plus sham motor save | ACK +256 ms | 50 samples, through+1.600 s; no predicate violation | Native exit0, final COMPLETE stdout witness absent; original harvester completed=false preserved |
| B-idle, same reset plus motor-node load | ACK +448 ms | 49 samples, through+1.568 s; no predicate violation | Separate journal COMPLETE at+1.600 s, but final stdout sample absent; original harvester refuses truncated coast |
| A-takeoff | NOT EXECUTED | No evidence | Immediate next-command question remains UNPROVEN |
| B-takeoff | NOT EXECUTED | No evidence | No claim that B repairs anything |

First run39561830185 on b78d5f1, attempt1 failure; artifact12328027041.
ZIP16,459 bytes, SHA256759cd7b53ad89b7ac5af7c092576f610cb5d1aae1bd6ce10a567bb7cd221ce29.
It correctly stopped the first series. A diagnosis-preserving amendment
528c5d93c6e41ede12a764f3722c5dad3b8a113b added a separate closed event journal
and permitted ONLY the three never-started cases, never a replacement of A.
Run39562357936, attempt1 failure, artifact12328670868: ZIP14,838 bytes,
SHA2561fa91ff1aac6b999d9a28656766f90b5513e8104dcb8bbfcc3fcb83a95f26d88.
It stopped at B-idle as specified. Both ZIPs/CRC/membership and eight manifest
members per ZIP were independently downloaded and verified.

The new journal identifies B's COMPLETE at6.304 s, while the last retained
stdout sample is6.272 s (ACK4.704 s). This is a32 ms missing measurement,
NOT a floating-point boundary issue, not a RESET_TIMEOUT and not a fabricated
sample. A's absent final event and B's absent final sample are consistent with
loss at the controller stdout/Webots shutdown relay. That mechanism is an
inference; the two missing witnesses themselves are directly established.
Both original workflow failures remain failures. No missing data is filled,
no budget/predicate is weakened, and no native process is repeated or added.

The asymmetric retained idle data support compatibility over their observed
windows. B does not improve the observed RESET latency; clearing motor state
cannot simply be presumed to improve settling. These observations do not prove
a universal invariant, a causal cure, equivalence of complete contact state,
or immediate takeoff safety. Both immediate cases remain unexecuted. Replaying
the harvester offline cannot manufacture those physical results.

## Decision and eligible work boundary

There is no demonstrated violation of the current explicit ACK conditions,
no Webots/ODE bug, and no relevant failed-A/successful-B historical repair.
The motor-only operation resets more than currentVelocity and must not be
introduced speculatively. No production file, threshold, five-second limit,
250 ms window, negative oracle or fail-closed behavior changes.

Ordinary integrations remain suspended under existing #637 evidence; no
independent GO or canonical CI Gate is asserted for this experimental branch.
#654's independently reviewed host-budget/provenance repair remains distinct
from #637 and does not establish a separately tested squash/main. The open
ordinary Grand Prix candidates do not justify a normal merge while this
health condition remains. Endpoint pedagogy and physical flight are unchanged.

Stop native experiments here. The finite experiment did not resolve the
immediate-command gap; no further identical cohort or automatic retry follows.
A future deliberately justified investigation may address that exact missing
question with reliable full physical logging; it must preserve these partial
subjects and cannot count an unexecuted case as PASS. Historical attribution
still requires actual failing native evidence or an independently causal
mechanism linking an intervention to the historical refusal.

Results are archived on a separate evidence branch; no production PR or
self-authored GO is created. No TEST_REQUIRED or hardware action.
