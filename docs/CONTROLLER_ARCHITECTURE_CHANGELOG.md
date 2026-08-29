# Controller architecture simplification — 2026-08-29

The #78 / PR #99 cycle exposed three orchestration costs that were unrelated to product correctness:

1. repeated Ready→Draft→Ready transitions were required only because role derivation used PR Draft state as a lock;
2. Controller runs stopped while CI was still active, but `DONE` did not distinguish temporary waiting from real completion;
3. the user had to inspect GitHub manually to discover when the exact head had stabilized.

This change removes those costs while preserving independent review:

- role derivation now uses exact-head CI and exact-head verdicts, not Draft/Ready;
- Worker repairs a failing or rejected Ready PR directly, with the new SHA invalidating stale verdicts;
- new PRs normally open directly Ready after branch-side preparation;
- `WAITING_EXTERNAL` represents a real asynchronous wait and never asks for a useless Controller relaunch;
- a GitHub-native PR watcher emits `READY_FOR_CONTROLLER` after exact-head stabilization;
- a dedicated `controller-signal` branch can deliver non-CI terminal signals to ntfy without modifying `main`.

Independent Reviewer-Integrator review remains mandatory before merge to `webots-ci`, and `main` remains human-controlled.
