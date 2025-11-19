from __future__ import annotations

import json
from pathlib import Path

import polars as pl

from backend.src.app.services.stage_03_5_textops import impl


def _write_shipments(tmp_path: Path, run_id: str) -> tuple[Path, Path, Path]:
    artifacts_root = tmp_path / "artifacts"
    shipments_dir = tmp_path / "raw" / "shipments"
    stage03_dir = artifacts_root / run_id / "stage_03"
    shipments_dir.mkdir(parents=True, exist_ok=True)
    stage03_dir.mkdir(parents=True, exist_ok=True)

    shipments_frame = pl.DataFrame(
        {
            "AWB_NO": ["A1", "A2", "A3"],
            "item_desc": ["SLA good", "SLA bad", "Neutral"],
            "customer_note": ["Check SOP", "Escalate", "Profile"],
            "created_at": [None, None, None],
            "SENDER ADDRESS": ["Riyadh", "Jeddah", "Dammam"],
            "SENDER PHONE": ["+966500000001", "+966500000002", "+966500000003"],
            "RECEIVER ADDRESS": ["Riyadh", "Jeddah", "Dammam"],
            "RECEIVER PHONE": ["+966500000011", "+966500000012", "+966500000013"],
        }
    )
    shipments_path = shipments_dir / "shipments.parquet"
    shipments_frame.write_parquet(shipments_path.as_posix())

    domain_dict_path = stage03_dir / "domain_dict.json"
    domain_dict_path.write_text(json.dumps({"stopwords_ar": [], "stopwords_en": []}), encoding="utf-8")
    text_catalog_path = stage03_dir / "text_columns_catalog.json"
    text_catalog_path.write_text(json.dumps({"text_columns": ["item_desc", "customer_note"]}), encoding="utf-8")
    return shipments_path, domain_dict_path, text_catalog_path


def test_docs_textops_generates_json_payloads(tmp_path: Path) -> None:
    run_id = "docs_run"
    artifacts_root = tmp_path / "artifacts"
    shipments_path, domain_path, catalog_path = _write_shipments(tmp_path, run_id)

    sla_dir = tmp_path / "docs" / "sla"
    sop_dir = tmp_path / "docs" / "sop"
    profile_dir = tmp_path / "docs" / "profile"
    for directory in (sla_dir, sop_dir, profile_dir):
        directory.mkdir(parents=True, exist_ok=True)

    sla_dir.joinpath("client.txt").write_text(
        "CLIENT_ID: CLIENT_123\nCLIENT_NAME: ACME Logistics\nSLA Same-Day: 4 hours zone Riyadh working days Sun Mon Tue Wed Thu\n"
        "KPI on_time: Delivered within 4 hours",
        encoding="utf-8",
    )
    sop_dir.joinpath("rules.txt").write_text(
        "Escalation Level 1 Owner Customer Support SLA 4h\nRole: Field Ops - Duties: Attempt delivery twice; Capture proof\n"
        "Constraint: No escalations on public holidays",
        encoding="utf-8",
    )
    profile_dir.joinpath("profile.txt").write_text(
        "Industries: Fashion, E-commerce\nRegions: Saudi Arabia, GCC\nServices: Same-day urban, Next-day GCC\n"
        "Peak: Q4, Ramadan\nNote: High COD share",
        encoding="utf-8",
    )

    config_payload = {
        "version": "1.0",
        "seed": 42,
        "timezone": "Asia/Riyadh",
        "inputs": {
            "shipments_path": shipments_path.as_posix(),
            "docs_path": str(tmp_path / "raw" / "docs"),
        },
        "sources": {
            "domain_dict": domain_path.as_posix(),
            "text_catalog": catalog_path.as_posix(),
            "kpi_map": "config/kpi_map.yaml",
            "dim_keys": "config/dim_keys.yaml",
        },
        "docs_textops": {
            "enabled": True,
            "doc_roots": {
                "sla": sla_dir.as_posix(),
                "sop": sop_dir.as_posix(),
                "profile": profile_dir.as_posix(),
            },
            "reader_priority": [".txt"],
            "llm_enabled": False,
        },
        "llm": {"enabled": False},
        "rag": {"enabled": False},
    }
    config_path = tmp_path / "textops_docs.yaml"
    config_path.write_text(json.dumps(config_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    result = impl.run(
        run_id,
        inputs={},
        config={"artifacts_root": artifacts_root.as_posix(), "config_path": config_path.as_posix()},
    )
    assert result["status"] in {"PASS", "WARN"}

    phase_dir = artifacts_root / run_id / "stage_03_5_textops"
    sla_path = phase_dir / "sla_policies.json"
    sop_path = phase_dir / "sop_rules.json"
    profile_path = phase_dir / "profile_entities.json"

    assert sla_path.exists()
    assert sop_path.exists()
    assert profile_path.exists()

    sla_payload = json.loads(sla_path.read_text(encoding="utf-8"))
    assert sla_payload["client_id"] == "CLIENT_123"
    assert sla_payload["service_levels"]

    sop_payload = json.loads(sop_path.read_text(encoding="utf-8"))
    assert sop_payload["escalation_steps"]
    assert sop_payload["responsibilities"]

    profile_payload = json.loads(profile_path.read_text(encoding="utf-8"))
    assert "Saudi Arabia" in profile_payload["regions_served"]
    assert "Fashion" in profile_payload["industries"]


def test_docs_textops_missing_docs_warns_but_succeeds(tmp_path: Path) -> None:
    run_id = "docs_empty"
    artifacts_root = tmp_path / "artifacts"
    shipments_path, domain_path, catalog_path = _write_shipments(tmp_path, run_id)

    empty_root = tmp_path / "docs" / "empty"
    empty_root.mkdir(parents=True, exist_ok=True)

    config_payload = {
        "version": "1.0",
        "seed": 42,
        "timezone": "Asia/Riyadh",
        "inputs": {
            "shipments_path": shipments_path.as_posix(),
            "docs_path": str(tmp_path / "raw" / "docs"),
        },
        "sources": {
            "domain_dict": domain_path.as_posix(),
            "text_catalog": catalog_path.as_posix(),
            "kpi_map": "config/kpi_map.yaml",
            "dim_keys": "config/dim_keys.yaml",
        },
        "docs_textops": {
            "enabled": True,
            "doc_roots": {
                "sla": empty_root.as_posix(),
                "sop": empty_root.as_posix(),
                "profile": empty_root.as_posix(),
            },
            "reader_priority": [".txt"],
            "llm_enabled": False,
        },
        "llm": {"enabled": False},
        "rag": {"enabled": False},
    }
    config_path = tmp_path / "textops_docs_empty.yaml"
    config_path.write_text(json.dumps(config_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    result = impl.run(
        run_id,
        inputs={},
        config={"artifacts_root": artifacts_root.as_posix(), "config_path": config_path.as_posix()},
    )
    assert result["status"] in {"PASS", "WARN"}

    phase_dir = artifacts_root / run_id / "stage_03_5_textops"
    sla_path = phase_dir / "sla_policies.json"
    sop_path = phase_dir / "sop_rules.json"
    profile_path = phase_dir / "profile_entities.json"

    assert sla_path.exists()
    assert sop_path.exists()
    assert profile_path.exists()

    sla_payload = json.loads(sla_path.read_text(encoding="utf-8"))
    assert sla_payload["service_levels"] == []

    findings_payload = json.loads((phase_dir / "quality_findings.json").read_text(encoding="utf-8"))
    warn_codes = {entry.get("code") for entry in findings_payload.get("warnings", [])}
    assert any(code and "docs" in code for code in warn_codes)
