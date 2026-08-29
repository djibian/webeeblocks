# Handoff payload schema

The live transport payload on `controller-signal` is `.controller/handoff.json` with `version: 1`, a `signal` in `READY_FOR_CONTROLLER | HUMAN_REQUIRED | DONE`, a short `message`, optional `copy_text`, and a WebeeBlocks GitHub `url`.

`WAITING_EXTERNAL` is never transported to ntfy.
