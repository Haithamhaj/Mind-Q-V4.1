from __future__ import annotations

from typing import Iterable, Optional, Sequence

import pandas as pd


def prepare_features(
    df: pd.DataFrame,
    *,
    numeric_columns: Optional[Sequence[str]] = None,
    categorical_columns: Optional[Sequence[str]] = None,
    dropna: bool = True,
) -> pd.DataFrame:
    """Return a modelling-ready frame with basic encoding and filtering.

    - Keeps the requested numeric columns as-is.
    - Applies one-hot encoding to the provided categorical columns.
    - Drops rows with missing values by default to simplify KNIME nodes downstream.
    """

    working = df.copy()
    if numeric_columns:
        missing_numeric = [col for col in numeric_columns if col not in working.columns]
        if missing_numeric:
            raise KeyError(f"Missing numeric columns: {missing_numeric}")
        numeric_part = working.loc[:, list(numeric_columns)]
    else:
        numeric_part = working.select_dtypes(include=["number"])

    if categorical_columns:
        missing_categoricals = [col for col in categorical_columns if col not in working.columns]
        if missing_categoricals:
            raise KeyError(f"Missing categorical columns: {missing_categoricals}")
        categoricals = working.loc[:, list(categorical_columns)]
    else:
        categoricals = working.select_dtypes(include=["object", "category"])

    if not categoricals.empty:
        encoded = pd.get_dummies(categoricals, dummy_na=False, drop_first=False)
        combined = pd.concat([numeric_part, encoded], axis=1)
    else:
        combined = numeric_part

    if dropna:
        combined = combined.dropna(axis=0, how='any')

    return combined.reset_index(drop=True)
