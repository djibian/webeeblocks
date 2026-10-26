# Native Webots Qt lifetime discriminator for #665 (diagnostic only)

**Status: GDB/Webots execution UNQUALIFIED.** This is an opt-in probe, not
a completed experiment or a repair. It extends the prior miniature Qt
lifetime evidence at commit 32147831 without rerunning it.

The historical archive 12533122680 contains a SIGSEGV backtrace from
QProgressBar::maximum -> QProgressDialog::setValue ->
WbMainWindow::setWorldLoadingProgress, and its capture metadata says
raw_core_uploaded=false. The retained backtrace cannot reveal the
identity and stack of a completed, nested destructor. Instrument the
live Webots process to obtain that missing evidence.

## Mechanism of this probe

The GDB Python script records QProgressDialog::setValue entry/return
identities, its matching progress bar via QProgressBar::setValue, bar
maximum calls, actual dialog/bar destructor entries and SIGSEGV stop.
When the exact active dialog or bar is destroyed before the matching
setValue returns, it records the immediate destructor stack. GDB does
not change Webots code, does not bypass negative oracles and does not
suppress SIGSEGV. GDB scheduling and breakpoints CAN perturb races.
Linux x86_64 System V only, using RDI for the C++ object pointer.

## Bounded diagnostic invocation

Use the same R2025a container/image, original world, local assets,
Qt libraries, display/QPA environment, and the same command arguments.
First reconstruct the environment set by the Webots shell wrapper:
the target of GDB must be the actual webots-bin ELF rather than the
shell launcher. The example world path is a placeholder, not a runnable
CI replacement:

    gdb -q --batch \
      -ex 'set pagination off' \
      -ex 'source /workspace/qt_lifetime_gdb.py' \
      -ex 'info breakpoints' \
      -ex run \
      -ex 'info breakpoints' \
      --args /usr/local/webots/bin/webots-bin \
        --stdout --stderr --batch --mode=fast --no-rendering /path/to/same.wbt \
      > qt-665-gdb.log 2>&1

The expected Qt Widgets ELF SHA256 is
868b516dde6d020badc7243facd48f880b0d606c76e46e50427c1c744a2c1024.
Also verify Qt Core/Gui and the exact Webots executable, container digest,
world, QPA and launcher. Run one bounded diagnostic instance, not a
blind native CI campaign. Keep raw logs private until reviewed.

Inspect the final 'info breakpoints' to confirm actual symbol
resolution; an installed pending breakpoint is not evidence of
coverage. Records prefixed WBB_QT665 contain JSON. A matching
dialog_destroyed_within_setvalue or bar_destroyed_within_setvalue
is a real lifetime witness in THAT instrumented process. Correlate
it with any SIGSEGV, the same object address, and its deleting callback
before attributing #665's historical crash. A run without a matching
destructor does not refute the hypothesis, and no debugger result
alone proves that an upstream repair works.

## Repair boundary

Webots R2025a WbMainWindow.cpp directly deletes its modal
QProgressDialog and invokes setValue, which internally processes
events. If deletion is witnessed during that frame, repair the
Webots window-level lifetime contract: retire the dialog only after
the outermost progress call, taking care of cancellation, repeated
events and new-world creation. A bare deleteLater(), changing
modal behavior, --minimize or --no-rendering is not independently
proved sufficient. Validate any actual repair by controlled A/B
native Webots evidence plus the unchanged mission negative oracles
and an independent V5 review.

This file itself is **not qualified by GDB execution**: only Python
syntax/offline reasoning are available in the current environment.
#665 stays OPEN / cause UNPROVEN. #637/#700 remain separate.
