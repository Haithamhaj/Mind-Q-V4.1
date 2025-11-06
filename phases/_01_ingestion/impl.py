from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_impl():
    base = Path(__file__).resolve().parents[1]
    impl_path = base / "01_ingestion" / "impl.py"
    if not impl_path.exists():
        raise FileNotFoundError(f"Unable to locate ingestion implementation at {impl_path}")
    spec = importlib.util.spec_from_file_location("phase_01_ingestion_impl", impl_path.as_posix())
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load ingestion implementation from {impl_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_shim = _load_impl()
run = _shim.run
