"""describe.py — turn CSV text into pandas `describe()` output that is JSON-safe."""

from __future__ import annotations

import io
import math
from typing import Any

import pandas as pd

MAX_BYTES = 5 * 1024 * 1024  # 5 MB


def _clean(value: Any) -> Any:
    """Make a pandas/numpy scalar JSON-safe (NaN/inf -> None, numpy -> python)."""
    if value is None or (pd.api.types.is_scalar(value) and pd.isna(value)):
        return None  # None, NaN, NaT and pd.NA all become JSON null
    if hasattr(value, "item"):  # numpy scalar
        value = value.item()
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return round(value, 6)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value if isinstance(value, (int, float, str, bool)) else str(value)


def load_csv(text: str) -> pd.DataFrame:
    if not text or not text.strip():
        raise ValueError("The file is empty.")
    if len(text.encode("utf-8")) > MAX_BYTES:
        raise ValueError("File is larger than 5 MB.")
    # sep=None + python engine sniffs the delimiter (comma, semicolon, tab, pipe).
    df = pd.read_csv(io.StringIO(text), sep=None, engine="python")
    if df.empty:
        raise ValueError("The file has a header but no data rows.")
    return _coerce_numeric(df)


def _coerce_numeric(df: pd.DataFrame, threshold: float = 0.95) -> pd.DataFrame:
    """Convert text columns that are really numbers (e.g. "10,400", "12%") so describe() treats them as numeric."""
    for col in df.columns:
        if not (pd.api.types.is_object_dtype(df[col]) or pd.api.types.is_string_dtype(df[col])):
            continue  # already numeric/datetime/bool (pandas 3 uses a 'str' dtype for text, older pandas 'object')
        s = df[col].dropna().astype(str).str.strip()
        if s.empty:
            continue
        cleaned = s.str.replace(r"(?<=\d),(?=\d{3}\b)", "", regex=True).str.rstrip("%")
        nums = pd.to_numeric(cleaned, errors="coerce")
        if nums.notna().mean() >= threshold:
            full = df[col].astype("string").str.strip().str.replace(r"(?<=\d),(?=\d{3}\b)", "", regex=True).str.rstrip("%")
            df[col] = pd.to_numeric(full, errors="coerce").astype("float64")
    return df


def describe_frame(df: pd.DataFrame, name: str) -> dict[str, Any]:
    """`df.describe(include="all")` plus dtype, missing counts and a preview."""
    desc = df.describe(include="all")  # rows = statistics, columns = dataframe columns
    stats = [str(s) for s in desc.index]  # e.g. count, unique, top, freq, mean, std, min, 25%, 50%, 75%, max
    columns = []
    for col in df.columns:
        columns.append(
            {
                "name": str(col),
                "dtype": str(df[col].dtype),
                "missing": int(df[col].isna().sum()),
                "values": {s: _clean(desc.at[s, col]) for s in desc.index},
            }
        )
    return {
        "name": name,
        "shape": {"rows": int(df.shape[0]), "columns": int(df.shape[1])},
        "statistics": stats,
        "columns": columns,
        "preview": {
            "columns": [str(c) for c in df.columns],
            "rows": [[_clean(v) for v in row] for row in df.head(5).itertuples(index=False)],
        },
    }


def describe_text(df: pd.DataFrame, name: str) -> str:
    """Plain-text version for Claude and for hosts that don't render the UI."""
    with pd.option_context("display.max_columns", 50, "display.width", 200):
        table = df.describe(include="all").to_string()
    return f'Dataset "{name}": {df.shape[0]} rows x {df.shape[1]} columns\n\ndf.describe(include="all"):\n{table}'
