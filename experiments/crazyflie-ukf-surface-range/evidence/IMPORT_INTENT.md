# One-shot raw evidence import

This branch exists only to make the already-acquired #70 checkpoint traces machine-readable from GitHub. The temporary importer workflow downloads the owner-attached archives from #180, #236 and #251, verifies the published archive digests where available, safely extracts UTF-8 evidence (including all CSV traces), records source/archive/file provenance, commits that evidence, and removes the importer workflow before the final candidate is offered for integration.

No new physical test, firmware retuning, Runtime change, flight authority or product claim is introduced.
