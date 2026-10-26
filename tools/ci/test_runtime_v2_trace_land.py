#!/usr/bin/env python3
"""Exercise the actual workflow parser's LAND token boundary and stop check."""
from pathlib import Path
import re
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[2]


def parse(log):
    workflow = (ROOT / ".github/workflows/ci-runtime.yml").read_text()
    section = workflow.split("      - name: Prove pre-READY gate, pinned Blockly runtime and dynamic STOP actions", 1)[1]
    block = section.split("          python3 - <<'PY'\n", 1)[1].split("\n          PY", 1)[0]
    code = textwrap.dedent(block)
    # Execute the real command parser, leaving the complete ordered mission
    # oracle in the workflow intact. Missing terminal LAND remains observable.
    code = code[code.index("trace = []"):code.index("expected = ")]
    values = {"log": log, "re": re}
    exec(compile(code, "actual-runtime-workflow-parser", "exec"), values)
    return values["trace"]


class LandTraceTests(unittest.TestCase):
    def test_diagnostic_is_not_a_terminal_response(self):
        diagnostic = "WEBEEBLOCKS_RUNTIME_V2 TRACE LAND_TOUCHDOWN time=13.472\n"
        self.assertEqual(parse(diagnostic), [])
        self.assertEqual(parse(diagnostic + "WEBEEBLOCKS_RUNTIME_V2 TRACE LAND stop=1\n"), ["LAND"])
        self.assertEqual(parse(diagnostic + diagnostic), [])

    def test_stop_and_command_order_are_preserved(self):
        with self.assertRaises(AssertionError):
            parse("WEBEEBLOCKS_RUNTIME_V2 TRACE LAND stop=0\n")
        self.assertEqual(parse("WEBEEBLOCKS_RUNTIME_V2 TRACE LAND_INVALID stop=1\n"), [])
        self.assertEqual(parse("WEBEEBLOCKS_RUNTIME_V2 TRACE TAKEOFF stop=1\n"
                               "WEBEEBLOCKS_RUNTIME_V2 TRACE LAND stop=1\n"), ["TAKEOFF", "LAND"])


if __name__ == "__main__":
    unittest.main()
