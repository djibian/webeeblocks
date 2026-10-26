# #665 — controlled Qt 6.5.3 lifetime intervention

Base: `aa8e1556cff45bfd5bde1b29593afabe5522e486` (2026-10-26).
AGENTS V5 / vision / roadmap blobs: `c00e855a431b1b83382ba333b0db490a8c330e53`,
`121409284eba687941c9f1f195077007c3352855`,
`e150cf29129304e54ce3a2eb7cd8208dbf648876`.

## Result

**Demonstrated on the exact Qt Widgets library of the archived Webots core:**
deleting a modal QProgressDialog in an event dispatched by its own `setValue`
destroys both dialogue and progress bar before that call returns. A deferred
deletion and a nonmodal control do not have that lifetime order.

This is a controlled sufficient mechanism, **not proof that this destruction
occurred in the historical Webots process**. None of the three runs SIGSEGVed:
all returned zero. Surviving an access after destruction is not lifetime safety.
No memory was overwritten or allocator state manipulated to force a crash.

| Intervention | Event dispatched within setValue | Bar destroyed before return |
| --- | --- | --- |
| modal, direct delete | yes, stack retained | yes |
| modal, deleteLater | yes, stack retained | no |
| nonmodal, direct delete | no | no |

The event is intentionally supplied by this miniature application. It is not
claimed to be a Webots download callback. `minimumDuration=0` and `forceShow`
establish the internal shown state deterministically; they are experimental
controls, not changes proposed for Webots or its CI. QObject destruction
signals establish the two identities. QPointer observes the surviving lifetime.

## Binary and source link

The locally available native R2025a Widgets library SHA256 is
`868b516dde6d020badc7243facd48f880b0d606c76e46e50427c1c744a2c1024`.
It equals the original pre-debugger sysroot manifest entry in artifact
[12533122680](https://github.com/djibian/webeeblocks/actions/runs/40026927733/artifacts/12533122680).
Core and Gui hashes were also compared; see `core-qt-provenance.json` and
`final/provenance.json`. The historical archive was already retained locally;
this experiment reads those retained bytes, not a newly downloaded raw core.
No raw core or memory dump is included here.

`qt-setvalue-disassembly.txt` removes reliance on source-version similarity:
the actual Widgets `setValue` at 0x3f8bf0 calls processEvents at 0x3f8d99,
returns at 0x3f8d9e, then branches to the bar load at 0x3f8c4f and maximum call
at 0x3f8c56. The historical frame returns to 0x3f8c5b (setValue + 0x6b),
immediately after this same maximum call. Both the nested event and subsequent
bar access are therefore present in the exact binary, not inferred from a tag.
This does not prove the historical call traversed the processEvents branch.

Primary sources independently read at exact references:

- [Qt 6.5.3 setValue](https://github.com/qt/qtbase/blob/v6.5.3/src/widgets/dialogs/qprogressdialog.cpp)
  has the same structure and explicitly warns about modal reentrancy.
- [R2025a WbMainWindow](https://github.com/cyberbotics/webots/blob/c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b/src/webots/gui/WbMainWindow.cpp)
  constructs the modal dialog, directly deletes it, and calls setValue followed
  by another processEvents. Minimized windows skip construction.
- [R2025a WbApplication](https://github.com/cyberbotics/webots/blob/c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b/src/webots/app/WbApplication.cpp)
  installs updateDownloadingProgress as progress callback; completion emits the
  delete signal. Cancellation and normal load completion also emit deletion.
  Which path, if any, destroyed the historical object is still unobserved.

## Reproduction

Use official R2025a headers/libraries and an available Qt 6.5.3 offscreen platform
plugin. This run uses the PySide6 Essentials 6.5.3 wheel's platform plugin with
the Webots Core/Gui/Widgets libraries (actual linked files retained in
`final/linked-libraries.txt`). This is **not** the CI Xvfb platform or full
Webots application; plugin, libc, allocator and host provenance remain scoped
to this intervention. The wheel does not replace Qt Widgets here.

```sh
python3 experiments/qt-progress-lifetime-665/run.py \
  --webots-home /path/to/R2025a/webots \
  --platform-plugins /path/to/qt-6.5.3/plugins/platforms \
  --out /new/output/directory
```

The runner compiles, runs three predefined contrasts once, checks destruction
order and the nested setValue stack, and retains stdout/stderr and provenance.
It fails closed on preparation or missing expected evidence. It does not run,
replace, rerun or exempt any product oracle. `final/` is the final acquisition;
the initial observation without backtrace and two failed plugin-path
preparations remain explicitly retained. The latter never entered QApplication.
The draft inherited from the interrupted workspace was inspected, then changed
and freshly compiled/executed here; no old stdout is treated as new evidence.

## Consequence and remaining discriminator

The reentrancy hypothesis is strengthened from source plausibility to an
observed lifetime violation with the exact library and two causal controls.
The next deep discriminator is still an actual Webots lifetime observation:
dialog/bar destruction inside an active setValue, with the deleting callback
stack, or a contrary observation identifying another invalidation mechanism.
An upstream lifecycle repair must be qualified at that layer; blindly adding
retries, changing renderer/oracles or treating `--minimize` as universal crash
eradication is unjustified.

#686 remains a bounded launcher mitigation and cannot inherit another HEAD's
CI/GO. #699 removes the outcome probe's external asset dependency but does not
repair object lifetime. #637/#700 LAND/RESET and #635 pedagogical acceptance
remain separate. #665 stays OPEN / ultimate historical cause UNPROVEN.
No product patch, CI Gate, independent GO, human test request or flight authority
is asserted by this evidence branch.
