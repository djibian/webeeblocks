# Compiled Webots self-pipe contrast — bounded native Linux result

Execution HEAD929ce7839aa19a738ef8fbd264996aeb381aa2a2, NON-GATE run40897930515,
job123532011648, attempt1 completed/success. Source product c0cb8c1873d48b26a0f67976c65fa92ca5d54f52;
upstream c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b. Current patch e9a6d936...
includes the process-lifetime FD repair, not the older d14be0c1 candidate.

## What actually ran

The full R2025a C/C++ application, renderer archives, Qt moc objects and link
were built against the same original Qt6.5.3 runtime libraries in a development
overlay of official OCI f0023e30.... Qt SDK6.5.3 supplied headers/moc only.
The baseline was built first. Then ONLY src/webots/gui/main.cpp was patched,
recompiled and relinked with the same compiler, flags and remaining objects.
Both real ELF files were installed successively into the disposable runtime,
then the existing unavailable/seed0/side2 test ran with internal controllers.
This was not a fake WbApplication, replacement main shim or partial Qt harness.

| Observation | Rebuilt baseline | Self-pipe fixed |
|---|---|---|
| Complete ELF bytes |201743200|201753304|
| ELF SHA256 |b9657239ea5dd004e5ed300fff1bbb0f929e1fc978d221726c7a019e65481176|6839dab73edffa3c5f2dda7fd043e6401cbf8d56595c2c5ebf3e09d7a85ec991|
| Actual Webots PID |135|195|
| Original callback offset |0x5479b0|0x547c70|
| SIGTERM handler entries/exits |2/2|2/2|
| Allocator calls at positive handler depth |4:120,4,120,4|0 observed|
| Mission negative |not-achieved/runtime|not-achieved/runtime|
| Simulated seconds |9.288|9.288|

The loaded ELF device/inode and callback relocation were matched to the exact
built file in each execution. Reused installation inode6737078/dev44 is recorded
explicitly; PID/trace/callback differ and each owned group is empty after cleanup.
The interposer was the already published observer from aba2a254...;
no new context observer or source predicate was substituted for execution.
Binary trace records were independently compared to their JSON decodings:
27 baseline records,19 fixed records,48 bytes each, one actual PID per trace.
Both existing strict native capture audits pass:12 files each,24 hashes total.

World bytes are identical, SHA256
4b17c32951fa76627e73485dc41c7ef30ef91f76b950b0525bf78a0f7322ef5a.
AST is identical, SHA256
89f955f1fcbcb6434e547a940c5a6f3db308608e45a0723d52df8120ca2c8d7d.
Events are byte-identical, SHA256
a91a7cde8f069d55a26ed422d91d4cd041a70b25b4539673dc30f4de0d423904.
Both internal controllers emit Terminating; EOF collection completes and both
owned process groups are empty. Direct wrapper statuses are-15, node statuses0;
these are NOT exit statuses of the actual Webots PIDs.

Handler disassembly of the exact binaries corroborates the contrast:
baseline jumps to WbApplication::simulationQuit; fixed normal path only calls
__errno_location/write and restores errno. Both are PIE/BIND_NOW binaries.
Qt Core/Gui/Widgets SHA256 remain the original ac3912.../f8396f.../868b51...
and appear in the actual loader maps; the full Qt library manifest is unchanged
before/after the two native executions.

## Durable data and independent reproduction

Original complete Actions artifact12908396846 is183675532 bytes,74 CRC-valid
entries, SHA2560637fdebbdd34beffb496ca6819d0119e3c01b9441e69af00f3e93b063912f5f.
It includes BOTH full debug ELF binaries and build inputs/logs. They were
downloaded, CRC-checked and independently rehashed before this conclusion.
Actions retention is14days; complete binaries are not silently claimed archived
forever in Git.

native-evidence.zip is a DERIVED preservation subset,1244847 bytes,65 CRC-valid
entries, SHA256a61a1b07da6995e076180af22bfce73d1d3b119e539b8110535b12072699b0b4.
It retains both complete native captures, raw context traces/maps, identities,
source patch/build/dependency/header hashes, package/image/compiler provenance,
original build/native logs, exact handler disassembly and dynamic flags.
PRESERVATION.json identifies raw original members and omitted binary/archive
payloads. All retained original member bytes are unchanged. Rebuild using the
checked-in workflow/build scripts for the exact input chain; no unchanged native
repeat is needed. The workflow is manual-only after publishing this result.

## Scope and remaining qualification

The source defect allocating in the POSIX handler is removed in the tested
compiled/loaded consumer, with a matching faulty baseline and preserved negative.
The pre-build source.txt NOT_TESTED strings describe that EARLIER static phase,
not the final result in RESULT.json.

This does NOT reproduce or attribute the historical #665 Qt console SIGSEGV,
prove absence of all internal glibc allocations from trace absence alone, qualify
all signals/timings, the full native suite/RESET/LAND210000ms or Windows Ctrl+C,
adopt an OCI/product distribution, promote #701, grant Ready-HEAD CI Gate/GO or
authorize hardware. The process-lifetime FD fix also has its separate actual
kernel scheduling counterexample/control in the parent experiment directory.
No own independent GO is supplied by the execution that repaired this patch.
