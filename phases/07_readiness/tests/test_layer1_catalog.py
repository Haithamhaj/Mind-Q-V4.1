from __future__ import annotations

import importlib
import json
from pathlib import Path

import pandas as pd

module = importlib.import_module("phases.07_readiness.impl")
_build_layer1_catalog = module._build_layer1_catalog
_infer_semantic_role = module._infer_semantic_role


def test_infer_semantic_role_variants() -> None:
    bool_series = pd.Series([True, False, None], dtype="boolean")
    assert _infer_semantic_role(bool_series) == "flag"

    datetime_series = pd.Series(pd.to_datetime(["2025-01-01", "2025-01-02"]))
    assert _infer_semantic_role(datetime_series) == "temporal"

    numeric_series = pd.Series([1.2, 3.4, 5.6])
    assert _infer_semantic_role(numeric_series) == "metric"

    string_series = pd.Series(["a", "b", "c"])
    assert _infer_semantic_role(string_series) == "dimension"


def test_build_layer1_catalog(tmp_path: Path) -> None:
    frame = pd.DataFrame(
        {
            "order_id": ["ORD-001", "ORD-002"],
            "cod_amount": [125.5, 0.0],
            "order_date": pd.to_datetime(["2025-01-01", "2025-01-02"]),
            "cod_flag": pd.Series([True, False], dtype="boolean"),
        }
    )
    dataset_path = tmp_path / "layer1_dataset.parquet"
    frame.to_parquet(dataset_path, index=False)

    schema_payload = {
        "columns": [
            {
                "name": "order_id",
                "role": "dimension",
                "dtype": "string",
                "label": {"en": "Order ID", "ar": "\u0645\u0639\u0631\u0641\u0020\u0627\u0644\u0634\u062d\u0646\u0629"},
                "description": {"en": "Shipment identifier", "ar": "\u0645\u0639\u0631\u0641\u0020\u0627\u0644\u0634\u062d\u0646\u0629"},
            },
            {
                "name": "cod_amount",
                "role": "metric",
                "dtype": "float",
            },
            {
                "name": "order_date",
                "role": "temporal",
                "dtype": "datetime",
            },
            {
                "name": "cod_flag",
                "role": "flag",
                "dtype": "bool",
            },
        ]
    }
    schema_path = tmp_path / "layer1_schema.json"
    schema_path.write_text(json.dumps(schema_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    catalog_result = _build_layer1_catalog(dataset_path, schema_path, run_id="unit-test")
    assert catalog_result is not None
    catalog, preview = catalog_result

    assert catalog["field_count"] == 4
    assert catalog["row_count"] == 2
    meta = {entry["name"]: entry for entry in catalog["columns"]}
    assert meta["cod_amount"]["role"] == "metric"
    assert meta["order_date"]["role"] == "temporal"
    assert meta["cod_flag"]["role"] == "flag"
    assert meta["order_id"]["label"]["ar"] == "\u0645\u0639\u0631\u0641\u0020\u0627\u0644\u0634\u062d\u0646\u0629"
    assert len(preview) == 2
