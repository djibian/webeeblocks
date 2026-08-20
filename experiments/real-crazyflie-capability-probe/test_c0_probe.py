import ast
import importlib.util
import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("c0_probe", HERE / "c0_probe.py")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class C0ProbeTests(unittest.TestCase):
    def test_mock_probe_succeeds_and_always_closes(self):
        port = MODULE.MockReadOnlyPort()
        report = MODULE.run_probe(
            port,
            uri=None,
            scan=True,
            connection_timeout_s=1,
            telemetry_timeout_s=1,
            mission=MODULE.DEFAULT_MISSION,
            mode="mock",
        )
        self.assertTrue(report.flow_v2_detected)
        self.assertTrue(report.multiranger_detected)
        self.assertTrue(report.telemetry_complete)
        self.assertFalse(report.physical_proof)
        self.assertTrue(port.closed)
        self.assertEqual(port.actions[-1], "close")

    def test_missing_deck_fails_before_telemetry_and_closes(self):
        port = MODULE.MockReadOnlyPort(decks=["bcFlow2"])
        with self.assertRaisesRegex(MODULE.ProbeError, "Multi-ranger"):
            MODULE.run_probe(
                port, uri="radio://mock", scan=False,
                connection_timeout_s=1, telemetry_timeout_s=1,
                mission=MODULE.DEFAULT_MISSION, mode="mock")
        self.assertNotIn("read_telemetry", port.actions)
        self.assertTrue(port.closed)

    def test_connection_failure_closes(self):
        port = MODULE.MockReadOnlyPort(connect_error=MODULE.ProbeError("radio lost"))
        with self.assertRaisesRegex(MODULE.ProbeError, "radio lost"):
            MODULE.run_probe(
                port, uri="radio://mock", scan=False,
                connection_timeout_s=1, telemetry_timeout_s=1,
                mission=MODULE.DEFAULT_MISSION, mode="mock")
        self.assertTrue(port.closed)

    def test_incomplete_telemetry_fails_closed(self):
        telemetry = MODULE._mock_telemetry()
        del telemetry["range.left"]
        port = MODULE.MockReadOnlyPort(telemetry=telemetry)
        with self.assertRaisesRegex(MODULE.ProbeError, "telemetry"):
            MODULE.run_probe(
                port, uri="radio://mock", scan=False,
                connection_timeout_s=1, telemetry_timeout_s=1,
                mission=MODULE.DEFAULT_MISSION, mode="mock")
        self.assertTrue(port.closed)

    def test_mapping_is_display_only_and_rejects_unknown_command(self):
        mapping = MODULE.compile_display_only_mapping(MODULE.DEFAULT_MISSION)
        self.assertEqual([m["semantic"]["op"] for m in mapping], ["TAKEOFF", "FORWARD", "TURN", "LAND"])
        with self.assertRaisesRegex(MODULE.ProbeError, "unsupported"):
            MODULE.compile_display_only_mapping([{"op": "MOTOR_RAW"}])

    def test_source_has_no_motorized_import_or_call_path(self):
        source = (HERE / "c0_probe.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        forbidden_import_fragments = (
            "motion_commander", "position_hl_commander", "high_level_commander",
        )
        forbidden_call_fragments = (
            "send_setpoint", "send_hover_setpoint", "send_position_setpoint",
            "send_velocity_world_setpoint", "send_zdistance_setpoint",
            "send_stop_setpoint", "send_notify_setpoint_stop",
            "arming_request", "take_off", "land", "forward", "back",
            "left", "right", "up", "down", "turn_left", "turn_right",
        )

        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                else:
                    names = [node.module or ""]
                for name in names:
                    self.assertFalse(any(fragment in name.lower() for fragment in forbidden_import_fragments), name)
            if isinstance(node, ast.Call):
                func = node.func
                parts = []
                while isinstance(func, ast.Attribute):
                    parts.append(func.attr)
                    func = func.value
                if isinstance(func, ast.Name):
                    parts.append(func.id)
                call_name = ".".join(reversed(parts)).lower()
                self.assertFalse(any(fragment in call_name for fragment in forbidden_call_fragments), call_name)

    def test_cflib_adapter_public_surface_is_read_only(self):
        public = {name for name in dir(MODULE.CflibReadOnlyPort) if not name.startswith("_")}
        self.assertEqual(public, {"close", "connect", "deck_names", "init_drivers", "read_telemetry", "scan_uris"})


if __name__ == "__main__":
    unittest.main()
