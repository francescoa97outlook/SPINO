"""
runner: headless subprocess entry point that executes the scheduling pipeline.

Usage::

    python -m spino.runner /path/to/settings.json

It overlays the JSON settings onto the pipeline's ``phase_config`` module and
then calls ``phase_scheduler.main()``.  The GUI launches this in a subprocess
and streams its stdout into the log pane; running it by hand is also the
recommended headless smoke test.

Why overlay-then-import: ``phase_scheduler`` binds ``CUSTOM_PLANETS`` at
*import* time (``from phase_config import CUSTOM_PLANETS``), so every override
must be applied to ``phase_config`` **before** ``phase_scheduler`` is imported.
The remaining globals are re-read inside ``main()`` and pick up the overrides
regardless.
"""
from __future__ import annotations

import os
import sys

# Force a headless matplotlib backend before any pipeline module imports pyplot.
import matplotlib
matplotlib.use("Agg")

_HERE = os.path.dirname(os.path.abspath(__file__))
PIPELINE_DIR = os.path.join(_HERE, "pipeline")

# Keys stored as JSON lists that the pipeline expects as tuples.
_TUPLE_KEYS = ("TELLURIC_LAMBDA_RANGE_NM", "TELLURIC_RV_GRID_KMS")


def run(settings_path: str) -> int:
    """Apply *settings_path* to phase_config and run the pipeline.

    Returns a process-style exit code (0 on success).
    """
    if PIPELINE_DIR not in sys.path:
        sys.path.insert(0, PIPELINE_DIR)

    import json
    with open(settings_path) as f:
        settings = json.load(f)

    import phase_config
    for key, val in settings.items():
        if key in _TUPLE_KEYS and isinstance(val, list):
            val = tuple(val)
        setattr(phase_config, key, val)

    os.makedirs(phase_config.OUTPUT_DIR, exist_ok=True)
    print(f"[runner] output dir: {phase_config.OUTPUT_DIR}", flush=True)

    # Import AFTER overrides so the module-level CUSTOM_PLANETS binding is current.
    import phase_scheduler
    phase_scheduler.main()
    print("[runner] done.", flush=True)
    return 0


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: python -m spino.runner <settings.json>",
              file=sys.stderr)
        sys.exit(2)
    sys.exit(run(sys.argv[1]))


if __name__ == "__main__":
    main()
