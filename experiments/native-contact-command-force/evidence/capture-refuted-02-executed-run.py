#!/usr/bin/env python3
"""Use the frozen native one-step runner with a distinct preregistered protocol."""
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('native_one_step', HERE.parent/'native-contact-intervention/run.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
runner.HERE = HERE

if __name__ == '__main__':
    runner.main()
