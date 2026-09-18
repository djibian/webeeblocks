# Windows native file-dialog foreground boundary

Issue #462 is a Windows 11 Firefox presentation boundary, not a project-file semantics defect. Human checkpoint #472 established that the native Open / Save As picker can remain behind the browser/Webots window even when the correct external foreground HWND is supplied as the dialog owner. Once the picker is manually reached, the established `.wbb` Open/Save behavior remains usable.

## Causal boundary

Qt 6.5.3 can execute its native `IFileDialog::Show(owner)` through a separate `QWindowsDialogThread`. Therefore attaching or hooking only the broker/provider GUI thread does not establish control over the input/activation state of the thread that actually owns the shell picker.

The Windows provider consequently bypasses Qt's threaded native-file-dialog helper for Open / Save As and uses `IFileOpenDialog` / `IFileSaveDialog` directly. The contract is:

- capture the external foreground HWND only if it belongs to another process;
- call `IFileDialog::Show(owner)` synchronously on the same broker thread whose activation relationship is controlled;
- while that captured owner is still foreground, temporarily join the dialog thread to the owner's input queue with `AttachThreadInput`;
- install `WH_CBT` on that same dialog thread and accept only the broker-process `#32770` picker whose owner is the captured external HWND;
- use normal, non-`TOPMOST` Z-order and request foreground activation for that exact picker;
- always unhook and detach through RAII;
- treat `ERROR_CANCELLED` as neutral user cancellation rather than an I/O failure;
- preserve the non-Windows Qt path and all opaque-reference, validation, atomic-write and same-file Save semantics.

This boundary intentionally rejects two earlier non-causal repairs: `Qt::WindowStaysOnTopHint`, which does not reach the native shell picker, and input/hook control on the provider thread while Qt shows the picker on a different helper thread.

## Evidence boundary

Canonical Windows build/package CI must establish that the direct COM provider and its explicit `ole32`/`uuid` link dependencies compile and package on the supported R2025a Windows path. That machine evidence does not prove desktop z-order. Foreground presentation remains a real Windows Firefox acceptance boundary and requires an exact integrated artifact checkpoint before #462 can be considered resolved.
