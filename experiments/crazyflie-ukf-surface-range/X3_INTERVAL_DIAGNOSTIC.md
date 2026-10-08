# Bounded X3 interval diagnostic

This implements observation preparation for the missing interval exposed by
#561. It creates no physical request, acceptance or scientific trial. The
historical #561 FAIL is unchanged; no initiating cause is inferred. A later
human-owned diagnostic requires its own independently reviewed exact bundle,
explicit procedure and trusted checkpoint. An open TEST_REQUIRED is not a queue
slot for a second request.

Keep all four propellers removed throughout. Preserve the exact #251 binary,
four X3 values, single fresh preparation reset, fixed settle and current health
bounds. The diagnostic never flashes, writes configuration, resets, arms,
invokes Commander, starts Webots or retries an ambiguous operation. It consumes
one applicable PREPARED record and performs the existing #567 read-only health
gate with its exclusive raw `.health` sidecar before its observation connection.
That initial gate/setup gap remains unobserved. Scientific capture, trial order,
all-trial retention, metric/time reference and acceptance criteria are unchanged.

## Frozen contrasts

| Mode | Sequence after all four streams become ready | Observation limit |
| --- | --- | --- |
| `handling-connected` | Stationary before 10 s; one independently witnessed handling interval 10 s; stationary after 10 s, on one unchanged live connection | Tests handling with a continuous connection; never claims disconnected behavior |
| `reconnect-stationary` | Stationary 10 s; stop logs and close; wait 5 s; open one new connection and observe stationary 10 s | Keep vehicle/surface geometry unchanged; no raw measurements exist while logs are stopped or during connection setup |

No sequence restarts preparation or estimator state between phases/epochs. If
one contrast fails, stop and retain that outcome; do not continue to the other
contrast or repeat it automatically. Running the other contrast requires its
own explicit human procedure and applicable preparation. Preserve every started
record, favorable or unfavorable, without choosing scientific replacement trials.

The four original streams and periods are unchanged: barometer 20 ms, IMU 10 ms,
pose 20 ms and detector 20 ms. Each epoch uses the production Recorder, retaining
startup and invalid rows, device timestamps and host receipt times. Read all four
frozen parameters freshly, with exact types, on each connection before logging.
Missing/malformed/non-finite values, duplicate/backward timestamps, more than
five nominal periods between samples, a stream silent for more than 1 s,
connection/log error, parameter mismatch, interruption or teardown uncertainty
stops the diagnostic. Connection/download and stream-start deadlines remain
30 s / 5 s. Apply unchanged broad health bounds to every retained pose row;
out-of-bound data are written before rejection. No bound is tuned from #561.

## Geometry and phase evidence

Before an explicitly authorized diagnostic, fix the intended vehicle and surface
coordinates using the independent measured-guide/time-witness contract. Supply
a UTF-8 JSON **plan** with exactly these fields (metres):

```json
{
  "mode": "reconnect-stationary",
  "method": "measured guide; separate video/metric-time witness retained",
  "vehicle_z_before_m": 0.60,
  "vehicle_z_after_m": 0.60,
  "surface_z_before_m": 0.0,
  "surface_z_after_m": 0.0,
  "uncertainty_m": 0.005
}
```

The numbers above are only a shape example, not measured evidence. Use actual
planned guide coordinates and declared positive witness uncertainty. For the
reconnection contrast both declared coordinates must be unchanged. Independently
retain the **actual** geometry/time witness across all stationary/handling
intervals; the plan alone cannot establish what physically happened. Preserve
any deviation rather than editing the plan or resynchronizing favorable samples.
The existing independent-reference rules apply to any later metric/scientific
analysis. Missing witness or ambiguous timing makes a causal/metric claim
UNPROVEN even if the raw collection completed.

Events mark the host schedule: `phase-start/end`, connection open/close and log
start/readiness/stop. They do not measure motion onset or surface geometry. Each
stream's first/last retained row defines its coverage; logs-ready does not extend
coverage backward. All log-stop/setup/disconnected intervals remain explicit
coverage gaps with no interpolation. Separate per-epoch CSVs never fuse device
clock coordinates across a reconnect.

## Packaged path and retained output

First use `bash run_x3_interval_diagnostic.sh --verify-environment`; it exercises
the existing exact offline five-wheel runtime and the actual diagnostic help
import without touching hardware or package bytes. Only an independently
requested procedure may then invoke:

```bash
bash run_x3_interval_diagnostic.sh \
  --uri <exact-radio-URI> --checkpoint-url <exact-TEST_REQUIRED-URL> \
  --request-sha <exact-bundle-SHA> --mode <explicit-contrast> \
  --preparation-record <applicable-preparation.json> \
  --geometry <frozen-geometry-plan.json> --output <new-outside-directory> \
  --props-removed
```

Manifest, exact preparation/source/URI binding, geometry plan and new output
paths are checked before hardware. Existing output is never overwritten. The
wrapper verifies/installs only local locked wheels, uses the pinned bundled
cflib and performs no network operation. Bundle provenance binds its source,
scripts, firmware and support; reported installation metadata is not remote
binary attestation.

Retain both `<output>.health` and `<output>`. The latter includes byte-identical
preparation/geometry plan and digests, start/result, exclusive per-event JSON,
fresh raw/type parameter readbacks and one directory of the four raw CSVs per
epoch. Failed/incomplete sequences retain everything already written, including
health failures, the first stream defect, causal exceptions and teardown errors.
Cleanup-event storage is independent of log/transport/file cleanup. Raw callbacks
and their health decisions are sealed together before teardown; every raw stream
close and transport close is attempted once even if another fails. Primary and
cleanup causes remain together in INCOMPLETE. If final result storage fails,
the terminal reports those causes plus storage uncertainty without retry;
no result file or successful close is inferred.
`OBSERVED` means only the frozen raw sequence completed. `INCOMPLETE` remains a
failure. Neither means scientific PASS, health beyond measured coverage,
causality, physical qualification or flight authority.
