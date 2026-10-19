"""Source registry: every number and quote must trace back to a registered source."""
from dataclasses import dataclass
import pandas as pd

REQUIRED_SOURCE_COLS = ["source_id", "company", "doc_type", "title", "period", "url", "page_or_timestamp"]


@dataclass(frozen=True)
class SourceRegistry:
    table: pd.DataFrame

    @classmethod
    def from_csv(cls, path: str) -> "SourceRegistry":
        df = pd.read_csv(path, dtype=str).fillna("")
        missing = [c for c in REQUIRED_SOURCE_COLS if c not in df.columns]
        if missing:
            raise ValueError(f"{path}: missing columns {missing}")
        if df["source_id"].duplicated().any():
            raise ValueError(f"{path}: duplicate source_id values")
        blank_url = df[df["url"].str.strip() == ""]
        if len(blank_url):
            raise ValueError(f"{path}: sources without URL: {list(blank_url['source_id'])}")
        return cls(df)

    @property
    def ids(self) -> set:
        return set(self.table["source_id"])

    def require(self, ids, where: str) -> None:
        unknown = set(ids) - self.ids
        if unknown:
            raise ValueError(f"{where}: unregistered source_id(s) {sorted(unknown)}")

    def as_prompt_block(self, only=None) -> str:
        t = self.table if only is None else self.table[self.table["source_id"].isin(only)]
        return "\n".join(
            f"[{r.source_id}] {r.company} | {r.doc_type} | {r.title} | {r.period} | {r.page_or_timestamp} | {r.url}"
            for r in t.itertuples()
        )
