"""Pure native-API fakes: fail-closed tests, NOT Webots R2025a qualification."""
from dataclasses import replace
import unittest
from tools.grand_prix.route_courses_v2 import plan_course, CoursePlan, reference_course
from tools.grand_prix.native_collider_contract_v2 import (
    NativeBox, required_box_names, canonical_native_boxes, verify_native_boxes,
)


class _Field:
    def __init__(self, value):
        self.value = value

    def getSFNode(self):
        return self.value

    def getSFBool(self):
        return self.value

    def getSFVec3f(self):
        return self.value

    def getSFVec2f(self):
        return self.value

    def getSFRotation(self):
        return self.value

    def getSFString(self):
        return self.value

    def getCount(self):
        return len(self.value)

    def getMFNode(self, i):
        return self.value[i]


class _Node:
    def __init__(self, def_name, kind, **fields):
        self.name, self.kind, self.fields = def_name, kind, fields
        self.position = fields.get('position')

    def getDef(self):
        return self.name

    def getTypeName(self):
        return self.kind

    def getBaseTypeName(self):
        return self.fields.get('_base', self.kind)

    def isProto(self):
        return self.fields.get('_proto', False)

    def getBaseNodeField(self, name):
        base_fields = self.fields.get('_base_fields', {})
        return _Field(base_fields[name]) if name in base_fields else None

    def getField(self, name):
        return _Field(self.fields[name]) if name in self.fields else None

    def getPosition(self):
        return self.position


class _Supervisor:
    def __init__(self, boxes):
        self.nodes = [self.solid(box) for box in boxes] + [_floor(), _vehicle()]

    @staticmethod
    def solid(box):
        physics = _Node(None, 'Box', size=box.size)
        visible = _Node(None, 'Box', size=box.size)
        shape = _Node(None, 'Shape', geometry=visible)
        return _Node(box.name, 'Solid',
                     position=tuple(float(f'{v:.6f}') for v in box.position),
                     boundingObject=physics, children=[shape], locked=True,
                     rotation=(0., 0., 1., 0.))

    def getRoot(self):
        return _Node(None, 'Root', children=self.nodes)

    def getFromDef(self, name):
        return next((n for n in self.nodes if n.getDef() == name), None)


def _plan_and_manifest():
    plan = plan_course(17, (2., 2.5, 3.), ('G', 'D'), 2)
    return plan, canonical_native_boxes(plan)


def _floor():
    return _Node(None, 'Floor', _base='Solid', _proto=True,
                 position=(0.,0.,0.), rotation=(0.,0.,1.,0.),
                 _base_fields={'locked': True, 'boundingObject':
                               _Node(None, 'Plane', size=(20.,20.))})

def _vehicle():
    return _Node(None, 'Crazyflie', _base='Robot', _proto=True,
                 name='Crazyflie WebeeBlocks', extensionSlot=[])


class NativeColliderContractTests(unittest.TestCase):
    def test_unreserved_physics_and_proto_wrappers_cannot_escape_inventory(self):
        plan, boxes = _plan_and_manifest()
        for placement in ('root', 'group', 'pose', 'slot', 'switch',
                          'physical-proto', 'group-proto', 'vehicle-slot',
                          'second-vehicle', 'second-floor', 'other-robot'):
            scene = _Supervisor(boxes)
            hidden = _Supervisor.solid(NativeBox(
                'UNRESERVED_EXTRA_DIRECT_ROOT', (0., 0., .65), (.1,.1,1.3)))
            if placement == 'root':
                node = hidden
            elif placement in ('group', 'pose'):
                node = _Node(None, placement.title(), children=[hidden])
            elif placement == 'slot':
                node = _Node(None, 'Slot', endPoint=hidden)
            elif placement == 'switch':
                node = _Node(None, 'Switch', choice=[hidden])
            elif placement == 'physical-proto':
                node = _Node(None, 'UnlistedObstacle', _base='Solid', _proto=True)
            elif placement == 'group-proto':
                node = _Node(None, 'OpaqueGroup', _base='Group', _proto=True,
                             _base_fields={'children': [hidden]})
            elif placement == 'vehicle-slot':
                scene.nodes[-1].fields['extensionSlot'] = [hidden]
                node = _Node(None, 'Pose', children=[])
            elif placement == 'second-vehicle':
                node = _vehicle()
            elif placement == 'second-floor':
                node = _floor()
            else:
                node = _Node(None, 'Robot')
            scene.nodes.append(node)
            with self.subTest(placement=placement), self.assertRaises(RuntimeError):
                verify_native_boxes(scene, plan, boxes)

    def test_legitimate_model_roots_and_nonphysical_decor_remain_admissible(self):
        plan, boxes = _plan_and_manifest()
        scene = _Supervisor(boxes)
        scene.nodes[-1].fields['extensionSlot'] = [
            _Node(None, 'Pose', children=[
                _Node(None, 'Shape', geometry=_Node(None, 'Box'))])]
        scene.nodes.extend([
            _Node('GP_ROUTE_EVALUATOR', 'Robot', children=[]),
            _Node(None, 'Group', children=[_Node(None, 'Pose', children=[])]),
        ])
        self.assertIsNone(verify_native_boxes(scene, plan, boxes))

    def test_missing_canonical_floor_or_vehicle_fails_closed(self):
        plan, boxes = _plan_and_manifest()
        for missing in ('Floor', 'Crazyflie'):
            scene = _Supervisor(boxes)
            scene.nodes = [node for node in scene.nodes if node.kind != missing]
            with self.subTest(missing=missing), self.assertRaisesRegex(
                    RuntimeError, 'missing required pinned scene model'):
                verify_native_boxes(scene, plan, boxes)

    def test_floor_allowance_does_not_admit_raised_box_or_incomplete_floor(self):
        plan, boxes = _plan_and_manifest()
        for mutation in ('raised', 'box', 'small', 'tilted', 'unlocked'):
            scene = _Supervisor(boxes)
            node = next(n for n in scene.nodes if n.kind == 'Floor')
            if mutation == 'raised':
                node.position = (0.,0.,.1)
            elif mutation == 'box':
                node.fields['_base_fields']['boundingObject'] = _Node(
                    None, 'Box', size=(20.,20.,.05))
            elif mutation == 'small':
                node.fields['_base_fields']['boundingObject'].fields['size'] = (1.,1.)
            elif mutation == 'tilted':
                node.fields['rotation'] = (1.,0.,0.,.1)
            else:
                node.fields['_base_fields']['locked'] = False
            with self.subTest(mutation=mutation), self.assertRaises(RuntimeError):
                verify_native_boxes(scene, plan, boxes)

    def test_full_manifest_and_authority_neutrality(self):
        plan, boxes = _plan_and_manifest()
        self.assertEqual(tuple(b.name for b in boxes), required_box_names(plan))
        self.assertIsNone(verify_native_boxes(_Supervisor(boxes), plan, boxes))
        self.assertEqual(len(boxes), 8 + 3*plan.count)

    def test_all_reference_courses_bind_actual_host_dimensions(self):
        # These are Python Supervisor fakes, NOT native R2025a measurements.
        for number in range(12):
            course = reference_course(number)
            boxes = canonical_native_boxes(course)
            with self.subTest(identifier=course.identifier):
                self.assertEqual(len(boxes), 8 + 3*course.count)
                self.assertEqual(tuple(b.name for b in boxes), required_box_names(course))
                self.assertIsNone(verify_native_boxes(_Supervisor(boxes), course, boxes))

    def test_rejects_self_consistent_forged_native_geometry(self):
        plan, boxes = _plan_and_manifest()
        # A fake scene can agree with a forged manifest but disagree with
        # the physical L, open H or terminal H specified by CoursePlan.
        for index in (0, 4, len(boxes)-1):
            box = boxes[index]
            for field in ('position', 'size'):
                with self.subTest(box=box.name, field=field):
                    if field == 'position':
                        forged_box = replace(box, position=(
                            box.position[0]+.002, *box.position[1:]))
                    else:
                        forged_box = replace(box, size=(
                            box.size[0]+.002, *box.size[1:]))
                    forged = boxes[:index] + (forged_box,) + boxes[index+1:]
                    with self.assertRaisesRegex(ValueError, 'canonical geometry'):
                        verify_native_boxes(_Supervisor(forged), plan, forged)

    def test_rejects_omitted_forged_or_noncanonical_manifests(self):
        plan, boxes = _plan_and_manifest()
        for manifest in (boxes[:-1], boxes[1:], boxes[:-1]+(boxes[0],),
                         boxes[:-1]+(replace(boxes[-1], name=boxes[0].name),),
                         boxes[:-1]+(replace(boxes[-1], size=(.04, 0., 1.)),),
                         boxes[:-1]+(replace(boxes[-1],
                                             position=(0., float('nan'), 1.)),)):
            with self.subTest(manifest=manifest[-1].name), self.assertRaises(ValueError):
                verify_native_boxes(_Supervisor(boxes), plan, manifest)
        forged = CoursePlan(plan.route, plan.gates[:1], 2)
        with self.assertRaises(ValueError):
            required_box_names(forged)
        with self.assertRaises(ValueError):
            required_box_names(None)

    def test_fails_closed_on_missing_extra_or_duplicate_physical_solids(self):
        plan, boxes = _plan_and_manifest()
        for mutation in ('missing', 'extra', 'duplicate',
                         'reserved-non-solid', 'reserved-wrapper-hidden-solid',
                         'reserved-wrapper-empty', 'reserved-unknown-pose',
                         'nested-extra',
                         'nested-pose-extra', 'attached-extra',
                         'decorative-hidden-solid', 'decorative-nested-solid',
                         'decorative-collider',
                         'decorative-pose', 'decorative-group'):
            scene = _Supervisor(boxes)
            if mutation == 'missing':
                scene.nodes.pop()
            elif mutation == 'extra':
                scene.nodes.append(_Supervisor.solid(
                    NativeBox('GP_V2_EXTRA', (0., 0., .65), (.1, .1, 1.3))))
            elif mutation == 'duplicate':
                scene.nodes.append(scene.nodes[0])
            elif mutation == 'reserved-non-solid':
                scene.nodes.append(_Node('GP_V2_L_0_0', 'Pose', children=[]))
            elif mutation == 'reserved-wrapper-hidden-solid':
                scene.nodes.append(_Node('GP_V2_EXTRA', 'Group', children=[
                    _Supervisor.solid(NativeBox(
                        'UNRESERVED_HIDDEN', (0., 0., .65), (.1, .1, 1.3)))]))
            elif mutation == 'reserved-wrapper-empty':
                scene.nodes.append(_Node('GP_V2_EXTRA', 'Group', children=[]))
            elif mutation == 'reserved-unknown-pose':
                scene.nodes.append(_Node('GP_V2_UNKNOWN', 'Pose', children=[]))
            elif mutation in ('nested-extra', 'nested-pose-extra', 'attached-extra'):
                hidden = _Supervisor.solid(NativeBox(
                    'GP_V2_EXTRA', (0., 0., .65), (.1, .1, 1.3)))
                if mutation == 'nested-extra':
                    scene.nodes.append(_Node(None, 'Group', children=[hidden]))
                elif mutation == 'nested-pose-extra':
                    scene.nodes.append(_Node(None, 'Pose', children=[
                        _Node(None, 'Transform', children=[hidden])]))
                else:
                    scene.nodes.append(_Node(None, 'Solid',
                                             boundingObject=hidden, children=[]))
            elif mutation == 'decorative-hidden-solid':
                scene.nodes.append(_Node(
                    'GP_V2_COURSE_RED_0', 'Pose', children=[
                        _Supervisor.solid(NativeBox(
                            'UNRESERVED_HIDDEN', (0., 0., .65),
                            (.1, .1, 1.3)))]))
            elif mutation == 'decorative-nested-solid':
                scene.nodes.append(_Node(
                    None, 'Group', children=[
                        _Node('GP_V2_WHITE_0', 'Pose', children=[
                            _Node(None, 'Group', children=[
                                _Supervisor.solid(NativeBox(
                                    'UNRESERVED_HIDDEN', (0., 0., .65),
                                    (.1, .1, 1.3)))])])]))
            elif mutation == 'decorative-collider':
                scene.nodes.append(_Node(
                    'GP_V2_COURSE_RED_0', 'Pose', children=[],
                    boundingObject=_Node(None, 'Box', size=(.1, .1, 1.3))))
            elif mutation == 'decorative-group':
                scene.nodes.append(_Node(None, 'Group', children=[
                    _Node('GP_V2_COURSE_RED_0', 'Pose', children=[])]))
            else:
                scene.nodes.append(_Node('GP_V2_COURSE_RED_0', 'Pose', children=[]))
            if mutation in ('decorative-pose', 'decorative-group'):
                self.assertIsNone(verify_native_boxes(scene, plan, boxes))
            else:
                with self.subTest(mutation=mutation), self.assertRaises(RuntimeError):
                    verify_native_boxes(scene, plan, boxes)

    def test_fails_closed_on_native_pose_lock_physics_or_rendering(self):
        plan, boxes = _plan_and_manifest()
        for mutation in ('position', 'lock', 'missing-lock', 'collider',
                         'missing-collider', 'rendered', 'invisible',
                         'rotation', 'missing-rotation', 'malformed-rotation',
                         'nested-collider'):
            scene = _Supervisor(boxes)
            node = scene.nodes[0]
            if mutation == 'position':
                node.position = (99., 0., 0.)
            if mutation == 'rotation':
                node.fields['rotation'] = (0., 0., 1., .7853981633974483)
            if mutation == 'missing-rotation':
                del node.fields['rotation']
            if mutation == 'malformed-rotation':
                node.fields['rotation'] = (0., 0., float('nan'), 0.)
            if mutation == 'nested-collider':
                node.fields['children'].append(_Node(
                    'GP_V2_SNEAK', 'Solid',
                    boundingObject=_Node(None, 'Box', size=(.1, .1, .1))))
            if mutation == 'lock':
                node.fields['locked'] = False
            if mutation == 'missing-lock':
                del node.fields['locked']
            if mutation == 'collider':
                node.fields['boundingObject'].fields['size'] = (1., 1., 1.)
            if mutation == 'missing-collider':
                del node.fields['boundingObject']
            if mutation == 'rendered':
                node.fields['children'][0].fields['geometry'].fields['size'] = (1., 1., 1.)
            if mutation == 'invisible':
                node.fields['children'].clear()
            with self.subTest(mutation=mutation), self.assertRaises(RuntimeError):
                verify_native_boxes(scene, plan, boxes)


    def test_six_decimal_native_serialization_is_not_geometry_drift(self):
        plan, boxes = _plan_and_manifest()
        box = boxes[0]
        rounded = replace(box, position=(box.position[0] + .00000042,
                                         box.position[1], box.position[2]))
        witness = (rounded,) + boxes[1:]
        self.assertIsNone(verify_native_boxes(_Supervisor(witness), plan, witness))
        scene = _Supervisor(boxes)
        scene.nodes[0].position = (box.position[0] + .000002,
                                   box.position[1], box.position[2])
        with self.assertRaises(RuntimeError):
            verify_native_boxes(scene, plan, boxes)


if __name__ == '__main__':
    unittest.main()
