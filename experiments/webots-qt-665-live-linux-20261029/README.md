# #701 — live Linux QtGui/QPA witness, 29 October 2026

**Result: PASS for the inspected Linux process identity only.** No product source,
PR #701 HEAD, CI workflow, oracle, image or human boundary was changed.

The unchanged attester from #701 `fbf6031b81d81250e9b2ad5e7956481fc51400de`
was exercised on a real Webots process running current-main WebeeBlocks
`019b5843212d61d05d11a520587a3cdb6bb27d22`. `RESULT.json` records its source
blob/hash, complete verdict, actual runtime paths, kernel process birth identity,
Qt family and platform plugin digests. `native-evidence.tar.gz` retains raw maps,
stat/status/argv, original logs, world, build log, built Runtime executable,
commands/provenance, full candidate native observer trace and original manifests.
The 26 candidate sealed files were independently rehashed after termination: no mismatch.

- Actual Webots PID **3220**, starttime **138268**; parent-safe ELF
  `e45a90b580a00f50dc08746e6f43d1a86a83fcf1b23f55538737309154150545`.
- Actual mapped Qt Core/Widgets/**Gui** match all three unchanged pinned hashes.
  The attester checks dev:inode and hashes through the same open descriptor.
- **QPA OBSERVED**: bundled `libqxcb.so`, measured SHA256
  `238b0c632cabfc5fdfe793dad0780ad233b832aa5b297039a83d140b119ccf3d`.
  Twelve Qt6 families and QPA are inventoried; unpinned modules stay observed-only.
- Real Runtime READY, then the existing `runtime-reset-contact/run.py --mode baseline`
  completed: four positive missions, three negative missions, collision attempt 7,
  seven strict RESET acknowledgements and fresh attempt 8. This is the existing
  TCP diagnostic, not browser/Blockly/.wbb or the complete canonical progression.

## Exact environment and negative evidence

Webots files came from digest-verified layers of the existing immutable #701 OCI
`7a9272dfef96e7668f8f31eaac9099b0417a9028e3181df6f8376eea59fe1aca`.
**The image was unpacked, not run as a container**: Ubuntu 24.04 host, Mesa software
rendering, locally extracted Xvfb, R2025a assets from exact upstream
`c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b`. This is not an OCI-environment
qualification or an independently closed ABI claim. Manifest/config are archived.

Initial prerequisites failed before a scenario (executable modes, Xvfb xkbcomp,
then libxkbfile); their logs are retained. The first live run accidentally used
the official ELF `1445efb2...`: the attester correctly REFUSED it. Inspecting the
last image layer independently showed the correct `e45a90b5...` bytes; these were
explicitly extracted, hashed and atomically installed before the distinct candidate
run. The initial unpack helper is retained for provenance, not as a validated OCI
unpacker. There is no evidence the published OCI has the wrong binary.

The official run's `events.jsonl` changed after its original seal. That manifest
is preserved and this run is **not claimed as qualified mission evidence**; its
live identity refusal remains useful. The candidate manifest has no mismatch.
The direct unit-test script had 7 passes and one environment-sensitive negative
failure (`/proc/2/exe` permission error versus expected text); it is not reported green.

Existing cleanup terminated controller groups; no SIGSEGV marker was observed.
This does **not** reproduce the unavailable/console-close crash, capture a first
memory violation, prove natural downloader retirement, eliminate RESET_TIMEOUT,
qualify Windows or authorize #701 Ready/merge. #637/#665 remain open. No hardware.

To verify, check SHA256SUMS, extract the archive and rehash payload-sha256.json
and candidate/sha256.json; then correlate live maps/stat/argv, attestation and
controller-0.log READY. Reproduction uses the exact main runner and archived
observer wrapper, with dependencies/paths adapted explicitly; it must not silently
substitute the official ELF or treat an absent QPA mapping as observed.
