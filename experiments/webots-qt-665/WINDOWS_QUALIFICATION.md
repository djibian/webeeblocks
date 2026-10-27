# Windows #665 — bounded native startup qualification, 27 October 2026

The corrected R2025a engine now starts the **unchanged, prebuilt classroom
Runtime and its separate sequence evaluator** on genuine Windows. This removes
the earlier claim that no usable patched Windows process exists. It does **not**
establish a corrected distributable, full simulation acceptance, or V5 GO.

## Exact evidence

- Upstream source: `cyberbotics/webots@c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b`,
  original guarded-retirement patch **plus** `repair_parent_shutdown.py`.
- Corrected Windows build: [40415782024](https://github.com/djibian/webeeblocks/actions/runs/40415782024),
  [artifact 12695533700](https://github.com/djibian/webeeblocks/actions/runs/40415782024/artifacts/12695533700),
  ZIP SHA256 `86b9540cd5a41bdd5680fb81f00d35befb6610da26f414fffb67123e7267301e`.
  Genuine engine SHA256 `52b8c047047094c30f0cd358456ca5a18c73209457c2129991068f5825c8a06e`.
- Native import closure / CLI: [40421551904](https://github.com/djibian/webeeblocks/actions/runs/40421551904),
  source `460d6b591e76dadd880c02e8475627b2fb9c2939`. Win32 resolution of
  12,620 named imports over 44 non-system PE modules, no missing names/errors;
  Windows/API-set dependencies excluded explicitly. Not a full C++ ABI proof.
- Stronger product startup: [40470490820](https://github.com/djibian/webeeblocks/actions/runs/40470490820),
  exact experimental source `24718c8d8c76101fe745d891563fc719a06221de`, SUCCESS.
  [Artifact 12718363355](https://github.com/djibian/webeeblocks/actions/runs/40470490820/artifacts/12718363355),
  ZIP SHA256 `8d796b0d82cc50f6b2e45d56a58aac14220c07097217a76d0c7ab078a07b48d4`.
  Downloaded ZIP hash and all 21 entry CRCs independently rechecked locally.
  The original `packaged-startup/result.json` is retained as
  [windows-startup-native.json](windows-startup-native.json).

The startup consumes the untouched **75-file** classroom package from canonical
run `40386450869`, artifact `12681442366`, source
`1899293f458f6497dd1c0c024231173bb84f44fe`; artifact ZIP digest
`81cb4431654c3aebcb3ae53e64a00d79134f80707f67137bd70d52caf37b9596`.
All extracted files match its manifest. This package is a retained real consumer,
**not a new current-main build or a transfer of its earlier acceptance**.

The probe uses `webots.exe`, not only a directly invoked GUI engine; its child
is the exact corrected PE. Both grandchildren use the exact packaged controller
SHA256 `809cbb7ada0a70e29178e66fb761987fcfe5df94cc6ec261936547fbd28e5888`.
Their actual command lines distinguish flight Runtime (no argument) and
`sequence-evaluator-v1`. Both parents must be the observed engine; process
creation times are retained. READY plus these three live identities must coexist
for two seconds. No student program, takeoff, or physical flight is submitted.

The engine maps the expected Qt Core/Gui/Widgets, qwindows, OpenAL and three GCC
runtime DLLs. **Both** controller processes map the same expected Qt and GCC
runtime plus the original `Controller.dll`. Paths and SHA256 are recorded.
The launched environment removes ambient Qt/QML/Python/controller overrides;
PATH contains only Webots and Windows directories. Any mapped file from the
external MSYS2 SDK tree is rejected. The SDK remains installed on this producer
host: this is **not yet a clean-host distribution installation**.

## Causal distinctions

1. **False Qt refusals came from parser truncation.** `pefile==2024.8.26`
   defaults to `max_symbol_exports=8192`. Actual QtGui declares 8,895 names and
   QtWidgets 8,463. The default scans stop at 8,192 with warnings; 11 Gui and
   six Widgets imports of the real engine are then falsely reported absent.
   A bounded 65,536 limit, required complete declared-name count and zero
   warnings resolve all 17. QtCore has 6,817 names and is unaffected.
   This is reproduced byte-for-byte from the build ZIP by
   `diagnose_pe_export_truncation.py`; results are in
   [pe_export_truncation.json](pe_export_truncation.json). It does not qualify
   runtime ABI or erase real native failures.
2. **OpenAL was genuinely incompatible with the selected GCC runtime.**
   [40420506026](https://github.com/djibian/webeeblocks/actions/runs/40420506026)
   resolves Qt names natively but the original OpenAL imports unavailable
   `__emutls_v._ZSt11__once_call` / `__emutls_v._ZSt15__once_callable`.
   Win32 LoadLibrary fails with 127; Webots exits `0xC0000139`. Replacing
   OpenAL with the matching SDK component closes the tested native graph and
   permits actual Webots startup. The changed OpenAL SHA is recorded, not
   silently attributed to a Qt repair.
3. **The hosted GPU is a separate precondition.**
   [40469539046](https://github.com/djibian/webeeblocks/actions/runs/40469539046)
   attests all nine engine modules but fails before controller startup:
   `FATAL: Webots could not initialize the rendering system`, WGL unavailable.
   Its artifact `12718102060` (ZIP SHA256
   `c002e278766519204749a0ae2d6b207c6e4715982a3e3c78f31f74da89e6e814`)
   is preserved as FAIL. The successful later experiment applies the **existing
   canonical CI** Mesa 24.2.1 archive, SHA256
   `f8355fa7274d8414f88160f0f0af3469bf0f9f192f84d7a7ffb06a4887ceb214`,
   with its existing `MESA_GL_VERSION_OVERRIDE=3.3` and software-renderer setting.
   Actual loaded OpenGL paths/hashes are retained. No minimize/no-rendering
   flag, world change, lowered oracle or hidden retry was added to the probe.

## Reproduction and remaining boundary

The Windows experiment lives on the separate durable branch
`evidence/665-windows-product-startup-20261027`, workflow
`.github/workflows/qt665-win-runtime-adoption.yml` at the exact source above.
It is deliberately **NON-GATE** and is not copied into the canonical workflow
allowlist. Build PE, package and installer identities are checked; SDK drift
fails closed. Live MSYS2 package installation is not an immutable/offline
distribution or a promise that future package repositories preserve these bytes.

Local host checks:

```sh
python -m unittest discover -s experiments/webots-qt-665 -p test_probe_windows_packaged_runtime.py -v
PYTHONPATH=/path/to/pefile-2024.8.26 python experiments/webots-qt-665/diagnose_pe_export_truncation.py \
  --build-archive /path/to/artifact-12695533700.zip --output /tmp/export-completeness.json
```

Five adversarial unit tests reject an evaluator substituted for Runtime,
unexpected controller arguments, missing/wrong/duplicated/tampered mapped DLLs,
external SDK dependencies, ambient Qt lookup, and corrupt/unlisted/escaping
package files. These checks run through repository hygiene in the canonical CI.
The full local hygiene run is **not PASS** on the Work host: the existing Linux
attester test cannot observe its syscall PID in mounted procfs (`/proc/12/stat`
absent), and the existing X3 clean-source test rejects an in-progress dirty
merge. Neither refusal is bypassed or reclassified.

Remaining: immutable Windows runtime packaging and installation on a clean
consumer without SDK; a current-source product build and full unchanged native
campaigns; exact canonical Ready CI Gate; independent review resolving all
applicable refutations; conditional merge and actual adoption. Qt6.12 Windows
startup does not transfer Linux Qt6.5.3 reentrance results or establish a natural
download callback inside full Webots `setValue`. The old timeout-gate FAIL is
historical evidence to assess on its actual subject, not to relabel or silently
transfer to a newer world. RESET, LAND and 210000 ms, all mission oracles and
negative tests are unchanged. #701 remains Draft; #665 remains open.
