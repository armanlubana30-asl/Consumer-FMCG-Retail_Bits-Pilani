"""Data loading with provenance checks.

No numbers or quotes live in code. Real data comes from CSVs where every row carries a
source_id that must exist in sources.csv. `--demo` loads clearly-labelled SYNTHETIC data
(the original illustrative figures) so the pipeline can be tested end to end.
"""
import pandas as pd
from sources import SourceRegistry

DEMO = "DEMO-SYNTHETIC"

QUARTERLY_COLS = ["quarter", "auto_revenue_cr", "wholesale_units", "export_units",
                  "retail_vahan_units", "source_id"]
QUOTE_COLS = ["quote_id", "quarter", "speaker", "text", "source_id"]


def _check_cols(df: pd.DataFrame, cols, name: str) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"{name}: missing columns {missing}")


def load_quarterly(path: str, registry: SourceRegistry, company: str = "") -> pd.DataFrame:
    df = pd.read_csv(path)
    _check_cols(df, QUARTERLY_COLS, path)
    for c in ["auto_revenue_cr", "wholesale_units"]:
        if df[c].isna().any() or (df[c] <= 0).any():
            raise ValueError(f"{path}: column {c} must be present and positive on every row")
    registry.require(df["source_id"].unique(), path)
    df["company"] = company or path
    return df.reset_index(drop=True)


def load_quotes(path: str, registry: SourceRegistry) -> pd.DataFrame:
    df = pd.read_csv(path)
    _check_cols(df, QUOTE_COLS, path)
    if df["text"].str.len().lt(20).any():
        raise ValueError(f"{path}: suspiciously short quote text")
    registry.require(df["source_id"].unique(), path)
    return df


def demo_bundle():
    """SYNTHETIC illustrative data. Not sourced. Never submit findings built on this."""
    rows = [
        ("Q1FY25", 16715.0, 186160, 172400), ("Q2FY25", 18532.0, 211057, 194120),
        ("Q3FY25", 19420.0, 218450, 201300), ("Q4FY25", 20850.0, 224100, 208900),
        ("Q1FY26", 19840.0, 199400, 182100), ("Q2FY26", 22100.0, 222500, 198400),
        ("Q3FY26", 23650.0, 229100, 203800), ("Q4FY26", 25200.0, 234800, 209500),
    ]
    df = pd.DataFrame(rows, columns=["quarter", "auto_revenue_cr", "wholesale_units", "retail_vahan_units"])
    df["export_units"] = float("nan")  # unknown -> channel gap flagged as unadjusted
    df["source_id"] = DEMO
    df["company"] = "M&M (synthetic)"
    quotes = pd.DataFrame([{
        "quote_id": "Q1", "quarter": "Q4FY26", "speaker": "SYNTHETIC",
        "text": "Demand remains strong across core SUV platforms with booking backlogs; "
                "our focus is volume market-share expansion. [SYNTHETIC PLACEHOLDER]",
        "source_id": DEMO}])
    registry = SourceRegistry(pd.DataFrame([{
        "source_id": DEMO, "company": "M&M", "doc_type": "synthetic", "title": "Illustrative data only",
        "period": "", "url": "n/a", "page_or_timestamp": ""}]))
    return df, quotes, registry
