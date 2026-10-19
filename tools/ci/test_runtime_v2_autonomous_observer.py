"""Falsify diagnostic retention without importing Webots or changing physics."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.ci.run_progression_autonomous_mission import observed_world, validate_observer_trace

spec = importlib.util.spec_from_file_location(
    "autonomous_reset_observer", ROOT / "tools/ci/fixtures/autonomous_reset_observer.py")
observer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(observer)


class ReadOnlyVehicle:
    """No mutation/command API exists on this deliberately small double."""
    def __init__(self, supervisor):
        self.supervisor = supervisor

    def getField(self, name):
        assert name == "customData"
        return SimpleNamespace(getSFString=lambda: self.supervisor.state["custom_data"])

    def getPosition(self):
        return self.supervisor.state["position"]

    def getOrientation(self):
        return self.supervisor.state["orientation"]

    def getVelocity(self):
        return self.supervisor.state["velocity"]

    def getContactPoints(self, *, includeDescendants):
        assert includeDescendants is True
        return [SimpleNamespace(**contact) for contact in self.supervisor.state["contacts"]]


class ReadOnlySupervisor:
    def __init__(self, samples):
        self.samples = iter(samples)
        self.state = None

    def getFromDef(self, name):
        assert name == "CI_AUTONOMOUS_CRAZYFLIE"
        return ReadOnlyVehicle(self)

    def getBasicTimeStep(self):
        return 32

    def step(self, step):
        assert step == 32
        self.state = next(self.samples, None)
        return 0 if self.state is not None else -1

    def getTime(self):
        return self.state["time"]


def state(time, position, velocity, contacts=(), custom_data="WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 7"):
    return dict(time=time, position=position, velocity=velocity, contacts=list(contacts),
                custom_data=custom_data, orientation=[1., 0., 0., 0., 1., 0., 0., 0., 1.])


class ObserverTests(unittest.TestCase):
    def test_world_change_is_only_def_window_and_empty_observer(self):
        source = (ROOT / "worlds/crazyflie_runtime_v2.wbt").read_text()
        world = observed_world(source)
        original, appended = world.rsplit('\nRobot {\n', 1)
        self.assertEqual(original.replace('DEF CI_AUTONOMOUS_CRAZYFLIE Crazyflie {', 'Crazyflie {', 1)
                         .replace('window "autonomous_probe"', 'window "blockly_v2"', 1), source)
        self.assertIn('controller "ci_autonomous_reset_observer"', appended)
        for forbidden in ('children', 'boundingObject', 'physics', 'translation', 'rotation'):
            self.assertNotIn(forbidden, appended)
        for bad_source in (source.replace('Crazyflie {\n', 'Crazyflie  {\n'), source + source):
            with self.assertRaises(ValueError):
                observed_world(bad_source)

    def test_keeps_collision_teleport_motion_and_partial_crash_trace(self):
        samples = [
            state(10., [.753434, -2.218063, .499283], [0., 1., -.5, .1, .2, .3],
                  [dict(point=[.75, -2.22, .5], node_id=42)]),
            state(10.032, [0., 0., .015], [0., 0., 0., .1, 0., 0.]),
            state(10.064, [0., 0., .015], [0.] * 6,
                  custom_data="WEBEEBLOCKS_ACTIVITY_ATTEMPT_V1 8"),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace.jsonl"
            observer.record(ReadOnlySupervisor(samples), path)
            validate_observer_trace(path, required_attempts=(7, 8))
            records = [json.loads(line) for line in path.read_text().splitlines()]
            for expected, actual in zip(samples, records[1:]):
                for key in expected:
                    self.assertEqual(expected[key], actual[key])

            class InterruptedSupervisor(ReadOnlySupervisor):
                def step(self, step):
                    if self.state is not None and self.state["time"] == 10.032:
                        # A failed simulation must leave the preceding lines intact.
                        partial = [json.loads(line) for line in path.read_text().splitlines()]
                        self_test.assertEqual(len(partial), 3)
                        raise RuntimeError("native failure sentinel")
                    return super().step(step)

            self_test = self
            with self.assertRaisesRegex(RuntimeError, "native failure sentinel"):
                observer.record(InterruptedSupervisor(samples), path)
            validate_observer_trace(path)
            self.assertEqual(len(path.read_text().splitlines()), 3)

    def test_nonfinite_evidence_is_preserved_without_forging_zero(self):
        sample = state(.032, [float('nan'), float('inf'), -float('inf')], [0.] * 6,
                       [dict(point=[float('nan'), 0., 0.], node_id=43)])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace.jsonl"
            observer.record(ReadOnlySupervisor([sample, state(.064, [0.] * 3, [0.] * 6)]), path)
            records = [json.loads(line, parse_constant=lambda x: self.fail(x))
                       for line in path.read_text().splitlines()]
            self.assertEqual(records[1]["position"], ['nan', 'inf', '-inf'])
            self.assertEqual(records[1]["contacts"][0]["point"][0], 'nan')
            validate_observer_trace(path)

    def test_missing_incomplete_and_nonmonotonic_traces_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace.jsonl"
            with self.assertRaises(FileNotFoundError):
                validate_observer_trace(path)
            observer.record(ReadOnlySupervisor([state(.032, [0.] * 3, [0.] * 6),
                                                state(.064, [0.] * 3, [0.] * 6)]), path)
            valid = path.read_text().splitlines()
            with self.assertRaisesRegex(ValueError, "missing observations"):
                validate_observer_trace(path, required_attempts=(7, 8))
            second = json.loads(valid[2])
            short = dict(second, velocity=[0.] * 3)
            backwards = dict(second, time=.032)
            for lines in ([], valid[:1], valid[:2], valid[:2] + [json.dumps(short)],
                          valid[:2] + [json.dumps(backwards)], valid + ['{"type":']):
                path.write_text('\n'.join(lines) + '\n')
                with self.assertRaises((ValueError, StopIteration)):
                    validate_observer_trace(path)


if __name__ == "__main__":
    unittest.main()
