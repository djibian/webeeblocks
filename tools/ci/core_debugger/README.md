# Offline debugger provisioning (CI only)

The subject image remains the exact M2 R2025a digest in `run_grand_prix_u_geometry.py`.
This Dockerfile prepares a separate GDB image only; never use it for Webots
simulation. The image must be published to the existing GHCR package under a
new tag, never replacing the subject tag. Commit its immutable
`ghcr.io/djibian/webeeblocks-qt665-r2025a@sha256:<64 hex>` reference as
`tools/ci/core_debugger/image.txt` only after verified publication. No mutable
tag or missing reference is accepted by the capture script. Build from the
exact Dockerfile, not an arbitrary prebuilt image.

Provisioning requires network access to Ubuntu archives and GHCR once. Native
qualification pulls the pinned images, exports an SHA-256-verified ELF
snapshot from the original subject image with networking disabled, then runs
GDB in a separate pinned debugger container with the original sysroot and
core read-only, networking disabled. No apt during the qualification. The
existing intentional multithread SIGSEGV preflight, restoration, size limit,
stack predicates and failure return codes remain mandatory. If the helper
comes from outside the original snapshot the result is unproven.
