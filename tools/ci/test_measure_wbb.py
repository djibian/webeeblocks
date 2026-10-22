#!/usr/bin/env python3
"""Regression examples for serialized pupil workspace metrics."""
import json
import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parents[1] / 'blockly'))
from measure_wbb import InvalidWorkspace, analyze, main


def b(typ, ident, **kwargs):
    return dict(type=typ, id=ident, **kwargs)


def project(roots, variables=None):
    return {'format': 'webeeblocks-project', 'version': 1, 'activity': {'id': 'gp'},
            'workspace': {'blocks': {'languageVersion': 0, 'blocks': roots}, 'variables': variables or []}}


class Complexity(unittest.TestCase):
    def test_real_vs_shadow_and_procedure_body(self):
        number = b('math_number', 'number')
        shadow = b('math_number', 'fallback')
        move = b('webeeblocks_v2_move', 'move', inputs={'DISTANCE': {'block': number, 'shadow': shadow}})
        until = b('webeeblocks_v2_until', 'until', inputs={'DO': {'block': move}})
        takeoff = b('webeeblocks_v2_takeoff', 'takeoff', next={'block': until})
        body = b('webeeblocks_v2_move', 'procedure-motion')
        definition = b('procedures_defnoreturn', 'definition', inputs={'STACK': {'block': body}})
        result = analyze(project([takeoff, definition], [{'id': 'v', 'name': 'not used'}]))
        self.assertEqual(result['total_blocks'], 6)
        self.assertEqual(result['main_chain_blocks'], 2)
        self.assertEqual(result['top_level_stacks'], 2)
        self.assertEqual(result['max_statement_nesting'], 1)
        self.assertEqual(result['max_input_nesting'], 2)
        self.assertEqual(result['procedure_definitions'], 1)
        self.assertEqual(result['unused_variable_declarations'], ['not used'])
        self.assertEqual(result['block_types']['math_number'], 1)

    def test_shadow_alone_and_reference(self):
        statement = b('variables_set', 'set', fields={'VAR': {'id': 'v'}},
                      inputs={'VALUE': {'shadow': b('math_number', 'shadow')}})
        result = analyze(project([statement], [{'id': 'v', 'name': 'nombre_H'}]))
        self.assertEqual(result['total_blocks'], 2)
        self.assertEqual(result['referenced_variables'], 1)
        self.assertEqual(result['unused_variable_declarations'], [])
        self.assertIsNone(result['main_chain_blocks'])

    def test_long_sequence_is_not_artificially_a_nested_program(self):
        sequence = None
        for i in reversed(range(200)):
            block = b('webeeblocks_v2_move', str(i))
            if sequence is not None:
                block['next'] = {'block': sequence}
            sequence = block
        result = analyze(project([sequence]))
        self.assertEqual(result['total_blocks'], 200)
        self.assertEqual(result['max_input_nesting'], 0)
        self.assertEqual(result['max_connected_chain_blocks'], 200)

    def test_existing_exact_project_fixture(self):
        # A versioned real Blockly project on main, not a synthetic AST.
        source = Path(__file__).resolve().parents[2] / 'tools/physical/hover_range_comparison.wbb'
        metrics = analyze(json.loads(source.read_text(encoding='utf-8')))
        self.assertEqual(metrics['total_blocks'], 5)
        self.assertEqual(metrics['main_chain_blocks'], 4)
        self.assertEqual(metrics['declared_variables'], 1)
        self.assertEqual(metrics['referenced_variables'], 1)
        self.assertEqual(metrics['max_input_nesting'], 1)

    def test_invalid_duplicate_ids_and_version(self):
        with self.assertRaisesRegex(InvalidWorkspace, 'duplicate'):
            analyze(project([b('x', 'same'), b('y', 'same')]))
        with self.assertRaisesRegex(InvalidWorkspace, 'format/version'):
            analyze(dict(project([]), version=3))
        with self.assertRaisesRegex(InvalidWorkspace, 'next-block'):
            analyze(project([b('x', 'a', next={'shadow': b('y', 'b')})]))
        with self.assertRaisesRegex(InvalidWorkspace, 'activity'):
            analyze(dict(project([]), activity='not-an-object'))
        with self.assertRaisesRegex(InvalidWorkspace, 'activity'):
            analyze(dict(project([]), activity={'id': []}))
        with self.assertRaisesRegex(InvalidWorkspace, 'Blockly block'):
            analyze(project([b('x', 'a', inputs={'VALUE': {
                'block': {}, 'shadow': b('math_number', 'fallback')
            }})]))

    def test_command_line_output_and_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'student.wbb'
            path.write_text(json.dumps(project([b('webeeblocks_v2_takeoff', 't')])), encoding='utf8')
            self.assertEqual(main([str(path)]), 0)
            path.write_text(json.dumps(dict(project([]), activity='bad')), encoding='utf8')
            self.assertEqual(main([str(path)]), 2)
            path.write_text('{', encoding='utf8')
            self.assertEqual(main([str(path)]), 2)


if __name__ == '__main__':
    unittest.main()
