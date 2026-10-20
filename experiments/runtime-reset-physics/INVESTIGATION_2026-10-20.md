# RESET_TIMEOUT #637 — verified native controls, 20 October 2026

**Historical cause UNKNOWN. No production correction is justified. Main health
NOT restored. These observations do not close #637 or release ordinary merges.**

Main reconstructed at a64ec6015aeba33ed2b761e49b4bf8f50d1a05a7. Contract/vision/
roadmap blobs c1b0078103507e7b0132af948b34a5cbd7b5950a,
df0b3b8591562f13f879db5c3f5ab78286b84cde,
e8c4e246df15f223728f94743c958374176fccac are unchanged. #639/#642/#648/#649/
#650/#651/#652/#653 are integrated. #653 source Ready HEAD 635343ebc9f715c3deff894889d6309c84acac9f
has canonical CI 39385917836 / Gate 118524872806 success and owner independent
GO 5591095870. Its squash a64ec6 is current main. This is diagnostic acceptance,
not RESET remediation. No independent GO is provided for code created here.

## Observed, with original browser/internal controllers and business oracles

| Acquisition | Browser actually measured | New strict RESETs | Native samples | Compared post-transient samples |
| --- | --- | ---: | ---: | ---: |
| Buffered self reads, run 39489946433 | 155.0.8059.84 | 14 | 25,767 | 139 |
| ODE control, run 39491731307 | 156.0.8078.47 | 14 | 35,242 | 141 |
| Fixed eight-process cohort, run 39492689767 | 156.0.8078.47 | 112 | 227,549 | 1,132 |
| Exact earlier155 bytes with ODE, run 39493737597 | 155.0.8059.84 | 14 | 26,030 | 141 |

All eleven new acquisitions completed the original fourteen RESETs and complete
positive/negative/freshness mission assertions; all 154 RESETs succeeded.
314,588 native physical states were retained; 1,553 comparisons at elapsed
>=64 ms show no persistent native/predicate disagreement. The cohort's longest
RESET is 384 ms; its latest false sample is +96 ms. The original 5 s / 250 ms,
32 ms, seed/thread=1 and 1500 host-second budget remain intact.

Raw artifact bindings:
- 12296001306, 39489946433, SHA-256
  2191cafcbfbe173dde51fe78dbee7a9aa3a64e8d1f5594618c6066737523fc10,
  7,128,152 bytes; 21-file manifest.
- 12296940061, 39491731307, SHA-256
  7d54f54afb4eded306df3c9a0cbfff95e8d26f9c3eaa14aec7ecd990dc74cb0a,
  24,120,751 bytes; 26-file manifest.
- All eight cohort IDs, ZIP digests, lengths, 27-file manifests, actual receipt
  states and results are in COHORT_RESULTS.json.
- 12297455612, 39493737597, SHA-256
  6b25b78afba73ae5485824ecae3535c6ad91793c51216f58458e820e792ff80c,
  19,116,428 bytes; 31-file manifest; PIN155_RESULTS.json.

ZIP digests/CRC, every manifested byte, original/instrumented C, buffered header,
plugin source, predicate/window recalculation and native/consumed comparisons
were verified after download. The first incomplete local buffer ZIP was rejected
before use; the complete distinct transfer matched the published digest. Raw
GitHub artifacts retain all cases; native and consumed records remain primary.
The portable verifier was executed on cohort case1 and the pinned155 case;
an adversarial wrong ZIP digest was refused. Cohort totals were independently
recomputed from the raw phase logs, not only copied from their summaries.

## Refuted only within the measured scope

These controls refute a universally broken RESET, a teleport GPS spike being
sufficient by itself, or a universal need for the extra synchronized observer
or added Runtime Supervisor queries to make these programs reset successfully.
They do not refute stochastic measurement effects, rare physical states or
persistent sensor incoherence in a different, genuinely failing trajectory.

The pinned155 control closes the version-confounding gap for this finite
measurement arrangement: that same earlier successful-control binary also
completes without extra Runtime queries. It is NOT the unknown historical
browser. The unpinned original download actually changed155 to156 during this
investigation; strata must remain distinct.

The earlier 600-rad/s prepared actuator fixture remains a demonstrated
synthetic mechanism, not an attribution of the historical failure. Its archived
negative and zero/motor-restoration controls were reverified. Clearing GPS
history or restoring motors is therefore not proposed as a proven #637 repair.

## Still open and indispensable missing evidence

The original 39226828934 / main 8b12e52 / artifact 12176914426 really contains
collision7 -> UNSAFE_OR_TIMEOUT -> RESET_TIMEOUT. Verified original ZIP SHA-256
de662a7420022fd139bdd09d45e702a3dddb606eef949a3af33f9cdcb25702ec.
It has no native/consumed five-second trajectory, solver/actuator state, precise
delivery timeline, measured CPU/load or actual Chrome identity. These cannot be
reconstructed from the collision contact coordinates or later successful runs.

Remaining branches: rare ODE/contact/actuator state or genuine motion/pose
deviation; rare consumed-data inconsistency; delivery/read-order/scheduling
interaction. No measured failing trajectory selects the responsible layer.
Producing a causal patch now would be speculation. None of the 11 new runs
contains the required five-second mechanism. The predeclared cohort ends at
eight; it is not automatically extended to search for green.

## Separate scheduled-main failure

39394857242 / main 4ff57f7 has core 118535743017 success but reset-replay job
118535818097 failure. Verified artifact12251657272 SHA-256
f49ecab079474f37c05bd755c3f9a7bcf2c4e33d700306acdcdb9ffa68a987a6:
three RESET OK, first negative complete, last replay still running when its
150 HOST-second process budget expires (exit124). UNSAFE_REPLAY_DONE is absent.
There is no native RESET_TIMEOUT in that dataset. This is an incomplete oracle,
never a PASS and never a second reproduction of #637.

## Concrete next acquisition and offline analysis

A new genuine refusal, not another green control, is indispensable. The capture
path is implemented, not an abstract request for instrumentation:
from a fresh isolated checkout of acquisition commit
4e28216f20db08ebb708fd9ca7211a969a9a9f6d, run
`bash tools/prepare_runtime_v2.sh`, then
`python3 experiments/runtime-reset-physics/pin155.py`.
This selects the exact known155 bytes (or stops at preparation refusal), uses
the ordinary internal browser program and preserves the complete
`ci-artifacts/progression-autonomous-mission` on its first refusal.
It is not a reconstruction of missing historical conditions, and no identical
new campaign is mandated by these successful results.

For an actually failing case, retain the entire directory immediately, before
any invocation that recreates it. Compare the full RESET trajectory after the
teleport-crossing sample: native pose/orientation/six velocities and contacts,
cached consumed GPS/IMU/gyro, targets, predicates and stable_since, actual
protocol response and receipt. Agreement of prolonged false predicates with
native deviation selects physics; disagreement selects observations/freshness.

For already retained cohort case1, on a checkout containing verify_archive.py,
download the ORIGINAL ZIP (not a repacked directory):
`gh api repos/djibian/webeeblocks/actions/artifacts/12297090035/zip > case1.zip`
then run:
`python3 experiments/runtime-reset-physics/verify_archive.py --zip case1.zip --sha256 2c30e6e55e4513a45952be2ceee7f367aa00e3e12cfc5d1c72451c6602a9c764 --head 6e219066f3387572c7fd2c09c5538c1ad8ee73a2 --run 39492689767 --artifact 12297090035 --trial 1 --output verified-case1`.
The output directory must be new. Exact metadata for each other cohort case is
in COHORT_RESULTS.json.

ODE contact candidates are geometric observations, including possible same-body
pairs, not a force-contact oracle; joint count alone does not prove freedom.
Their coordinates are not the body centre. Engine milliseconds/state time,
cached sensor sampling phase, actual ACK and motor target/current distinctions
remain explicit. Instrumentation can affect scheduling. No full-product,
pedagogical or flight acceptance follows. No TEST_REQUIRED is requested.
