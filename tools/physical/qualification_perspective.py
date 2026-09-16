#!/usr/bin/env python3
"""Bind the physical qualification Robot Window to its exact Webots perspective.

The underlying launcher remains the authority boundary.  This module only wraps
its ephemeral Robot Window preparation so the final per-session world has the
R2025a `.<completeBaseName>.wbproj` companion required for automatic Robot Window
opening.  Importing this module starts no process and creates no physical
authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any

import launch_physical_qualification as launcher

ROOT = Path(__file__).resolve().parents[2]
PERSPECTIVE_TEMPLATE = ROOT / "tools" / "physical" / "qualification_world.wbproj"
EXPECTED_PERSPECTIVE = (
    "Webots Project File version R2025a\n"
    "robotWindow: Crazyflie WebeeBlocks\n"
)
_ORIGINAL_PREPARE = launcher.prepare_ephemeral_robot_window


class QualificationPerspectiveError(RuntimeError):
    """The exact R2025a Robot Window perspective cannot be established."""


def perspective_path_for_world(world_path: Path) -> Path:
    world_path = world_path.resolve()
    if world_path.suffix != ".wbt" or not world_path.name[:-4]:
        raise QualificationPerspectiveError("qualification world must have a non-empty .wbt basename")
    # Webots R2025a uses .<completeBaseName>.wbproj.  Ephemeral qualification
    # worlds intentionally begin with '.', so their exact perspective begins
    # with two dots (for example `..webeeblocks-physical-<id>.wbproj`).
    complete_base_name = world_path.name[:-4]
    return world_path.with_name("." + complete_base_name + ".wbproj")


def verify_perspective_template(path: Path = PERSPECTIVE_TEMPLATE) -> None:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise QualificationPerspectiveError("qualification perspective template is unavailable") from exc
    if text != EXPECTED_PERSPECTIVE:
        raise QualificationPerspectiveError(
            "qualification perspective must be exact R2025a Robot Window binding"
        )


@dataclass(slots=True)
class PerspectiveBoundEphemeral:
    """Lifecycle-bound proxy for one launcher ephemeral world/perspective pair."""

    inner: Any
    perspective_path: Path

    @property
    def plugin_dir(self) -> Path:
        return self.inner.plugin_dir

    @property
    def world_path(self) -> Path:
        return self.inner.world_path

    def close(self) -> None:
        try:
            self.inner.close()
        finally:
            self.perspective_path.unlink(missing_ok=True)


def _bind_perspective(inner: Any, *, template: Path = PERSPECTIVE_TEMPLATE) -> PerspectiveBoundEphemeral:
    perspective_path = perspective_path_for_world(inner.world_path)
    try:
        verify_perspective_template(template)
        if perspective_path.exists():
            raise QualificationPerspectiveError("ephemeral qualification perspective path collision")
        shutil.copy2(template, perspective_path)
        if perspective_path.read_text(encoding="utf-8") != EXPECTED_PERSPECTIVE:
            raise QualificationPerspectiveError("ephemeral qualification perspective copy is not exact")
        return PerspectiveBoundEphemeral(inner=inner, perspective_path=perspective_path)
    except BaseException:
        perspective_path.unlink(missing_ok=True)
        inner.close()
        raise


def prepare_ephemeral_robot_window_with_perspective(*args: object, **kwargs: object) -> PerspectiveBoundEphemeral:
    inner = _ORIGINAL_PREPARE(*args, **kwargs)
    return _bind_perspective(inner)


def install() -> None:
    current = launcher.prepare_ephemeral_robot_window
    if current is prepare_ephemeral_robot_window_with_perspective:
        return
    if current is not _ORIGINAL_PREPARE:
        raise QualificationPerspectiveError("qualification Robot Window preparation was already replaced")
    launcher.prepare_ephemeral_robot_window = prepare_ephemeral_robot_window_with_perspective


def self_test() -> None:
    """Exercise the real ephemeral launcher seam without Webots, Crazyradio or authority."""

    verify_perspective_template()
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        robot_windows = root / "plugins" / "robot_windows"
        source = robot_windows / "blockly_v2"
        source.mkdir(parents=True)
        (source / "main.js").write_text("// main\n", encoding="utf-8")
        (source / "physical_preflight_runtime.js").write_text("// preflight\n", encoding="utf-8")
        (source / "blockly_v2.html").write_text(
            '<html><body><script src="physical_preflight_runtime.js"></script></body></html>\n',
            encoding="utf-8",
        )
        worlds = root / "worlds"
        worlds.mkdir()
        world = worlds / "qualification-source.wbt"
        world.write_text('Robot { window "blockly_v2" }\n', encoding="utf-8")
        helper = root / "helper.js"
        helper.write_text("// helper\n", encoding="utf-8")
        bootstrap = {
            "baseUrl": "http://127.0.0.1:43117",
            "token": "capability-token",
            "preflightResponderToken": "responder-token",
            "executionAuthority": False,
        }
        ephemeral = prepare_ephemeral_robot_window_with_perspective(
            source_plugin=source,
            source_world=world,
            helper_script=helper,
            launcher_base_url="http://127.0.0.1:42000",
            launcher_token="launcher-token",
            host_bootstrap=bootstrap,
        )
        generated_world = ephemeral.world_path
        generated_plugin = ephemeral.plugin_dir
        generated_perspective = ephemeral.perspective_path
        expected_path = perspective_path_for_world(generated_world)
        if generated_perspective != expected_path:
            raise QualificationPerspectiveError("final ephemeral world lost exact Webots perspective naming")
        if generated_perspective.name != "." + generated_world.name[:-4] + ".wbproj":
            raise QualificationPerspectiveError("final perspective does not use complete world basename")
        if generated_perspective.read_text(encoding="utf-8") != EXPECTED_PERSPECTIVE:
            raise QualificationPerspectiveError("final ephemeral perspective lost Robot Window binding")
        ephemeral.close()
        if generated_world.exists() or generated_plugin.exists() or generated_perspective.exists():
            raise QualificationPerspectiveError("ephemeral world/perspective/plugin lifecycle cleanup failed")

        bad_template = root / "bad.wbproj"
        bad_template.write_text("Webots Project File version R2025a\n", encoding="utf-8")
        inner = _ORIGINAL_PREPARE(
            source_plugin=source,
            source_world=world,
            helper_script=helper,
            launcher_base_url="http://127.0.0.1:42000",
            launcher_token="launcher-token",
            host_bootstrap=bootstrap,
        )
        bad_world = inner.world_path
        bad_plugin = inner.plugin_dir
        bad_perspective = perspective_path_for_world(bad_world)
        try:
            _bind_perspective(inner, template=bad_template)
        except QualificationPerspectiveError:
            pass
        else:
            raise QualificationPerspectiveError("invalid perspective template was accepted")
        if bad_world.exists() or bad_plugin.exists() or bad_perspective.exists():
            raise QualificationPerspectiveError("failed perspective binding did not clean ephemeral paths")


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        if args == ["--self-test"]:
            self_test()
            print("PASS: exact R2025a ephemeral qualification perspective lifecycle verified")
            return 0
        verify_perspective_template()
        install()
        return launcher.main(args)
    except QualificationPerspectiveError as exc:
        print("FAIL: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
