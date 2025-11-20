from __future__ import annotations

import importlib

import polars as pl

payment_module = importlib.import_module("phases.06_feature_eng.payment")
derive_payment_type = payment_module.derive_payment_type
load_payment_rules = payment_module.load_payment_rules


def _base_rules() -> dict:
    return {
        "priority_signals": [],
        "fallback_by_cod_amount": {"enabled": True, "treat_zero_dash_empty_as": "Prepaid", "treat_positive_as": "COD"},
        "explicit_prepaid_flag": {},
    }


def test_payment_type_priority_signal_overrides():
    rules = _base_rules()
    rules["priority_signals"] = [
        {"column": "PAYMENT_METHOD", "mapping": {"COD": "COD", "PREPAID": "Prepaid"}},
    ]
    df = pl.DataFrame(
        {
            "PAYMENT_METHOD": ["COD", "PREPAID", "UNKNOWN"],
            "COD_AMOUNT": ["100", "0", "SAR 55"],
        }
    )
    result = derive_payment_type(df, rules)
    assert result["PAYMENT_TYPE"].to_list() == ["COD", "Prepaid", "COD"]


def test_payment_type_cod_amount_fallback_handles_dirty_values():
    rules = _base_rules()
    df = pl.DataFrame(
        {
            "COD_AMOUNT": ["0", "0.0", "-", "", None, "SAR 0", "SAR 120", "120 SAR", "50.00SAR"],
        }
    )
    result = derive_payment_type(df, rules)
    expected = ["Prepaid", "Prepaid", "Prepaid", "Prepaid", "Prepaid", "Prepaid", "COD", "COD", "COD"]
    assert result["PAYMENT_TYPE"].to_list() == expected


def test_explicit_prepaid_flag_overrides_positive_cod():
    rules = _base_rules()
    rules["explicit_prepaid_flag"] = {"column": "IS_PREPAID", "truthy_values": ["Y"]}
    df = pl.DataFrame(
        {
            "COD_AMOUNT": ["150", "20", "0"],
            "IS_PREPAID": ["Y", "N", None],
        }
    )
    result = derive_payment_type(df, rules)
    assert result["PAYMENT_TYPE"].to_list() == ["Prepaid", "COD", "Prepaid"]


def test_payment_type_unknown_when_no_signals():
    rules = _base_rules()
    rules["fallback_by_cod_amount"]["enabled"] = False
    df = pl.DataFrame({"STATUS": ["Delivered", "RTO"]})
    result = derive_payment_type(df, rules)
    assert result["PAYMENT_TYPE"].to_list() == ["Unknown", "Unknown"]


def test_load_payment_rules_merges_client_override(tmp_path):
    contracts_dir = tmp_path / "contracts"
    payment_dir = contracts_dir / "payment"
    payment_dir.mkdir(parents=True)
    config = """
default:
  fallback_by_cod_amount:
    enabled: false
clients:
  FASTCOO:
    fallback_by_cod_amount:
      enabled: true
      treat_positive_as: "COD"
"""
    (payment_dir / "payment_rules.yml").write_text(config, encoding="utf-8")
    default_rules = load_payment_rules(contracts_dir, None)
    assert default_rules["fallback_by_cod_amount"]["enabled"] is False
    fastcoo_rules = load_payment_rules(contracts_dir, "fastcoo")
    assert fastcoo_rules["fallback_by_cod_amount"]["enabled"] is True
    assert fastcoo_rules["fallback_by_cod_amount"]["treat_positive_as"] == "COD"
