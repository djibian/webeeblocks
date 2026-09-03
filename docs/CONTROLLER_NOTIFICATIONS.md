# Controller notifications

Notifications transport a requested human action; they never store Controller
state and they are intentionally narrower than GitHub evidence.

## When ntfy is sent

There are only two notification purposes:

1. **TEST** — Emmanuel must perform a concrete manual/physical test or collect
   human-only evidence.
2. **RELAUNCH** — the current Controller session must stop and a fresh Controller
   launch is the next useful action.

Everything else is silent: CI pending/completion, `GO`, merges, roadmap changes,
context switches, ordinary comments/reviews and `UNPROVEN` by itself.

| GitHub artifact | Meaning for ntfy | Session effect |
| --- | --- | --- |
| `CONTROLLER_HANDOFF HUMAN_REQUIRED <sha>` | TEST | may continue on one independent atom |
| `CONTROLLER_HANDOFF READY_FOR_REVIEW <sha>` | RELAUNCH for independent review | stop |
| native review `NO_GO <sha>` | RELAUNCH for fresh Worker repair | stop |
| `CONTROLLER_HANDOFF BLOCKED <sha>` | RELAUNCH only when a fresh run is useful | stop |
| `CONTROLLER_HANDOFF SESSION_LIMIT <sha>` | RELAUNCH after real platform/runtime limit | stop |

A missing proof that does not itself require Emmanuel is recorded as
`VERDICT UNPROVEN <sha>` and does not match the ntfy transport grammar. If the
missing proof is a human test, publish the separate `HUMAN_REQUIRED` test
handoff once.

## Strict handoff protocol

Comment handoffs use an exact first line:

```text
CONTROLLER_HANDOFF <STATUS> <full-sha>
```

The transport-recognized comment statuses are `READY_FOR_REVIEW`,
`HUMAN_REQUIRED`, `BLOCKED` and `SESSION_LIMIT`. The following lines contain one
precise actionable detail.

The only native review that requests a relaunch is:

```text
NO_GO <full-sha>
```

`GO <full-sha>` and `VERDICT UNPROVEN <full-sha>` remain GitHub evidence but are
silent notification-wise.

The workflow accepts an event only when:

- repository and author are exactly the trusted repository owner;
- a PR handoff names the current full HEAD SHA of a PR to `develop`;
- an issue-only handoff names the current full `develop` SHA;
- the first line matches the strict grammar and details are non-empty.

Stale or ordinary events are ignored. The Controller must not duplicate an
already-current relaunch handoff or an unresolved identical human test. GitHub
remains authoritative if ntfy delivery fails.

## Compatibility during develop/main separation

GitHub executes the trusted notification workflow from the default branch. The
optimized Controller protocol therefore deliberately reuses the existing
transport-recognized statuses: once the new `AGENTS.md` is authoritative,
`HUMAN_REQUIRED` is emitted only for a test and the other recognized statuses
only for a required relaunch. `VERDICT UNPROVEN` intentionally does not match
the older `UNPROVEN <sha>` review grammar.

This means the semantic migration does not require an unauthorized direct write
to `main`. The updated workflow wording reaches `main` only through a later
human-authorized normal promotion.

## Security

- fixed ntfy server `https://ntfy.sh/`;
- secret limited to `NTFY_TOPIC`;
- `permissions: {}`;
- no candidate checkout, import or execution;
- no GitHub write, CI orchestration or merge authority;
- event JSON is parsed as data and current public GitHub state is revalidated;
- transport failure cannot change CI, review or merge truth.
