# Controller handoffs and Android notifications

WebeeBlocks uses issue #100 as the durable human handoff log. Repository and exact-head GitHub facts remain authoritative; #100 is not a queue, lock or controller-state database.

## Signals

Every Controller terminal frontier produces one concise #100 comment whose first line is exactly one of:

- `WEBEEBLOCKS_SIGNAL: READY_FOR_CONTROLLER`;
- `WEBEEBLOCKS_SIGNAL: WAITING_EXTERNAL`;
- `WEBEEBLOCKS_SIGNAL: HUMAN_REQUIRED`;
- `WEBEEBLOCKS_SIGNAL: DONE`.

The comment mentions `@djibian`. `READY_FOR_CONTROLLER` includes the standard Controller relaunch text. `HUMAN_REQUIRED` includes one decision, its genuine options, a recommendation and a directly usable `COPY_TEXT`.

`WAITING_EXTERNAL` is used only when CI, a check or another external event is genuinely still running and no useful same-mode work remains. It never includes a relaunch request. `DONE` is reserved for a state where no known external event is expected to make work immediately actionable.

## PR lifecycle

Draft/Ready is not a Worker/Reviewer lock.

1. Worker prepares a stable head and normally opens the PR directly Ready.
2. Required workflows run against the GitHub pull-request merge ref.
3. A repair is pushed directly to the same Ready PR.
4. Native `pull_request.synchronize` events request fresh exact-head evidence.
5. When the exact head is green, a fresh Reviewer-Integrator independently judges it.
6. Only `GO <full_sha>` permits the unchanged head to merge into `webots-ci`.

All required PR workflows either use GitHub's implicit `synchronize` subscription or list `synchronize` explicitly. No workflow dispatcher or PR-stability watcher substitutes raw-branch runs for pull-request merge-ref evidence.

This contract is intentionally enforced by the real workflow triggers plus independent review, not by a custom YAML meta-parser. Repository-level protections should be used for stronger mechanical authority boundaries when they become available or are deliberately configured.

## Trusted Android relay

The separately authorized default-branch workflow is:

`.github/workflows/controller-handoff-ntfy.yml`

It runs only when a new issue comment is created. Before publishing, it revalidates:

- repository `djibian/webeeblocks`;
- issue number `100`, excluding pull requests;
- comment author equal to the repository owner;
- first-line signal in the four-value protocol;
- any notification target URL remains inside the repository.

It relays only:

- `READY_FOR_CONTROLLER`;
- `HUMAN_REQUIRED`;
- `DONE`.

`WAITING_EXTERNAL` is intentionally silent on Android. The relay does not infer that CI completed and never creates a new handoff.

## Security boundary

The workflow is trusted because GitHub loads `issue_comment` workflows from the default branch. Its contract is deliberately smaller than a PR watcher:

- `permissions: {}`;
- no checkout;
- no execution or import of candidate code;
- no PR or check observation;
- no polling or workflow dispatch;
- no GitHub comment, branch, review or merge authority;
- event content parsed only as untrusted data;
- fixed ntfy server `https://ntfy.sh/`;
- only the `NTFY_TOPIC` secret is consumed.

The relay never changes product, review or controller state. The #100 comment remains authoritative if ntfy is unavailable.

## ntfy setup

1. Install the official ntfy Android application.
2. Subscribe to a long random topic.
3. Add that topic as the repository Actions secret `NTFY_TOPIC`.

Never commit the topic. Rotate it if it is exposed or receives unwanted messages.

For actionable signals, the notification can provide:

- **Copier** for the `COPY_TEXT` line;
- **Ouvrir GitHub** for the first repository-local evidence link;
- **Ouvrir ChatGPT** for `READY_FOR_CONTROLLER` and `HUMAN_REQUIRED`.

Absence or failure of ntfy must never weaken CI, alter a verdict, block a safe merge or cause a duplicate handoff.
