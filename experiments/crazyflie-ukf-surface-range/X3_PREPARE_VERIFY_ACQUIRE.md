# X3 reproducible prepare -> verify -> acquire handoff

This document is the outer physical handoff for the `x3-independent-props-off`
characterization. It repairs the preparation gap identified in #533 without
changing the scientific experiment in `X3_CHARACTERIZATION_PROCEDURE.md`.

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
- props removed throughout preparation and acquisition.

No other parameter is part of this reconstruction. In particular, the
preparation helper does not persist parameters, pulse an estimator reset, tune a
threshold, change `rangeUp`, modify Runtime/controller behavior, arm, invoke a
commander or run motors.

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
required value that differs, and performs a fresh read-back of every required
value.

There is no automatic retry. A flash, connection, missing-parameter, type,
write-acknowledgement or read-back failure yields `INCOMPLETE`; do not acquire
from that result.

The output directory is append-only for this attempt and contains
`preparation-start.json` plus `preparation.json`. A valid result has
`status = "PREPARED"` and binds:

- the exact bundle repository SHA;
- the exact firmware digest and STM32 flash target;
- the Crazyradio URI;
- the exact cflib runtime identity;
- every required parameter type/value;
- observed values before and after reconstruction;
- the exact set of parameters actually written;
- absence of persistence/reset/arming/commander/motor/scientific-retry effects.

Do not power-cycle the Crazyflie after `PREPARED` and before the corresponding
read-only acquisition.

## 3. Verify

The acquisition runner independently validates `preparation.json` against the
exact current bundle before it connects to the Crazyflie. The record must match
the same URI, firmware digest, bundle provenance, preparation-script digest,
runtime identity and parameter contract.

The collector then performs a second independent live gate: it reads the four
required values from the Crazyflie and refuses capture on a mismatch. Neither
the capture runner nor `capture_independent_inputs.py` flashes firmware or
writes parameters.

The low-level collector retains its historical `--installed-bin-confirmed`
argument, but that is no longer an operator-memory assertion in the trusted
handoff. Only `run_x3_independent_capture.sh` supplies it, after mechanically
verifying the exact preparation record and bundled firmware. Directly supplying
that low-level flag is not a substitute for the preparation gate.

A valid preparation record is therefore necessary but not sufficient for a
capture: both the retained preparation evidence and the collector's live
verification must succeed.

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

On a successful capture the runner copies the verified preparation record and
its SHA-256 into the capture directory so the hardware reconstruction evidence
travels with the raw acquisition evidence.

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

## 5. Existing #532 evidence

Captures already retained under #532 are not deleted or silently replaced.
Their admissibility under this repaired preparation/provenance contract must be
decided mechanically and outcome-independently from retained preparation facts,
not from detector performance.

The currently open #532 request remains bound to its original exact artifact
and procedure. This repair does not mutate that authority and does not create a
second simultaneous human request. If a future physical request uses this
repaired executable handoff, it must be issued through the normal exact-SHA
checkpoint mechanism only after #532 has been resolved according to the V5
contract.

Refs: #533, #532, #251, #70, `X3_CHARACTERIZATION_PROCEDURE.md`,
`X3_CHARACTERIZATION_PREREGISTRATION.md`.
