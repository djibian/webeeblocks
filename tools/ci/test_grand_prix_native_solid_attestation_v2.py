"""Adversarial Supervisor-node fixtures, never a native Webots/flight PASS."""
import math
import unittest
from copy import deepcopy

from tools.grand_prix.native_solid_attestation_v2 import (
    NativeGeometryMismatch, RequiredSolid, assert_native_solids_match,
)


class Field:
    def __init__(self, value):
        self.value = value

    def getSFBool(self):
        return self.value

    def getSFVec3f(self):
        return self.value

    def getSFNode(self):
        return self.value

    def getSFRotation(self):
        return self.value

    def getCount(self):
        return len(self.value)

    def getMFNode(self, i):
        return self.value[i]


class Node:
    def __init__(self, kind, name='', **fields):
        self.kind, self.name = kind, name
        self.fields = {key: Field(value) for key, value in fields.items()}

    def getTypeName(self):
        return self.kind

    def getDef(self):
        return self.name

    def getField(self, key):
        return self.fields.get(key)


class Supervisor:
    def __init__(self, nodes):
        self.root = Node('Group', children=nodes)

    def getRoot(self):
        return self.root


def solid(spec):
    return Node('Solid', spec.name,
                locked=True, translation=list(spec.translation),
                rotation=[0., 0., 1., 0.],
                boundingObject=Node('Box', size=list(spec.size)),
                children=[Node('Shape', geometry=Node('Box', size=list(spec.size)))])


class NativeSolidAttestationTests(unittest.TestCase):
    def setUp(self):
        self.required = (
            RequiredSolid('GP_V2_L_0_0', (2., .3, .65), (.60, .04, 1.3)),
            RequiredSolid('GP_V2_H_0_BEAM', (.9, 0., .96), (.04, .56, .68)),
            RequiredSolid('GP_V2_FINAL_PANEL', (2., 2., .65), (.04, 1.84, 1.3)),
        )
        self.nodes = [solid(spec) for spec in self.required]

    def check_rejected(self, nodes, required=None):
        with self.assertRaises(NativeGeometryMismatch):
            assert_native_solids_match(Supervisor(nodes),
                                       self.required if required is None else required)

    def test_complete_locked_visible_colliders_pass_only_this_precondition(self):
        # Decorative tape is not a physical body and must not be mistaken for one.
        self.assertIsNone(assert_native_solids_match(
            Supervisor(self.nodes + [Node('Pose', 'GP_V2_RED_1_0')]), self.required))

    def test_missing_extra_and_duplicate_body_fail_closed(self):
        self.check_rejected(self.nodes[:-1])
        extra = solid(RequiredSolid('GP_V2_H_1_LEFT', (0., 0., .65), (.48, .04, 1.3)))
        self.check_rejected(self.nodes + [extra])
        # A reserved collider under a Group was previously invisible to the
        # direct-root inventory, even though it can change physical contacts.
        self.check_rejected(self.nodes + [Node('Group', children=[extra])])
        self.check_rejected(self.nodes + [
            Node('Pose', children=[Node('Transform', children=[extra])])])
        # SFNode attachments must not hide an extra reserved Solid either.
        self.check_rejected(self.nodes + [
            Node('Solid', 'OTHER', locked=True, boundingObject=extra,
                 children=[Node('Shape', geometry=Node('Box', size=[.1, .1, .1]))])])
        self.assertIsNone(assert_native_solids_match(
            Supervisor(self.nodes + [
                Node('Group', children=[Node('Shape', geometry=Node('Box', size=[.1, .1, .1]))])]),
            self.required))
        self.check_rejected(self.nodes + [deepcopy(self.nodes[0])])
        self.check_rejected(self.nodes, required=self.required + (self.required[0],))
        self.check_rejected(self.nodes, required=())

    def test_native_geometry_is_not_interchangeable_with_rendering(self):
        for index in range(len(self.nodes)):
            nodes = deepcopy(self.nodes)
            nodes[index].fields['locked'].value = False
            self.check_rejected(nodes)
            nodes = deepcopy(self.nodes)
            nodes[index].fields['rotation'].value = [0., 0., 1., .7853981633974483]
            self.check_rejected(nodes)
            nodes = deepcopy(self.nodes)
            nodes[index].fields['boundingObject'].value = None
            self.check_rejected(nodes)
            nodes = deepcopy(self.nodes)
            nodes[index].fields['boundingObject'].value.kind = 'Cylinder'
            self.check_rejected(nodes)
            nodes = deepcopy(self.nodes)
            nodes[index].fields['boundingObject'].value.fields['size'].value[0] += .001
            self.check_rejected(nodes)
            nodes = deepcopy(self.nodes)
            nodes[index].fields['children'].value[0].fields['geometry'].value = None
            self.check_rejected(nodes)
            nodes = deepcopy(self.nodes)
            nodes[index].fields['children'].value[0].fields['geometry'].value.fields['size'].value[1] += .001
            self.check_rejected(nodes)
            nodes = deepcopy(self.nodes)
            nodes[index].fields['translation'].value[1] += .001
            self.check_rejected(nodes)

    def test_malformed_native_nodes_and_nonfinite_observations_fail_closed(self):
        for name in ('GP_V2_H_0_BEAM', 'GP_V2_FINAL_PANEL'):
            nodes = deepcopy(self.nodes)
            node = next(n for n in nodes if n.name == name)
            node.kind = 'Pose'
            self.check_rejected(nodes)
        nodes = deepcopy(self.nodes)
        nodes[0].fields['translation'].value[0] = math.nan
        self.check_rejected(nodes)
        nodes = deepcopy(self.nodes)
        nodes[0].fields['boundingObject'].value.fields['size'].value[2] = 0
        self.check_rejected(nodes)
        nodes = deepcopy(self.nodes)
        del nodes[0].fields['locked']
        self.check_rejected(nodes)
        nodes = deepcopy(self.nodes)
        del nodes[0].fields['rotation']
        self.check_rejected(nodes)
        for rotation in ([0., 0., 1., math.nan], [0., 0., 1.],
                         [0., True, 1., 0.], '0 0 1 0'):
            nodes = deepcopy(self.nodes)
            nodes[0].fields['rotation'].value = rotation
            self.check_rejected(nodes)
        nodes = deepcopy(self.nodes)
        nodes[0].fields['children'].value = []
        self.check_rejected(nodes)
        nodes = deepcopy(self.nodes)
        nodes[0].fields['children'].value.append(Node('Shape'))
        self.check_rejected(nodes)
        self.check_rejected(self.nodes, required=[object()])
        with self.assertRaises(NativeGeometryMismatch):
            assert_native_solids_match(object(), self.required)

    def test_requirements_reject_invalid_identifiers_and_sizes(self):
        for name in ('GP_U_BOX_0', 'GP_V2_RED_0', 'GP_V2_H_0_B-EAM', '', None):
            with self.assertRaises(NativeGeometryMismatch):
                RequiredSolid(name, (0., 0., 0.), (.1, .2, .3))
        for vec in ((math.nan, 0., 0.), (True, 0., 0.), (0., 0.), (0., '1', 0.)):
            with self.assertRaises(NativeGeometryMismatch):
                RequiredSolid('GP_V2_H_0_LEFT', vec, (.1, .2, .3))
        for size in ((0., .2, .3), (-1., .2, .3), (math.inf, .2, .3)):
            with self.assertRaises(NativeGeometryMismatch):
                RequiredSolid('GP_V2_H_0_LEFT', (0., 0., 0.), size)


if __name__ == '__main__':
    unittest.main()
