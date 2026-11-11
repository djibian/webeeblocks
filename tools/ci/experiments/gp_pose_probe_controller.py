"""Temporary evaluator test-controller wrapper ONLY. Never a production controller.

This controller occupies the exact SAME evaluator slot as the canonical
existing native witness. It imports that witness and runs its original tests.
After each historical NativeRouteEvaluator.tick returns, it observes already
sampled values, then optionally overwrites a single presentation-only mmap.
No extra Webots step, Supervisor call, publication ACK or oracle changes.
"""
import atexit
import json
import os
from pathlib import Path
import sys
import traceback

sys.path.insert(0, os.environ['GP_ROUTE_EVALUATOR_SOURCE'])
from controller import Supervisor
from tools.ci.fixtures.gp_route_evaluator_probe import witness
from tools.grand_prix.evaluator_publisher_v2 import NativeRouteEvaluator
from tools.ci.experiments.pose_mailbox_v1 import PoseWriter

writer = PoseWriter(os.environ['GP_POSE_MAILBOX_PATH']) if os.getenv('GP_POSE_MAILBOX_PATH') else None
observations = []
original_tick = NativeRouteEvaluator.tick


def tick_observed(self):
    result = original_tick(self)  # Historical native safety/flight authority.
    sample, context = self.observation, self._context
    if sample is not None:
        kin = sample.kinematics
        row = dict(time_ms=self._last_ms, attempt=context.attempt if context else None,
                   phase=self.phase, error=self.last_error,
                   position=list(kin.position), orientation=list(kin.orientation),
                   velocity=list(kin.velocity), ranges_m=list(sample.flight.ranges_m),
                   contact_count=len(sample.contacts.points))
    else:
        row = dict(time_ms=self._last_ms, attempt=context.attempt if context else None,
                   phase=self.phase, error=self.last_error, position=None,
                   orientation=None, velocity=None, ranges_m=None,
                   contact_count=None)
    # The evidence list is diagnostic only, finite, and shared by ALL arms,
    # including the no-publication baseline. Never a presentation queue.
    if len(observations) >= 4096:
        raise RuntimeError('diagnostic evidence buffer exceeded')
    observations.append(row)
    if writer is not None:
        writer.publish(context, sample)
    return result


def finish():
    output = Path(os.environ['GP_POSE_PROBE_OUT'])
    output.write_text(json.dumps(dict(samples=observations,
                                      publisher=(writer.summary() if writer else None)),
                                 allow_nan=False, sort_keys=True) + '\n')
    if writer:
        writer.close()


NativeRouteEvaluator.tick = tick_observed
atexit.register(finish)

if __name__ == '__main__':
    try:
        witness()
    except Exception:
        traceback.print_exc()
        Supervisor().simulationQuit(1)
        raise
