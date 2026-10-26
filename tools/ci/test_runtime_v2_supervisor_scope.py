#!/usr/bin/env python3
"""Reject extra world queries and relocation of the private contact input."""
import unittest
from runtime_v2_supervisor_scope import SOURCE, validate


class SupervisorScopeTests(unittest.TestCase):
    def test_current_shared_source(self):
        validate(SOURCE.read_text())

    def test_forbidden_or_relocated_queries(self):
        source = SOURCE.read_text()
        mutations = (
            source + '\nvoid extra(void) { wb_supervisor_node_get_from_def("GOAL"); }\n',
            source + '\nvoid extra(void) { wb_supervisor_node_get_contact_points(0, true, 0); }\n',
            source.replace('wb_supervisor_node_get_self(), true, &count',
                           'wb_supervisor_node_get_field(0, "target"), true, &count'),
            source.replace('wb_supervisor_node_get_self(), true, &count',
                           'another_body, true, &count'),
            source.replace('wb_supervisor_node_get_self(), true, &count',
                           'wb_supervisor_node_get_self(), false, &count'),
            source.replace('land_has_ground_contact(z, origin_z)', 'another_contact_input(z, origin_z)'),
            source + '\nvoid extra(void) { land_has_ground_contact(0, 0); }\n',
        )
        for index, mutation in enumerate(mutations):
            with self.subTest(index=index), self.assertRaises(ValueError):
                validate(mutation)


if __name__ == "__main__":
    unittest.main()
