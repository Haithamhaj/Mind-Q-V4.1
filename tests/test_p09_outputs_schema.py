from __future__ import annotations

import json
from pathlib import Path

from tests.p09_utils import load_impl, load_models, write_stage_artifacts


def test_p09_outputs_schema(tmp_path: Path) -> None:
    run_id = "run_schema"
    artifacts_root = write_stage_artifacts(tmp_path, run_id, n_rows=4)
    impl = load_impl()
    impl.run(run_id, {}, {"artifacts_root": artifacts_root.as_posix()})

    out_dir = artifacts_root / run_id / "stage_09_business_validation"
    models = load_models()

    validation_payload = (out_dir / "validation_report.json").read_text(encoding="utf-8")
    models.ValidationReport.model_validate_json(validation_payload)

    schema_dir = out_dir / "contracts" / "stage_09"
    assert (schema_dir / "validation_report.schema.json").exists()
    assert (schema_dir / "bi_feed.schema.json").exists()

    whitelist_schema = json.loads((schema_dir / "bi_whitelist.schema.json").read_text(encoding="utf-8"))
    assert whitelist_schema["type"] == "array"
