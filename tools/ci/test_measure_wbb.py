#!/usr/bin/env python3
"""Regression examples for serialized pupil workspace metrics."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parents[1] / 'blockly'))
from measure_wbb import InvalidWorkspace, MAX_BYTES, analyze, main
from compare_wbb import compare, main as comparison_main


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
        with self.assertRaisesRegex(InvalidWorkspace, 'connected block'):
            analyze(project([b('x', 'a', inputs={'VALUE': {
                'block': None, 'shadow': b('math_number', 'fallback')
            }})]))
        with self.assertRaisesRegex(InvalidWorkspace, 'Blockly shadow'):
            analyze(project([b('x', 'a', inputs={'VALUE': {'shadow': None}})]))

    def test_real_wbb_structure_comparison_and_signed_deltas(self):
        with tempfile.TemporaryDirectory() as folder:
            first, second = (Path(folder) / name for name in ('first.wbb', 'second.wbb'))
            comparison = b('logic_compare', 'comparison', inputs={
                'A': {'block': b('webeeblocks_v2_range', 'range')},
                'B': {'block': b('math_number', 'threshold')},
            })
            condition = b('controls_if', 'condition', inputs={
                'IF0': {'block': comparison},
                'DO0': {'block': b('webeeblocks_v2_move', 'move')},
            })
            first.write_text(json.dumps(project([
                b('webeeblocks_v2_takeoff', 'start', next={'block': condition})
            ])), encoding='utf-8')
            second.write_text(json.dumps(project([
                b('webeeblocks_v2_takeoff', 'start2',
                  next={'block': b('webeeblocks_v2_move', 'move2')})
            ])), encoding='utf-8')
            result = compare([first, second])
            metrics = result['candidates'][0]['metrics']
            self.assertEqual(metrics['total_blocks'], 6)
            self.assertEqual(metrics['if_blocks'], 1)
            self.assertEqual(metrics['if_test_slots'], 1)
            self.assertEqual(metrics['if_elseif_test_slots'], 0)
            self.assertEqual(metrics['if_else_slots'], 0)
            self.assertEqual(metrics['loop_guard_slots'], 0)
            self.assertEqual(metrics['conditional_test_slots'], 1)
            self.assertNotIn('conditions', metrics)
            self.assertEqual(metrics['comparisons'], 1)
            self.assertEqual(metrics['sensor_reads'], 1)
            self.assertEqual(metrics['numeric_literals'], 1)
            self.assertEqual(metrics['movement_commands'], 1)
            self.assertEqual(metrics['main_chain_blocks'], 2)
            self.assertEqual(result['comparisons'][0]['delta_vs_first']['total_blocks'], -4)
            self.assertEqual(result['comparisons'][0]['delta_vs_first']['if_blocks'], -1)
            self.assertEqual(result['comparisons'][0]['delta_vs_first']['conditional_test_slots'], -1)
            self.assertEqual(len(result['candidates'][0]['sha256']), 64)
            self.assertTrue(result['human_construction_debugging_evidence_required'])
            self.assertIsNone(result['automatic_pedagogical_winner'])

            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(comparison_main([str(first), str(second)]), 0)
            self.assertEqual(json.loads(output.getvalue())['candidates'][1]['metrics']['total_blocks'], 2)

    def test_conditional_loops_not_misreported_as_zero_conditions(self):
        with tempfile.TemporaryDirectory() as folder:
            reference, until, while_loop = (Path(folder) / name for name in
                                            ('reference.wbb', 'until.wbb', 'while.wbb'))
            reference.write_text(json.dumps(project([
                b('controls_if', 'if', inputs={
                    'IF0': {'block': b('logic_boolean', 'bool')}
                })
            ])), encoding='utf-8')
            until.write_text(json.dumps(project([
                b('webeeblocks_v2_until', 'until', inputs={
                    'CONDITION': {'block': b('logic_boolean', 'until-bool')}
                })
            ])), encoding='utf-8')
            while_loop.write_text(json.dumps(project([
                b('controls_whileUntil', 'while', fields={'MODE': 'UNTIL'},
                  inputs={'BOOL': {'block': b('logic_boolean', 'while-bool')}})
            ])), encoding='utf-8')
            result = compare([reference, until, while_loop])
            for entry in result['candidates'][1:]:
                self.assertEqual(entry['metrics']['if_blocks'], 0)
                self.assertEqual(entry['metrics']['if_test_slots'], 0)
                self.assertEqual(entry['metrics']['loop_guard_slots'], 1)
                self.assertEqual(entry['metrics']['conditional_test_slots'], 1)
                self.assertIsNone(result['automatic_pedagogical_winner'])
            for delta in result['comparisons']:
                self.assertEqual(delta['delta_vs_first']['conditional_test_slots'], 0)
                self.assertEqual(delta['delta_vs_first']['if_blocks'], -1)
                self.assertEqual(delta['delta_vs_first']['loop_guard_slots'], 1)

    def test_elseif_else_branches_count_even_without_connected_value(self):
        with tempfile.TemporaryDirectory() as folder:
            reference, complex_path, fixed = (Path(folder) / name for name in
                                              ('reference.wbb', 'elseif.wbb', 'repeat.wbb'))
            reference.write_text(json.dumps(project([
                b('controls_if', 'basic', inputs={
                    'IF0': {'block': b('logic_boolean', 'bool0')}
                })
            ])))
            complex_path.write_text(json.dumps(project([
                b('controls_if', 'if-else', extraState={'elseIfCount': 2, 'hasElse': True},
                  inputs={
                      'IF0': {'block': b('logic_boolean', 'bool1')},
                      'IF1': {'block': b('logic_boolean', 'bool2')},
                      # IF2 and ELSE are intentionally empty Blockly sockets.
                  })
            ])))
            fixed.write_text(json.dumps(project([
                b('controls_repeat_ext', 'repeat', inputs={
                    'TIMES': {'block': b('math_number', 'three')}
                })
            ])))
            result = compare([reference, complex_path, fixed])
            large = result['candidates'][1]['metrics']
            self.assertEqual(large['if_blocks'], 1)
            self.assertEqual(large['if_test_slots'], 3)
            self.assertEqual(large['if_elseif_test_slots'], 2)
            self.assertEqual(large['if_else_slots'], 1)
            self.assertEqual(large['conditional_test_slots'], 3)
            self.assertEqual(result['comparisons'][0]['delta_vs_first']['if_test_slots'], 2)
            self.assertEqual(result['comparisons'][0]['delta_vs_first']['if_else_slots'], 1)
            small = result['candidates'][2]['metrics']
            self.assertEqual(small['if_blocks'], 0)
            self.assertEqual(small['conditional_test_slots'], 0)
            self.assertEqual(small['fixed_iteration_loops'], 1)
            self.assertIsNone(result['automatic_pedagogical_winner'])

    def test_serialized_elseif_inputs_without_extra_state_not_ignored(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'elseif.wbb'
            path.write_text(json.dumps(project([
                b('controls_if', 'with-elseif',
                  inputs={'IF0': {'block': b('logic_boolean', 'one')},
                          'IF1': {'block': b('logic_boolean', 'two')},
                          'DO1': {'block': b('webeeblocks_v2_move', 'move')},
                          'ELSE': {'block': b('webeeblocks_v2_land', 'land')}})
            ])))
            actual = compare([path, path])['candidates'][0]['metrics']
            self.assertEqual(actual['if_blocks'], 1)
            self.assertEqual(actual['if_test_slots'], 2)
            self.assertEqual(actual['if_elseif_test_slots'], 1)
            self.assertEqual(actual['if_else_slots'], 1)
            self.assertEqual(actual['conditional_test_slots'], 2)

    def test_malformed_if_extra_state_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'bad-if.wbb'
            for malformed in ({'elseIfCount': -1}, {'elseIfCount': '100'},
                              {'elseIfCount': True}, {'elseIfCount': 1001},
                              ['not a dict'], [], '', 0, None, False,
                              {'hasElse': 'false'}, {'hasElse': 'true'},
                              {'hasElse': 0}, {'hasElse': 1},
                              {'hasElse': None}, {'hasElse': []}):
                path.write_text(json.dumps(project([
                    b('controls_if', 'if', extraState=malformed)
                ])))
                with self.subTest(malformed=malformed):
                    with self.assertRaisesRegex(InvalidWorkspace, 'IF'):
                        compare([path, path])

            for valid, expected_else in (({}, 0), ({'hasElse': False}, 0),
                                         ({'hasElse': True}, 1),
                                         ({'elseIfCount': 2, 'hasElse': True}, 1)):
                path.write_text(json.dumps(project([
                    b('controls_if', 'if', extraState=valid)
                ])))
                with self.subTest(valid=valid):
                    counters = compare([path, path])['candidates'][0]['metrics']
                    self.assertEqual(counters['if_else_slots'], expected_else)
                    self.assertEqual(counters['if_test_slots'], 1 + valid.get('elseIfCount', 0))

            path.write_text(json.dumps(project([
                b('controls_if', 'if-without-mutation-state')
            ])))
            self.assertEqual(compare([path, path])['candidates'][0]['metrics']['if_else_slots'], 0)

    def test_compare_never_ranks_identical_valid_real_project(self):
        source = Path(__file__).resolve().parents[2] / 'tools/physical/hover_range_comparison.wbb'
        result = compare([source, source])
        self.assertEqual(result['candidates'][0]['metrics']['total_blocks'], 5)
        self.assertEqual(result['candidates'][0]['metrics']['referenced_variables'], 1)
        self.assertTrue(all(value == 0 for value in result['comparisons'][0]['delta_vs_first'].values()))
        self.assertIsNone(result['automatic_pedagogical_winner'])

    def test_compare_rejects_malformed_missing_or_oversized_project(self):
        with tempfile.TemporaryDirectory() as folder:
            first, second = (Path(folder) / name for name in ('first.wbb', 'second.wbb'))
            first.write_text(json.dumps(project([b('webeeblocks_v2_takeoff', 'valid')])))
            with self.assertRaisesRegex(ValueError, 'at least two'):
                compare([first])
            with self.assertRaises(FileNotFoundError):
                compare([first, second])
            second.write_text(json.dumps(project([b('x', 'dup'), b('y', 'dup')])))
            with self.assertRaisesRegex(InvalidWorkspace, 'duplicate'):
                compare([first, second])
            second.write_text('{', encoding='utf-8')
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(comparison_main([str(first), str(second)]), 2)
            second.write_bytes(b' ' * (MAX_BYTES + 1))
            with self.assertRaisesRegex(InvalidWorkspace, 'maximum supported size'):
                compare([first, second])

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
