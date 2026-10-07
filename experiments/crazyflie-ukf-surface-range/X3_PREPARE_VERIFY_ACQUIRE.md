# X3 reproducible prepare -> verify -> acquire handoff

This document is the outer physical handoff for the `x3-independent-props-off`
characterization. It incorporates the reproducible preparation repair from #533
and the fresh-reset repair from #551 after the owner-authoritative #550 FAIL,
without changing the scientific experiment in `X3_CHARACTERIZATION_PROCEDURE.md`.

The sequence is strictly:

`prepare -> verify -> acquire`

Preparation is an effectful, props-off setup phase. Acquisition remains
read-only with respect to firmware and parameters.

## 1. Fixed state to reconstruct

The preparation phase reconstructs only the state already proven and frozen by
checkpoint #251:

- bundled `cf2.bin` SHA-256
  `67d71f2fc74c06001bb141ed6206b0d06df23497a48f498531c3aba192f0b738`;
- `stabilizer.estimator` as `uint8_t` value `3`;
- `ukf.qualityGateTof` as `float` value `20.0`;
- `ukf.baroNoise` as `float` value `6.25`;
- `ukf.surfaceOffsetS3` as `uint8_t` value `1`;
- one fresh `ukf.resetEstimation` `uint8_t` request: write `1`, require a
  fresh observation of the pinned firmware consuming the request and auto-clearing
  it to `0` within 0.25 s, then retain the historical explicit client write of
  `0` after the 0.25 s client delay;
- a fixed 5 s stationary post-reset settle followed by a broad fail-closed
  estimator-health observation;
- props removed throughout preparation and acquisition.

No other parameter is part of this reconstruction. The reset is state
initialization, not tuning: the preparation helper does not persist parameters,
search thresholds, change `rangeUp`, modify Runtime/controller behavior, arm,
invoke a commander or run motors.

## 2. Prepare

Keep all four propellers removed. Do not start a characterization capture yet.

First verify the packaged preparation environment:

```bash
./prepare_x3_independent_capture.sh --verify-environment
```

Then run one preparation against the exact Crazyradio URI that will be used for
acquisition:

```bash
./prepare_x3_independent_capture.sh \
  --uri radio://0/80/2M/E7E7E7E7E7 \
  --output /path/to/x3-preparation-001 \
  --props-removed
```

The preparation helper always installs the exact bundled STM32 `cf2.bin`. This
removes dependence on an unknown prior firmware state instead of asking the
operator to remember which binary was previously installed. It then inspects
the live parameter TOC, requires the exact parameter types above, writes only a
required frozen value that differs, and performs a fresh read-back of every
required value. It then requires `ukf.resetEstimation` to be writable
`uint8_t`, writes `1`, and requires a bounded fresh read to observe the
firmware-owned auto-clear to `0` before the client can manufacture that
postcondition. The helper preserves the retained procedure's explicit client
`0` write after the 0.25 s client delay, verifies the final `0`, waits the
fixed 5 s stationary settle, and checks these broad predeclared
gross-sanity bounds: `roll/pitch in [-45,+45] deg`, `stateEstimate.z in
[-1,+5] m`, and `stateEstimate.vz in [-1,+1] m/s`, with at least 10 finite
samples over a fixed 2 s / 100 ms observation. These are intentionally much
wider than the retained healthy #251 stationary evidence; they reject an
already-divergent estimator but are not scientific acceptance thresholds.

There is no automatic retry. A flash, connection, missing-parameter, type,
write/reset acknowledgement, reset final-state, health-observation or read-back
failure yields `INCOMPLETE`; do not acquire from that result.

The output directory is append-only for this attempt and contains
`preparation-start.json` plus `preparation.json`. A valid result has
`status = "PREPARED"` and binds:

- the exact bundle repository SHA;
- the exact firmware digest and STM32 flash target;
- the Crazyradio URI;
- the exact cflib runtime identity;
- every required parameter type/value;
- observed values before and after reconstruction;
- the exact set of frozen parameters actually written;
- the exact reset parameter/type, acknowledged client request `1`, bounded
  firmware-owned auto-clear observation to `0`, historical 0.25 s client
  release delay, explicit client `0` release and final read-back;
- the fixed post-reset settle and broad estimator-health evidence;
- absence of persistence/arming/commander/motor/scientific-retry effects.

Do not power-cycle the Crazyflie after `PREPARED` and before the corresponding
read-only acquisition.

## 3. Verify

The acquisition runner independently validates `preparation.json` against the
exact current bundle before it connects to the Crazyflie. The record must match
the same URI, firmware digest, bundle provenance, preparation-script digest,
runtime identity and parameter contract.

After validating the preparation record, the acquisition runner performs a
fresh **read-only live estimator-health gate** using the same broad predeclared
bounds and the dedicated no-Commander transport teardown. This catches a later
divergence before the scientific collector starts without emitting cflib's normal
close-time safety-zero setpoint.
The collector then performs another independent live gate by reading the four
required frozen values and refusing capture on a mismatch, and it uses the same
no-Commander teardown. Neither the capture runner nor
`capture_independent_inputs.py` flashes firmware, pulses reset, writes
parameters or emits a Commander/setpoint packet.

The low-level collector retains its historical `--installed-bin-confirmed`
argument, but that is no longer an operator-memory assertion in the trusted
handoff. Only `run_x3_independent_capture.sh` supplies it, after mechanically
verifying the exact preparation record and bundled firmware. Directly supplying
that low-level flag is not a substitute for the preparation gate.

A valid preparation record is therefore necessary but not sufficient for a
capture: the retained fresh-reset preparation evidence, the runner's live
read-only health gate and the collector's live parameter verification must all
succeed.

## 4. Acquire

Use the same URI and pass the retained preparation record:

```bash
./run_x3_independent_capture.sh \
  --uri radio://0/80/2M/E7E7E7E7E7 \
  --checkpoint-url https://github.com/djibian/webeeblocks/issues/<N> \
  --request-sha <exact-request-sha> \
  --seconds <30..300> \
  --output /path/to/new-capture-directory \
  --preparation-record /path/to/x3-preparation-001/preparation.json \
  --props-removed
```

Whenever the collector has created its capture directory, the runner copies the
verified preparation record and its SHA-256 beside the retained raw evidence,
including an incomplete capture. The collector's nonzero exit remains nonzero;
retaining its preparation binding does not make it a successful capture. No
capture directory is manufactured if admission or the pre-acquisition health
gate prevents collection from starting. Always use a new output directory.

After preparation, all scientific collection rules remain exactly those in
`X3_CHARACTERIZATION_PROCEDURE.md`:

1. three primary cycles;
2. fixed scenario order in every cycle:
   `stationary -> terrain -> vertical -> mixed`;
3. retain every validly started capture, including unfavorable or procedurally
   invalid results;
4. use only the predeclared procedure-defect replacement rule and the existing
   five-start cap;
5. retain the independent apparatus, clock, guide, uncertainty, witness,
   continuous-hold and trial-ledger evidence required by that procedure.

Preparation success is not a scientific result and cannot produce `PASS`,
`FAIL`, `GO`, a classifier claim or a flight authorization.

## 5. Failed #550 evidence

The #550 request is closed owner-authoritative `FAIL`. Its started stationary
and terrain captures remain historical failure evidence and are not deleted,
silently replaced or counted as successful characterization slots. They exposed
that the no-reset preparation could leave UKF grossly divergent before terrain
motion began.

A future physical request using this repaired handoff must be issued through the
normal exact-SHA checkpoint mechanism with a new artifact/fingerprint. #550 is
never reused as authority for the repaired procedure.

Refs: #551, #550, #533, #251, #236, #70,
`X3_CHARACTERIZATION_PROCEDURE.md`,
`X3_CHARACTERIZATION_PREREGISTRATION.md`.
