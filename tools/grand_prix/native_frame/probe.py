"""Isolated Webots controller for the R2025a physics-frame experiment."""
import ctypes as c
import json
import math
import os
from pathlib import Path
from time import perf_counter_ns

from controller import Supervisor
from controller.wb import wb


class Contact(c.Structure):
    _fields_ = [
        ('point', c.c_double * 3),
        ('node_id', c.c_int32),
        ('padding', c.c_int32),
    ]


class Frame(c.Structure):
    _fields_ = [
        ('time_ms', c.c_double),
        ('incarnation', c.c_ubyte * 16),
        ('supervisor_id', c.c_int32),
        ('solid_id', c.c_int32),
        ('position', c.c_double * 3),
        ('orientation', c.c_double * 9),
        ('velocity', c.c_double * 6),
        ('contact_count', c.c_int32),
        ('contacts', Contact * 128),
    ]


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def bind_frame_api():
    request = wb.wb_supervisor_physics_frame_request
    request.argtypes = [c.c_int32]
    request.restype = c.c_bool
    read = wb.wb_supervisor_physics_frame_read
    read.argtypes = [c.POINTER(Frame)]
    read.restype = c.c_bool
    return request, read


def official_observation(node):
    return (
        list(node.getPosition()),
        list(node.getOrientation()),
        list(node.getVelocity()),
        [(list(contact.point), contact.node_id) for contact in node.getContactPoints(True)],
    )


def compact_observation(frame, robot, solid_id, supervisor_id):
    require(frame.solid_id == solid_id and frame.supervisor_id == supervisor_id,
            'physics-frame identity mismatch')
    require(abs(frame.time_ms - 1000 * robot.getTime()) < 1e-6,
            'physics-frame clock mismatch')
    require(0 <= frame.contact_count <= len(frame.contacts), 'invalid contact count')
    require(any(frame.incarnation), 'missing observation incarnation')
    observation = (
        list(frame.position), list(frame.orientation), list(frame.velocity),
        [(list(contact.point), contact.node_id) for contact in frame.contacts[:frame.contact_count]],
    )
    require(all(math.isfinite(x) for vector in observation[:3] for x in vector) and
            all(math.isfinite(x) and node_id > 0 for point, node_id in observation[3] for x in point),
            'invalid physics-frame coordinates or contact identity')
    return observation


def verify_rejections(robot, target, target_id, request, read, frame, incarnation):
    require(not read(frame), 'a frame was read twice')
    require(not request(0), 'invalid node accepted by Controller')
    require(robot.step(8) != -1 and not read(frame), 'unrequested frame')
    require(request(target_id), 'unable to queue long-step probe')
    require(robot.step(16) != -1 and not read(frame), 'frame accepted after long step')
    require(request(2**31 - 1), 'unable to queue missing-node probe')
    require(robot.step(8) != -1 and not read(frame), 'missing node yielded a frame')
    require(request(target_id), 'unable to queue immediate-message probe')
    require(not read(frame), 'queued request exposed old data')
    target.getPosition()
    require(not read(frame), 'immediate RPC yielded a frame')
    require(robot.step(8) != -1 and read(frame), 'immediate RPC consumed pending request')
    require(bytes(frame.incarnation) == incarnation, 'ordinary step changed incarnation')


def main():
    mode = os.environ['WEEBEE_FRAME_MODE']
    steps = int(os.environ['WEEBEE_FRAME_STEPS'])
    output = Path(os.environ['WEEBEE_FRAME_RESULT'])
    robot = Supervisor()
    require(robot.getBasicTimeStep() == 8, 'unexpected physical step')
    target = robot.getFromDef('TARGET')
    require(target is not None, 'missing native target')
    target_id, supervisor_id = target.getId(), robot.getSelf().getId()
    require(target_id > 0 and supervisor_id > 0, 'invalid native node ids')
    frame = Frame()
    request, read = bind_frame_api() if mode != 'baseline' else (None, None)
    times, observations = [], []
    incarnation = None
    start_time_ms = round(1000 * robot.getTime())

    # The same world, with no controller on the target, is used for all modes.
    # This stimulus produces both moving samples and real ODE contacts.
    target.setVelocity([0.07, 0.02, 0., 0., 0., 0.11])
    for index in range(steps):
        begin = perf_counter_ns()
        if request:
            require(request(target_id), 'frame request refused')
        require(robot.step(8) != -1, 'engine exited before all requested steps')
        step_end = perf_counter_ns()
        require(abs(1000 * robot.getTime() - (start_time_ms + 8 * (index + 1))) < 1e-6,
                'skipped or repeated physical step')
        if read:
            require(read(frame), 'missing fresh native frame')
            if incarnation is None:
                incarnation = bytes(frame.incarnation)
            require(bytes(frame.incarnation) == incarnation, 'observation incarnation changed')
            observation = compact_observation(frame, robot, target_id, supervisor_id)
            if mode == 'shadow':
                require(observation == official_observation(target),
                        f'same-step Supervisor mismatch at {robot.getTime():.3f}s')
        else:
            observation = official_observation(target)
        done = perf_counter_ns()
        times.append((begin, step_end, done))
        observations.append(observation)

    contacts = [contact for observation in observations for contact in observation[3]]
    child_id = robot.getFromDef('CONTACT_CHILD').getId()
    descendant_samples = sum(node_id == child_id for _, node_id in contacts)
    require(descendant_samples > 0 and any(not observation[3] for observation in observations),
            'fixture did not exercise empty and descendant-contact observations')
    if mode == 'shadow':
        verify_rejections(robot, target, target_id, request, read, frame, incarnation)

    output.write_text(json.dumps({
        'mode': mode, 'steps': steps, 'start_sim_ms': start_time_ms,
        'supervisor_id': supervisor_id, 'target_id': target_id, 'child_id': child_id,
        'descendant_contacts': descendant_samples,
        'timings_ns': times, 'observations': observations,
    }, allow_nan=False), encoding='utf-8')
    robot.simulationQuit(0)


if __name__ == '__main__':
    main()
