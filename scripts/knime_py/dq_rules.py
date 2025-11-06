from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd


@dataclass
class RuleResult:
    rule_id: str
    passed: bool
    details: Dict[str, Any]


def _missing_columns(df: pd.DataFrame, required: Iterable[str]) -> List[str]:
    return [col for col in required if col not in df.columns]


def apply_rules(
    df: pd.DataFrame,
    *,
    required_columns: Optional[Iterable[str]] = None,
    max_null_fraction: float = 0.25,
) -> Dict[str, Any]:
    """Execute lightweight data-quality checks on a DataFrame.

    Parameters
    ----------
    df:
        The dataframe loaded inside a KNIME Python Script node.
    required_columns:
        Columns that must exist; missing ones are reported as violations.
    max_null_fraction:
        Threshold for flagging a column with excessive null values.
    """

    rules: List[RuleResult] = []
    total_rows = int(df.shape[0])

    if required_columns:
        missing = _missing_columns(df, required_columns)
        rules.append(
            RuleResult(
                rule_id="required_columns",
                passed=len(missing) == 0,
                details={"missing": missing},
            )
        )

    if total_rows > 0:
        null_fractions = (df.isna().sum() / total_rows).to_dict()
    else:
        null_fractions = {col: 0.0 for col in df.columns}
    flagged_nulls = {col: frac for col, frac in null_fractions.items() if frac > max_null_fraction}
    rules.append(
        RuleResult(
            rule_id="null_fraction",
            passed=len(flagged_nulls) == 0,
            details={"flagged": flagged_nulls, "threshold": max_null_fraction},
        )
    )

    duplicates = int(df.duplicated().sum())
    rules.append(
        RuleResult(
            rule_id="duplicate_rows",
            passed=duplicates == 0,
            details={"duplicate_count": duplicates},
        )
    )

    summary = {
        "total_rows": total_rows,
        "total_columns": int(df.shape[1]),
        "rules_executed": len(rules),
        "rules_failed": sum(1 for rule in rules if not rule.passed),
    }

    return {
        "summary": summary,
        "results": [
            {
                "rule_id": rule.rule_id,
                "passed": rule.passed,
                "details": rule.details,
            }
            for rule in rules
        ],
    }
