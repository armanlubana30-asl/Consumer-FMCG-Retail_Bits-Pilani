import argparse
import pandas as pd
from data_pipeline import demo_bundle, load_quarterly, load_quotes, DEMO
from sources import SourceRegistry
from engine import RealizationEngine

try:
    from tabulate import tabulate
    def show(df): print(tabulate(df, headers="keys", tablefmt="psql", floatfmt=".2f", showindex=False))
except ImportError:
    def show(df): print(df.to_string(index=False, float_format=lambda x: f"{x:.2f}"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="synthetic data, for testing only")
    ap.add_argument("--data", default="data/mandm_quarterly.csv")
    ap.add_argument("--quotes", default="data/mandm_quotes.csv")
    ap.add_argument("--sources", default="data/sources.csv")
    ap.add_argument("--peers", nargs="*", default=[], help="name=path.csv for each peer")
    ap.add_argument("--no-llm", action="store_true", help="run the deterministic engine only")
    a = ap.parse_args()

    print("=" * 70)
    print("AUTONOMOUS FINANCIAL RESEARCH AGENT - ATMOS 2026 | Track C")
    print("=" * 70)

    if a.demo:
        df, quotes, registry = demo_bundle()
        print("*** SYNTHETIC DEMO DATA - NOT A REAL FINDING ***")
    else:
        registry = SourceRegistry.from_csv(a.sources)
        df = load_quarterly(a.data, registry, "Mahindra & Mahindra")
        quotes = load_quotes(a.quotes, registry)

    peers = {}
    for spec in a.peers:
        name, path = spec.split("=", 1)
        peers[name] = load_quarterly(path, registry, name)

    d = RealizationEngine.run_decomposition(df)
    cols = ["quarter", "asp_lakhs", "volume_yoy_pct", "pct_from_volume", "pct_from_realisation",
            "channel_gap_pct_of_retail"]
    print("\nYoY revenue decomposition (volume + realisation = 100% of revenue change):")
    show(d[cols].dropna(subset=["pct_from_volume"]))

    audit = RealizationEngine.audit_anomaly(d)
    peer_metrics = RealizationEngine.peer_comparison(d, peers) if peers else {}
    fals = RealizationEngine.evaluate_falsification(d)
    print("\nAudit:", audit)
    print("Falsification:", fals)
    if not audit["channel_gap_is_export_adjusted"]:
        print("[!] Channel gap is NOT export-adjusted; treat as indicative only.")
    if a.no_llm:
        return

    from agents import AutonomousResearchAgents
    agents = AutonomousResearchAgents(registry)
    print("\n[+] A: narrative extraction")
    narrative = agents.extract_narrative_intent(quotes)
    print("[+] B: adversarial critique")
    critique = agents.run_adversarial_critique(audit, peer_metrics, fals)
    print("[+] C: report")
    used = set(df["source_id"]) | set(quotes["source_id"]) | {s for p in peers.values() for s in p["source_id"]}
    report = agents.generate_final_report(narrative, audit, peer_metrics, critique, fals, used, a.demo)
    print("=" * 70); print(report); print("=" * 70)


if __name__ == "__main__":
    main()
