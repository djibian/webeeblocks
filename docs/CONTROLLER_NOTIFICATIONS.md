# WebeeBlocks V4 human notifications

GitHub is authoritative. Controller lifecycle never notifies Emmanuel.

## The only notification

The sole notification class is TEST_REQUIRED. It is valid only for:
1. real-world information that the machine cannot produce and that has become
   indispensable to an important decision/work path; or
2. final real-world acceptance of an exact artifact intended for publication.

There is no notification for CI, Ready PRs, reviews, GO, NO_GO, merges, blocked
Controllers, session limits or relaunch.

## Checkpoint request

A Controller does not call ntfy. It writes on a relevant GitHub issue/PR:

CHECKPOINT_REQUEST <40-char-sha> <test-profile> <checkpoint|release>
<actionable instructions>

human-checkpoint.yml performs deterministic preparation and may emit
TEST_REQUIRED only after the exact target, full evidence, required artifact,
provenance/digest and procedure are ready. Enabled profiles are:

- `windows-low-end` — checkpoint or release acceptance of the Windows classroom artifact;
- `s3-props-off` — checkpoint-only, props-removed #70 S3 physical evidence using the exact deterministically built experimental `cf2.bin` artifact.

Any unknown profile is rejected until its preparation is implemented explicitly.

## Human concurrency and idempotence

There may be only one unresolved TEST_REQUIRED globally. There is no queue. If a
test is already open, another checkpoint request remains silent in its own
GitHub context.

A fingerprint is derived from target SHA + test profile + purpose. If the same
fingerprint already produced a TEST_REQUIRED issue, repetition is a no-op.

Actions concurrency only serializes creation. The durable fact is the open
canonical `[TEST_REQUIRED]` GitHub issue created by `github-actions[bot]`; arbitrary
issues, pull requests or copied marker/fingerprint text do not occupy the human
slot and do not deduplicate a checkpoint.

## Resolution

A TEST_REQUIRED closes only with PASS, FAIL or NOT_NEEDED. NOT_NEEDED is valid
only when the requested result can no longer influence any relevant future
decision. A late PASS/FAIL after NOT_NEEDED remains historical evidence only.

ntfy is transport only. If delivery fails, the GitHub TEST_REQUIRED issue remains
authoritative.
