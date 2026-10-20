# #637 — preregistered unchanged-browser variability experiment

This is a non-integrating experiment branch, based on exact #653
635343ebc9f715c3deff894889d6309c84acac9f, not a production repair or CI Gate.
That source candidate's canonical pull_request run 39385917836 attempt 1
and real CI Gate 118524872806 succeeded. Its new archive is re-downloaded and
byte-verified before using its measurements. No GO is supplied by its mutator.

## Question and predictions, before acquisition

Does the original internal-controller/RobotWindow/browser path exhibit enough
host scheduling/contact-phase variability, with unchanged world/program/commands,
to reproduce the historical RESET refusal in a bounded fresh-process series?

- A physical failure has persistent false predicates consistent with native
  pose, orientation, six velocities and contacts after the teleport transient.
- A measurement/freshness failure has persistent false predicates contradicting
  corresponding native state after that transient.
- Successes describe only their measured trajectories; they select no historical
  cause and establish neither disappearance nor restored main health. Eight
  successes are not an intermittent-defect acceptance criterion.

Run exactly EIGHT trials sequentially, each a fresh original runner/Docker/browser
acquisition, with all fourteen original RESETs and positive/negative/freshness
oracles. Stop at the FIRST native refusal, preparation failure or verification
error. No retry, no replacement, no continuation until green. Retain every
started trial, including incomplete ones. After eight successes, terminate this
series and assess measured variability, without another identical blind series.

The only C change remains the original two prints of #652; DEFER_STEPS=0.
No receiver wrapper, fixture, physical injection, changed wait/command/strategy,
timeout or safety threshold is applied. An argument wrapper records Chrome's
actual version, downloaded deb and executable SHA-256 immediately after original
installation and before Webots starts. Original/measured preparation commands
are retained. This changes preparation only, not the original simulation path.
If Chrome changes between trials, analyze those strata separately. CPU information
is retained once for this single VM. The host schedule is not a historical replay.

The wrapper always moves a completed/refused acquisition before another invocation
can recreate its original directory. Original primary manifests are unchanged;
new outer metadata/analysis are covered by a separate campaign manifest.
A real RESET_TIMEOUT exposes every internal sample and native samples from the
preceding second through that RESET in readable job logs, and retains the ENTIRE
raw acquisition in the archive. Equal observer timestamps are not claimed to be
simultaneous reads. The comparator excludes elapsed 0 and +32ms and projects
world angular velocity to the body frame; raw fields remain primary.

## Remote byte verification

The original canonical ZIP and the actual uploaded campaign ZIP are downloaded
through GitHub's artifact API. The verifier checks exact artifact/run/HEAD and
SHA-256 against the API digest, then checks manifests, the two-print source
relationship, original image/HEAD provenance, recalculated predicates/windows
and native observations. Authorization is stripped on signed-download redirects.
The hostile-byte/path/redirect tests run before acquisition. Original runner
failure is not inferred from its Docker exit-code alone: the outer runner result
is retained because a browser ERROR can stop the container with exit 0.
A missing/incomplete acquisition remains UNPROVEN, never a native success.

The branch-specific push workflow publishes no context named CI Gate and does
not integrate this branch or #653. Independent review on exact Ready #653 remains
required. Main 4ff57f7621fbff42756b90b089afbe40569f2514 remains NOT restored and
ordinary integrations remain suspended.
