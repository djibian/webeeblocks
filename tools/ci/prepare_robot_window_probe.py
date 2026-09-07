#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAIN_JS = ROOT / "plugins" / "robot_windows" / "blockly" / "main.js"

needle = "    window.robotWindow.receive = receiveMessage;\n"
injection = """    window.robotWindow.receive = function(value) {\n        receiveMessage(value);\n        if(value === \"WEBEEBLOCKS_CI_CONTROLLER_TO_WINDOW\") {\n            console.log(\"WEBEEBLOCKS_CI_CONTROLLER_TO_WINDOW_OK\");\n            window.robotWindow.send(\"WEBEEBLOCKS_CI_WINDOW_ACK\");\n        }\n    };\n    window.robotWindow.send(\"WEBEEBLOCKS_CI_WINDOW_READY\");\n"""

source = MAIN_JS.read_text(encoding="utf-8")
if needle not in source:
    raise SystemExit("Robot Window receive assignment not found; refusing ambiguous CI instrumentation")
MAIN_JS.write_text(source.replace(needle, injection, 1), encoding="utf-8")
print("Instrumented actual Blockly Robot Window for bidirectional WWI probe")
