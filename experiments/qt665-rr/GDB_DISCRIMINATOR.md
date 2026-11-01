# Unique fallback: controlled SIGTERM inside the real allocator

**Proposed experiment, NOT EXECUTED. No ROOT_CAUSE_PROVEN claim.**
GitHub's observed runner permits child ptrace, so this fallback does not require
hardware counters. The present Work Mode host does not permit it. Do not confuse
an available ptrace syscall with qualification of the full GDB/Webots experiment.

## Falsifiable question

Can the *real* original Webots quit handler, delivered at an authenticated
allocator instruction after READY, cause two still-live allocation owners to
receive the same heap chunk (or first write invalid allocator metadata)?

Existing traces only establish `malloc(120), malloc(4)` inside that handler;
they do not observe its interrupted context or any corruption. This experiment
adds the missing controlled interrupted instruction and ownership invariant.
It is not another unstructured signal or no-crash campaign.

## Matched subjects and reuse

For allocator scheduling A/B, reuse the already-built pair from original
Actions artifact **12908396846**, run **40897930515**, ZIP SHA256
`0637fdebbdd34beffb496ca6819d0119e3c01b9441e69af00f3e93b063912f5f`.
No compilation is justified before checking availability and hashes.

* A: rebuilt upstream baseline ELF
  `b9657239ea5dd004e5ed300fff1bbb0f929e1fc978d221726c7a019e65481176`.
* B: same build, only main.cpp self-pipe change, ELF
  `6839dab73edffa3c5f2dda7fd043e6401cbf8d56595c2c5ebf3e09d7a85ec991`.

This pair is **not** the historical official ELF; it controls the source-level
mechanism. The combined #701+POSIX ELF changes two mechanisms and is therefore
not the minimal B here. The self-pipe candidate's known Cancel-veto defect
remains disqualifying for adoption; this noninteractive matched experiment
does not test or repair it. Do not promote this B from an allocator result.

Use the same pinned OCI, libc, Qt libraries, host, actual `unavailable` world,
AST, native oracles and controller resources for both subjects. Hash libc and
its debug package/build ID, disassemble the actually mapped libc. The tcache
instruction must be identified afresh from these **exact bytes**, never from a
different machine's glibc offsets. Disable neither tcache nor ASLR to fabricate
equivalence. Software rendering only. No LD_PRELOAD allocator replacement.

## Exact observation/scheduling boundary

1. Attach GDB to the actual native Webots PID from a **separate process group**,
   outside the harness's owned termination group. Preserve its normal SIGTERM
   handling (`handle SIGTERM stop print pass`), ordinary 5 s cleanup bound and
   all oracles. A stop that consumes the cleanup budget is an invalid/incomplete
   trial, never a reason to enlarge that bound or hide SIGKILL.
2. Authenticate libc `__libc_malloc`/`__libc_free` and the inlined `tcache_get`
   path using its debug info and machine instructions. At the prospective
   interrupt boundary capture actual request size, tcache bin/count/head,
   chunk address and TLS identity. Select a bin that the **real** handler needs
   (observed 120/4 bytes), with a genuine pending outer allocation. Do not
   pre-fill/fake the allocator or modify mission data to manufacture this state.
3. Schedule **one additional real SIGTERM**, after the unchanged unavailable
   result, while malloc has loaded a tcache head but **before that pop is
   committed**. Check exact instruction ordering from disassembly: a source
   line alone is insufficient. If the unchanged run never reaches this state,
   report TARGET_NOT_REACHED and stop; do not perform a timing sweep.
4. Single-step the handler and resumed outer malloc. Log each pertinent
   allocation return and intervening free, with native TID, PC, requested
   size, returned chunk, tcache head/count, signal frame and object owner.
   Watchpoints on the *selected bin/chunk* should expose the first invalid
   store rather than taking a later malloc SIGSEGV as its cause.
5. In B require the **same semantic allocator instruction and pre-state**,
   not merely the same absolute PC (ASLR), and deliver the same signal there.
   The self-pipe must be exercised (write observed); the original callback
   in A must actually invoke its nested Qt allocation. Native scenario,
   world/AST and result invariants must remain unchanged in both.

If GDB cannot reach and observe these boundaries without violating the
existing wall-clock bounds, report EXPERIMENT_NOT_QUALIFIED. Preparing an
instrumented scheduling facility would then be a separately justified next
step, not an implicit timeout change or another campaign.

## Discriminating outcomes

* **Same chunk returned to two simultaneously live owners in A**, no intervening
  free, with the first conflicting mutation and both allocation lifetimes
  observed; **B exercises the same interrupt pre-state without that violation**:
  causal allocator-reentrancy mechanism demonstrated for the controlled pair.
* Target reached, original handler allocates but allocator invariants remain
  valid: refutes this **particular instruction/bin/interleaving**, not every
  signal-induced corruption hypothesis.
* Handler blocks on a glibc lock: demonstrates a controlled deadlock, not heap
  corruption or the historical SIGSEGV. Preserve this distinct result.
* A Qt object's destructor/free precedes its later reuse before any allocator
  invariant break: prioritize that observed lifetime violation. Do not call
  an allocator output the first violation until preceding object lifetimes
  have been checked. Birth/address reuse must be distinguished (ABA).

A duplicate live allocation is logically impossible in a correct allocator
even when all Qt objects are live. That makes it stronger than the previous
allocation-in-handler trace and distinguishes a concrete heap corruption route
from an independently stale console/document pointer. Nevertheless a forced
interleaving establishes **possibility**, not historical attribution. To connect
it to #665's actual core, recover a matching naturally faulting execution or
evidence of the same first violation leading to the same allocator fault.

For every outcome keep last pre-crash instruction, first observed invariant
violation, established causal mechanism and historical applicability separate.
Never infer an A/B success from B's lack of SIGSEGV alone.
