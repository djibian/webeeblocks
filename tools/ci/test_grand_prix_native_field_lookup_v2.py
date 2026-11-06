"""Controlled API/schema checks only; never a native speed or flight PASS."""
import unittest
from tools.grand_prix.native_field_lookup_v2 import NativeFieldLookup


class Field:
    def __init__(self, node, name):
        self.node, self.name = node, name

    def getName(self):
        return self.name

    def getSFNode(self):
        return self.node.values[self.name]


class Node:
    def __init__(self, kind, names, **values):
        self.kind, self.names, self.values = kind, names, values
        self.probes, self.enumerations = [], 0

    def isProto(self):
        return False

    def getTypeName(self):
        return self.kind

    def getNumberOfFields(self):
        self.enumerations += 1
        return len(self.names)

    def getFieldByIndex(self, index):
        return Field(self, self.names[index])

    def getField(self, name):
        self.probes.append(name)
        return Field(self, name) if name in self.names else None


class NativeFieldLookupTests(unittest.TestCase):
    def test_full_collider_checks_still_refute_live_geometry_and_new_physics(self):
        from unittest.mock import patch
        from tools.ci.test_grand_prix_native_collider_contract_v2 import (
            _Node, _Field, _Supervisor, _plan_and_manifest,
        )
        from tools.grand_prix.native_collider_contract_v2 import verify_native_boxes
        original = _Node.getField
        absent = []

        def field(node, name):
            if not node.isProto() and name not in node.fields:
                absent.append((node.kind, name))
            return original(node, name)

        def by_index(node, index):
            name = list(node.fields)[index]
            result = _Field(node.fields[name])
            result.getName = lambda: name
            return result

        plan, boxes = _plan_and_manifest()
        with patch.object(_Node, 'getNumberOfFields', lambda node: len(node.fields), create=True), \
                patch.object(_Node, 'getFieldByIndex', by_index, create=True), \
                patch.object(_Node, 'getField', field):
            scene = _Supervisor(boxes)
            verify_native_boxes(scene, plan, boxes)
            self.assertEqual(absent, [])
            scene.nodes[0].position = (99., 0., .65)
            with self.assertRaisesRegex(RuntimeError, 'world pose mismatch'):
                verify_native_boxes(scene, plan, boxes)
            scene = _Supervisor(boxes)
            # A new Solid through a live SFNode edge is not hidden by schema reuse.
            shape = scene.nodes[0].fields['children'][0]
            shape.fields['geometry'] = _Supervisor.solid(boxes[1])
            with self.assertRaises(RuntimeError):
                verify_native_boxes(scene, plan, boxes)
            scene = _Supervisor(boxes)
            scene.nodes.append(_Node('new-extra', 'Group', children=[
                _Supervisor.solid(boxes[1])]))
            with self.assertRaises(RuntimeError):
                verify_native_boxes(scene, plan, boxes)

    def test_builtin_absence_does_not_repeat_ipc_but_values_and_edges_stay_live(self):
        nodes = [Node('Pose', ['children'], children=[]) for _ in range(100)]
        lookup = NativeFieldLookup()
        for node in nodes:
            for key in ('boundingObject', 'extensionSlot', 'choice', 'endPoint', 'geometry'):
                self.assertIsNone(lookup.get(node, key))
            self.assertEqual(lookup.get(node, 'children').getSFNode(), [])
        self.assertEqual(sum(n.enumerations for n in nodes), 1)
        self.assertEqual([n.probes for n in nodes], [['children']] * 100)
        # A new collidable child must remain visible, even to an existing handle.
        handle = lookup.get(nodes[0], 'children')
        extra = object()
        nodes[0].values['children'] = [extra]
        self.assertEqual(handle.getSFNode(), [extra])
        self.assertEqual(lookup.get(nodes[0], 'children').getSFNode(), [extra])
        # A separate scene check does not inherit any schema or old node value.
        self.assertEqual(NativeFieldLookup().get(nodes[0], 'children').getSFNode(), [extra])
        self.assertEqual(nodes[0].enumerations, 2)

    def test_proto_fields_and_unsupported_api_use_original_unfiltered_reads(self):
        node = Node('UserProto', ['children'], children=[])
        node.isProto = lambda: True
        lookup = NativeFieldLookup()
        self.assertIsNone(lookup.get(node, 'boundingObject'))
        node.names.append('boundingObject')
        node.values['boundingObject'] = 'real collider'
        self.assertEqual(lookup.get(node, 'boundingObject').getSFNode(), 'real collider')
        self.assertEqual(node.enumerations, 0)
        node.isProto = lambda: False
        node.getNumberOfFields = None
        self.assertEqual(lookup.get(node, 'boundingObject').getSFNode(), 'real collider')

    def test_unreadable_or_oversized_schema_is_not_an_absence_certificate(self):
        for count in (-1, 4097, True, 1.0):
            node = Node('Pose', ['children'])
            node.getNumberOfFields = lambda: count
            with self.assertRaisesRegex(RuntimeError, 'field count'):
                NativeFieldLookup().get(node, 'boundingObject')
        for names in (['children', 'children'], [''], [None]):
            with self.assertRaisesRegex(RuntimeError, 'field declaration'):
                NativeFieldLookup().get(Node('Pose', names), 'boundingObject')
        node = Node('Pose', ['children'])
        node.getFieldByIndex = lambda index: None
        with self.assertRaisesRegex(RuntimeError, 'field declaration'):
            NativeFieldLookup().get(node, 'boundingObject')


if __name__ == '__main__':
    unittest.main()
