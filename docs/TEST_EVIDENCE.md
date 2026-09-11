# Durable physical-test evidence

Issue #296 defines the canonical path for future bounded CSV/text/log evidence.
Raw files produced by a physical checkpoint should become ordinary Git content;
a browser-only `github.com/user-attachments` upload may be convenient transport,
but it is not canonical project evidence.

The publication path is:

`exact request -> local output directory -> materialize/verify -> new evidence branch -> Draft PR -> human verdict`

`tools/evidence/publish_test_evidence.py` is the deterministic local bridge. It
does not run a physical test and it never records `PASS`, `FAIL` or `NOT_NEEDED`.

## Registering a test-output profile

Each reusable output shape is a repository-controlled JSON file under
`tools/evidence/profiles/`. A profile declares:

- a stable versioned profile id;
- `required_globs`, each of which must match at least one produced file;
- `allowed_globs`, outside of which publication fails closed;
- `max_files` and `max_total_bytes` bounds.

Adding a profile is sufficient to describe a new bounded output shape; no
experiment-specific importer workflow is required. Version an incompatible
profile rather than silently changing the meaning of evidence already published
under an older id.

The initial `physical-csv-text-v1` profile requires at least one CSV and allows
bounded CSV, text, JSON and log files.

## Materialize and verify locally

The source directory is never modified or removed. From a checkout that contains
the exact tested commit:

```sh
python3 tools/evidence/publish_test_evidence.py \
  --repo-root . materialize \
  --source /path/to/test-output \
  --destination experiments/<experiment>/evidence/checkpoint-<N>-<sha12> \
  --profile physical-csv-text-v1 \
  --target-sha <exact-tested-40-char-sha> \
  --checkpoint-ref issue-<N> \
  --purpose checkpoint \
  --request https://github.com/djibian/webeeblocks/issues/<N>#issuecomment-<ID> \
  --provenance '<one-line capture command or equally precise production description>'
```

The resulting directory contains:

- `raw/` — byte-for-byte copies of the registered source files;
- `PROFILE.json` — the exact profile contract used for this capture;
- `EVIDENCE.json` — exact SHA/request/profile/purpose/capture provenance, sizes,
  digests, and an explicit `human_verdict: null`;
- `MANIFEST.sha256` — an independently checkable raw-file SHA-256 manifest;
- `.gitattributes` — `raw/** -text`, so Git does not normalize CRLF measurement
  bytes or turn them into whitespace failures.

A fresh Controller or operator can verify an evidence directory with:

```sh
python3 tools/evidence/publish_test_evidence.py \
  --repo-root . verify \
  --evidence-dir experiments/<experiment>/evidence/checkpoint-<N>-<sha12>
```

Verification fails closed on a missing, unexpected, modified, size-mismatched or
digest-mismatched raw file, malformed metadata/profile, changed manifest, invalid
tested commit, or byte-preservation attributes.

## Publish without a manual attachment

When tooling/AI has access to the local files and authenticated Git push is
available, use `publish` instead of manually staging an archive:

```sh
python3 tools/evidence/publish_test_evidence.py \
  --repo-root . publish \
  --source /path/to/test-output \
  --destination experiments/<experiment>/evidence/checkpoint-<N>-<sha12> \
  --profile physical-csv-text-v1 \
  --target-sha <exact-tested-40-char-sha> \
  --checkpoint-ref issue-<N> \
  --purpose checkpoint \
  --request https://github.com/djibian/webeeblocks/issues/<N>#issuecomment-<ID> \
  --provenance '<one-line capture command or equally precise production description>' \
  --base-sha <exact-current-main-sha> \
  --base-ref main \
  --branch evidence/issue-<N>-<sha12>
```

Publication requires a clean checkout exactly at `--base-sha`, reconstructs the
remote `main` SHA, refuses an already-existing evidence branch, creates the local
branch, materializes and re-verifies the evidence, commits only that destination,
rechecks remote `main` and the destination branch immediately before push, and
uses a normal non-force push. It then verifies that the remote branch resolves to
the exact created commit.

If the remote base moves, the evidence branch appears concurrently, push is
rejected, or remote verification is ambiguous, the command reports failure and
keeps the local source/evidence for recovery. It never deletes raw source data.

After a successful push, the Controller/AI opens a short Draft PR from the
reported branch to `main`, links the exact checkpoint/request, and lets normal
governance/independent review validate the evidence mechanism and content. The
branch plus PR are project state; no Controller ownership marker is needed.

## Authority boundary

Raw publication is machine evidence, not a real-world acceptance verdict.
`human_verdict` is deliberately fixed to `null`; this helper has no command-line
surface that can publish `PASS`, `FAIL` or `NOT_NEEDED`. Those remain separate,
owner-authoritative actions bound to the applicable TEST_REQUIRED request.

Derived analysis should live separately from `raw/` and cite the immutable
evidence set. A correction or recapture uses a new destination/branch; the tool
will not overwrite an existing decision-relevant publication.
