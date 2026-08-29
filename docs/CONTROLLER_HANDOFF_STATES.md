# Controller handoff states

- `READY_FOR_CONTROLLER`: a new manual impulse is useful now.
- `WAITING_EXTERNAL`: external CI/event is still running; no manual relaunch is useful.
- `HUMAN_REQUIRED`: a human decision, permission or physical action is indispensable.
- `DONE`: no work is actionable and no known external event is expected to reopen it immediately.
