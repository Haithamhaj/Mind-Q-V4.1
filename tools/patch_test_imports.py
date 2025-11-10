#!/usr/bin/env python3
# v1.0 — idempotent patcher for tests imports
import pathlib, re
ROOT = pathlib.Path(__file__).resolve().parents[1]
repls = [
 (r"\bfrom\s+phases\._09_business_validation\s+import\b",
  "from backend.src.app.services.business_validation import"),
 (r"\bfrom\s+pipeline\s+import\s+PipelineRequest\b",
  "from backend.src.app.pipeline_api import PipelineRequest"),
 (r"\bimport\s+readiness\.tables\s+as\s+rt\b",
  "from backend.src.app.services.readiness import tables as rt"),
 (r"importlib\.import_module\(['\"]readiness\.tables['\"]\)",
  "importlib.import_module('backend.src.app.services.readiness.tables')"),
 (r"\bfrom\s+backend\.src\.app\.services\.pipeline_api\s+import\s+fastapi_app,\s*_purge_run_history\b",
  "from backend.src.app.services.run_history import purge_run_history"),
 (r"\bfrom\s+backend\.src\.app\.services\.pipeline_api\s+import\s+fastapi_app\b", ""),
 (r"\bfrom\s+backend\.src\.app\.services\.pipeline_api\s+import\s+_purge_run_history\b",
  "from backend.src.app.services.run_history import purge_run_history"),
 (r"\bfrom\s+backend\.src\.app\.services\.pipeline_api\s+import\s+PipelineRequest\b",
  "from backend.src.app.pipeline_api import PipelineRequest"),
]
for p in ROOT.joinpath("tests").glob("**/*.py"):
    t = p.read_text(encoding="utf-8")
    nt = t
    for pat, sub in repls: nt = re.sub(pat, sub, nt)
    if nt != t:
        p.write_text(nt, encoding="utf-8")
        print("patched:", p.relative_to(ROOT))
print("done.")
