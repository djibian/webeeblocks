# Controller notification security boundary

The notification workflow handles only GitHub metadata and a low-value ntfy topic secret. It never checks out or executes candidate PR code.

The ntfy topic is not a product credential or deployment authority. Rotate it if exposed. Do not add higher-value secrets to this workflow.

`main` remains outside the notification architecture.
