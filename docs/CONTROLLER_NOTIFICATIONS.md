# Controller notifications

Notifications transport a terminal handoff; they never store Controller state.

## When ntfy is sent

CI pending and CI completion are silent. An active Controller session waits,
polls moderately and continues from the exact result without asking Emmanuel
to relaunch it.

The trusted default-branch workflow sends one notification only when a terminal
Controller handoff requires an external action:

| Status | GitHub artifact | Requested action |
| --- | --- | --- |
| `READY_FOR_REVIEW` | PR comment | launch a fresh Reviewer-Integrator |
| `NO_GO` | native PR review | launch a Worker to repair the same PR |
| `UNPROVEN` | native PR review | arbitrate or obtain the missing proof |
| `HUMAN_REQUIRED` | PR or issue comment | perform the stated human action |
| `BLOCKED` | PR or issue comment | resolve the stated blocker |
| `SESSION_LIMIT` | PR or issue comment | relaunch the same mode |

`GO`, `COMPLETED`, ordinary comments/reviews and every CI event are silent.

## Strict handoff protocol

Worker and non-review terminal comments use an exact first line:

```text
CONTROLLER_HANDOFF <STATUS> <full-sha>
```

The allowed comment statuses are `READY_FOR_REVIEW`, `HUMAN_REQUIRED`,
`BLOCKED` and `SESSION_LIMIT`. The following lines must contain a precise,
actionable detail.

Reviewer handoffs use the existing native review verdict as the exact first
line:

```text
NO_GO <full-sha>
UNPROVEN <full-sha>
```

The workflow accepts an event only when:

- repository and author are exactly the trusted repository owner;
- a PR handoff names the current full head SHA of a PR to `develop`;
- an issue-only handoff names the current full `develop` SHA;
- the first line matches the strict grammar and details are non-empty.

Stale or ordinary events are ignored. The Controller emits at most one artifact
for a terminal status/SHA. GitHub remains authoritative if ntfy delivery fails.

## Security

- fixed ntfy server `https://ntfy.sh/`;
- secret limited to `NTFY_TOPIC`;
- `permissions: {}`;
- no candidate checkout, import or execution;
- no GitHub write, CI orchestration or merge authority;
- event JSON is parsed as data and current public GitHub state is revalidated;
- transport failure cannot change CI, review or merge truth.

