"""Pure-Python Stage 07 BI prep module (replaces KNIME bridge)."""

from .impl import resolve_mode, run

__all__ = ["run", "resolve_mode"]
