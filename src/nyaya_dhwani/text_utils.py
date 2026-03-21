"""Pure-Python helpers shared with the ingestion notebook (testable without Spark)."""

from __future__ import annotations

import re

import pandas as pd


def clean_cols(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize column names for Delta / SQL (matches notebook `clean_cols`)."""
    df = df.copy()
    df.columns = [
        re.sub(r"[\s,;{}()\n\t=]+", "_", str(c)).strip("_")
        for c in df.columns
    ]
    return df
