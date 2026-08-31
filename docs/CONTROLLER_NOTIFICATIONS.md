# Controller notifications

Notifications transport an external event; they never store Controller state.

## CI settlement

The trusted default-branch workflow observes only completion of the top-level
`CI Gate`. It performs no checkout, executes no candidate code, writes nothing
to GitHub and has no merge authority.

For the PR and exact head attached to the completed run, it sends one ntfy
message containing:

- PR number;
- full head SHA;
- the GitHub conclusion;
- the workflow-run URL.

The event is ignored when its embedded current PR head differs from the
completed run SHA. Every accepted notification still includes the exact SHA,
so the Controller can reject any event superseded after delivery.

The message says that CI settled, not that the change is approved. A fresh
Controller launch reconstructs the result and chooses Worker or
Reviewer-Integrator.

## Human action

When a product decision, permission or physical test is indispensable, the
Controller mentions `@djibian` in the relevant issue or PR and asks one precise
question with a recommendation. GitHub Mobile is the durable fallback.

No `READY_FOR_CONTROLLER`, `WAITING_EXTERNAL`, Draft transition or issue-log
comment is required to derive a mode.

## Security

- fixed ntfy server `https://ntfy.sh/`;
- secret limited to `NTFY_TOPIC`;
- no candidate checkout or import;
- no GitHub write permission;
- an event whose embedded PR head already differs from the run SHA is ignored;
- transport failure cannot change CI, review or merge truth.
