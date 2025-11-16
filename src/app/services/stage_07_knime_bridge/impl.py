"""Legacy import shim for the deprecated KNIME bridge module."""

from src.app.services.stage_07_bi_prep_python.impl import *  # noqa: F401,F403

__all__ = ["run", "resolve_mode"]
