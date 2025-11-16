"""Compatibility shim forwarding to the legacy pipeline timeline module."""

# Import from the parent src directory
import sys
from pathlib import Path

# Add parent directory to path if not already there
parent_src = Path(__file__).resolve().parents[5] / "src"
if str(parent_src) not in sys.path:
    sys.path.insert(0, str(parent_src))

# Now import from the actual timeline module
from app.services.pipeline_api.timeline import *  # type: ignore[F401,F403]
from app.services.pipeline_api.timeline import build_run_timeline  # noqa: F401
