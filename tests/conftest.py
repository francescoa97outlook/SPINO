"""
Make the flat-import pipeline modules importable from the tests.

The pipeline layer (`phase_kepler`, `phase_telluric_plot`, ...) uses flat
imports with no `spino.` prefix, because the scheduler adds its own directory
to `sys.path` at runtime.  The tests reproduce that arrangement.
"""

import sys
from pathlib import Path

PIPELINE_DIR = Path(__file__).resolve().parents[1] / "src" / "spino" / "pipeline"

if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))
