"""Deterministic analytics: exact revenue decomposition, peer comparison, coded falsification."""
import pandas as pd
from typing import Dict, Any, Optional

LAG = 4  # YoY


class RealizationEngine:
    @staticmethod
    def run_decomposition(df: pd.DataFrame, lag: int = LAG) -> pd.DataFrame:
        """Midpoint (Shapley) split of YoY revenue change into volume and realisation effects.

        dRev = V1*P1 - V0*P0 = dV*(P0+P1)/2 + dP*(V0+V1)/2   (exact, no residual)
        'Realisation' = revenue per unit: price AND mix AND scope effects. Separating pure price
        from mix needs variant-level data, which this engine does not claim to have.
        """
        df = df.copy()
        df["asp_lakhs"] = df["auto_revenue_cr"] * 100.0 / df["wholesale_units"]
        v0, p0 = df["wholesale_units"].shift(lag), df["asp_lakhs"].shift(lag)
        v1, p1 = df["wholesale_units"], df["asp_lakhs"]
        df["delta_revenue_cr"] = df["auto_revenue_cr"].diff(lag)
        df["volume_yoy_pct"] = (v1 / v0 - 1) * 100.0
        df["volume_effect_cr"] = (v1 - v0) * (p0 + p1) / 2.0 / 100.0
        df["realisation_effect_cr"] = (p1 - p0) * (v0 + v1) / 2.0 / 100.0

        resid = (df["volume_effect_cr"] + df["realisation_effect_cr"] - df["delta_revenue_cr"]).abs()
        if (resid.dropna() > 1e-6).any():
            raise AssertionError("Decomposition does not reconcile to revenue change")

        # Shares are only meaningful when revenue grew; otherwise leave NaN rather than mislead.
        grew = df["delta_revenue_cr"] > 0
        df["pct_from_realisation"] = (df["realisation_effect_cr"] / df["delta_revenue_cr"] * 100.0).where(grew)
        df["pct_from_volume"] = (df["volume_effect_cr"] / df["delta_revenue_cr"] * 100.0).where(grew)

        # Channel proxy: dispatches vs retail. Exports are in wholesale but not in domestic Vahan.
        exp_known = df["export_units"].notna()
        domestic = df["wholesale_units"] - df["export_units"].fillna(0)
        df["channel_gap_units"] = domestic - df["retail_vahan_units"]
        df["channel_gap_adjusted"] = exp_known
        df["channel_gap_pct_of_retail"] = df["channel_gap_units"] / df["retail_vahan_units"] * 100.0
        return df

    @staticmethod
    def audit_anomaly(df: pd.DataFrame, n: int = 4) -> Dict[str, Any]:
        recent = df.dropna(subset=["pct_from_realisation", "pct_from_volume"]).tail(n)
        if recent.empty:
            raise ValueError("No quarters with positive YoY revenue growth to audit")
        return {
            "quarters_used": list(recent["quarter"]),
            "avg_realisation_share_pct": round(float(recent["pct_from_realisation"].mean()), 1),
            "avg_volume_share_pct": round(float(recent["pct_from_volume"].mean()), 1),
            "avg_volume_yoy_pct": round(float(recent["volume_yoy_pct"].mean()), 1),
            "cumulative_channel_gap_units": int(recent["channel_gap_units"].sum()),
            "channel_gap_is_export_adjusted": bool(recent["channel_gap_adjusted"].all()),
            "channel_gap_note": "Proxy only: Vahan registration lags/category mismatches are not corrected.",
        }

    @staticmethod
    def peer_comparison(company_df: pd.DataFrame, peers: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        out = {}
        for name, pdf in peers.items():
            d = RealizationEngine.run_decomposition(pdf)
            out[name] = RealizationEngine.audit_anomaly(d)
        mine = RealizationEngine.audit_anomaly(company_df)
        out["_company_vs_peer_realisation_gap_pp"] = (
            round(mine["avg_realisation_share_pct"] - sum(
                v["avg_realisation_share_pct"] for k, v in out.items() if not k.startswith("_")
            ) / max(1, len(peers)), 1) if peers else None)
        return out

    @staticmethod
    def evaluate_falsification(df: pd.DataFrame, share_threshold: float = 50.0,
                               consecutive: int = 2) -> Dict[str, Any]:
        """Thesis: growth is realisation-led (volume share < threshold) despite a volume narrative.
        Falsified if volume explains >= threshold of revenue growth in the latest `consecutive`
        quarters with positive revenue growth."""
        d = df.dropna(subset=["pct_from_volume"]).tail(consecutive)
        condition = (f"Volume effect >= {share_threshold:.0f}% of YoY revenue growth in each of the latest "
                     f"{consecutive} growing quarters")
        if len(d) < consecutive:
            return {"condition": condition, "status": "INSUFFICIENT_DATA", "evidence": []}
        met = bool((d["pct_from_volume"] >= share_threshold).all())
        return {
            "condition": condition,
            "status": "THESIS_FALSIFIED" if met else "THESIS_SURVIVES",
            "evidence": [{"quarter": r.quarter, "volume_share_pct": round(float(r.pct_from_volume), 1)}
                         for r in d.itertuples()],
        }
