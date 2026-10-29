# Qt665 — repeated SIGTERM after GUI Cancel, native Qt source-extracted negative

**Verified effect, not product repair.** Experimental execution HEAD `da065269294765e66eaadb6c5712acf3f143a4b3`, [NON-GATE #40915363063](https://github.com/djibian/webeeblocks/actions/runs/40915363063) **completed/success**, original [artifact 12916355681](https://github.com/djibian/webeeblocks/actions/runs/40915363063/artifacts/12916355681) downloaded and CRC/sha256 verified (**5/5 ZIP members**, **16,194 bytes**, SHA256 `d75969404830733181631772dfedbcd6901bfa7ca66e747d266a52526750a7ae`). Upstream Webots exact `c6793d8f7230a311c4bc2a3101d9f1a8bc0aa01b`; POSIX patched source SHA256 `e9a6d9365011e55fe853fea1026d9b83be097feb4ba9a4759639fe75796f54b8`. Tests use actual Qt6.5.3 Xvfb, verbatim signal handler + QSocketNotifier fragment from that source, a QWidget close-event veto double and queued method call model. They **do not** run Webots GUI full nor a world.

```
NORMAL: AFTER_EXIT MODE=normal SENT=1 REQUESTS=1 CLOSES=1 VISIBLE=0 RC=0
VETO:   BEFORE_EXIT MODE=veto SENT=2 REQUESTS=1 CLOSES=1 VISIBLE=1
        CANCEL_SECOND_SIGTERM_SWALLOWED=OBSERVED
```

The veto test sends **two real SIGTERM** (POSIX `raise`), the first close is ignored (Webots source `WbMainWindow::proposeToSaveWorld` can return false on QMessageBox::Cancel), and the second signal cannot produce another Qt request because the patch permanently disabled the notifier. A one-shot `quitRequested` flag is correct for coalescing during the close, **not** automatically for the case when the close was refused. The initial run [40914853969](https://github.com/djibian/webeeblocks/actions/runs/40914853969) failed because its assertion happened **after harness teardown**. The corrected test moves the observation before teardown; it does not alter the patch source, actual handler, notifier or veto logic. The trace prints one literal backslash-n before the marker, a formatting artifact not interpreted as an event.

[GitHub #665 detailed independent boundary / NO_GO for adoption](https://github.com/djibian/webeeblocks/issues/665#issuecomment-6502928385). This is not a NO_GO on the already independently qualified #701 pre-READY Qt improvements, nor a challenge to the 20 native Webots mission oracles. **It is a decisive missing cancellation/retry acceptance criterion** for POSIX patch product adoption.

Next version must preserve the original user choice, no calls to Qt/allocator in async handler, lifetime-of-process FDs, bounded drain and one active close request at a time. Test one accepted close, Cancel then another SIGTERM, and bursts during an active modal dialog under real Qt and ideally installed Webots. Do not force-exit on Cancel or relax mission predicates. #637, #665 root cause, real crash and Windows remain UNPROVEN.

**This workflow is intentionally now manual-only.** Its exact useful source/Qt check is already preserved by the immutable run; do not automatically repeat it on documentation pushes.
