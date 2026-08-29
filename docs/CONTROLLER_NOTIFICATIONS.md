# Controller handoff and Android notifications

WebeeBlocks uses issue #100 as the durable human handoff log. Repository facts remain authoritative; #100 is not a queue, lock or machine-state database.

## Signals

The Controller records exactly one terminal signal:

- `READY_FOR_CONTROLLER`: a fresh manual Controller impulse is immediately useful;
- `WAITING_EXTERNAL`: CI/checks or another external event are still running, so no user action is useful yet;
- `HUMAN_REQUIRED`: a concrete human decision, permission or physical action is indispensable;
- `DONE`: nothing further is currently actionable and no known external event is expected to make it immediately actionable.

Every signal mentions `@djibian`, so GitHub Mobile remains the zero-configuration fallback.

## Why WAITING_EXTERNAL exists

Before this contract, a Controller run waiting for CI used `DONE`, and Emmanuel then had to inspect GitHub manually to discover when another launch became useful. `WAITING_EXTERNAL` separates a temporary asynchronous wait from real completion.

A Ready PR is watched by GitHub Actions. Once its exact head stabilizes, the watcher posts a deduplicated `READY_FOR_CONTROLLER` in #100 and can send the Android notification automatically. ChatGPT therefore does not poll CI.

## Simplified PR lifecycle

Draft/Ready is no longer a Worker/Reviewer lock.

Normal lifecycle:

1. Worker prepares a stable head on a short-lived branch.
2. Worker opens the PR directly Ready for review.
3. Full exact-head CI runs.
4. If CI fails or independent review returns `NO_GO`/`UNPROVEN`, a fresh Worker repairs the same Ready PR directly.
5. The repair push changes the SHA, invalidates stale verdicts and triggers fresh CI through `synchronize`.
6. When exact-head CI stabilizes, the watcher notifies Emmanuel.
7. A fresh Reviewer-Integrator either rejects the head or records `GO` and merges it unchanged to `webots-ci`.

The old Ready→Draft→Ready round-trip is not required. Draft remains available only for genuinely incomplete exceptional work.

## Automatic PR-stability watcher

`.github/workflows/controller-android-notification.yml` watches non-Draft pull requests targeting `webots-ci` on `opened`, `reopened`, `synchronize` and `ready_for_review`.

The watcher:

- never checks out or executes candidate PR code;
- binds itself to the exact PR head SHA;
- aborts if the PR closes, becomes Draft or changes head;
- waits until external exact-head checks are complete and remain unchanged for a stabilization window;
- treats a stabilized failing head as actionable, because Worker can diagnose it;
- posts one deduplicated `READY_FOR_CONTROLLER` handoff in #100;
- optionally sends the same event through ntfy.

## Why issue_comment is not the ntfy trigger

GitHub documents that `issue_comment` workflows run only when the workflow file exists on the repository default branch. WebeeBlocks deliberately keeps `main` human-controlled and does not install controller infrastructure there. Therefore #100 comments cannot directly trigger ntfy without violating that branch boundary.

Instead, non-CI terminal notifications use a dedicated transport branch.

## `controller-signal` transport branch

After this infrastructure is integrated, create `controller-signal` from the integrated `webots-ci` head. It is permanent transport infrastructure, not a product WIP and never merges anywhere.

For `READY_FOR_CONTROLLER`, `HUMAN_REQUIRED` and `DONE`, the Controller first writes the authoritative #100 comment, then updates only:

`.controller/handoff.json`

on `controller-signal`.

`WAITING_EXTERNAL` is intentionally not mirrored, because the user should not be disturbed while CI is still running.

Expected payload:

```json
{
  "version": 1,
  "signal": "HUMAN_REQUIRED",
  "message": "Short human-readable summary",
  "copy_text": "Recommended response ready to copy",
  "url": "https://github.com/djibian/webeeblocks/issues/100"
}
```

A `push` workflow on that branch reads the JSON strictly as data and publishes the Android notification. It does not execute repository code from the payload.

## ntfy one-time setup

1. Install the official ntfy Android application.
2. Choose a long, random, unguessable topic and subscribe to it.
3. In GitHub repository **Settings → Secrets and variables → Actions**, create `NTFY_TOPIC` with that topic.
4. Optional: add `NTFY_SERVER` for a self-hosted ntfy server; otherwise `https://ntfy.sh` is used.

Do not commit the topic. Treat it as a low-value notification credential: if it is ever exposed or spammed, rotate it.

If `NTFY_TOPIC` is absent, all workflows exit cleanly and GitHub `@djibian` mentions remain the fallback.

## Android actions

Notifications can contain up to three actions:

- **Copier** / **Copier relance**: copies the `COPY_TEXT` payload;
- **Ouvrir GitHub**: opens the relevant PR or #100;
- **Ouvrir ChatGPT**: opens ChatGPT.

`HUMAN_REQUIRED` uses high priority; `READY_FOR_CONTROLLER` uses normal priority; `DONE` uses low priority.

## Security boundary

The ntfy topic is the only secret required by this workflow. Never add product credentials, deployment secrets or privileged external authority to this notification mechanism.

The PR watcher reads GitHub API metadata/checks only and never executes PR code. The signal transport reads only the fixed JSON path from the trusted transport branch. `main` is not modified by this architecture.
