"""LLM agents. They interpret and argue; they never supply numbers or sources."""
import os
import re
import json
import time
from google import genai

try:
    import httpx  # installed as a dependency of google-genai
    NETWORK_ERRORS = (httpx.TransportError, ConnectionError, TimeoutError)
except ImportError:
    NETWORK_ERRORS = (ConnectionError, TimeoutError)

CITE = re.compile(r"\[([A-Za-z0-9\-_.]+)\]")


class AutonomousResearchAgents:
    def __init__(self, registry, model=None):
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not set.")
        self.client = genai.Client(api_key=api_key)
        # Override with the GEMINI_MODEL environment variable if needed.
        self.model = model or os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
        self.registry = registry
        self.quote_ids = set()

    @staticmethod
    def _transient(e: Exception) -> bool:
        if isinstance(e, NETWORK_ERRORS):
            return True  # dropped connection, timeout
        code = getattr(e, "code", None) or getattr(e, "status_code", None)
        return code in (408, 429, 500, 502, 503, 504)

    def _call(self, prompt: str, json_out: bool = False, attempts: int = 6) -> str:
        cfg = {"response_mime_type": "application/json"} if json_out else None
        for i in range(attempts):
            try:
                r = self.client.models.generate_content(
                    model=self.model, contents=prompt, config=cfg)
                return r.text.strip()
            except Exception as e:
                if not self._transient(e) or i == attempts - 1:
                    raise  # auth errors, bad model name, or final failure
                wait = 5 * 2 ** i  # 5, 10, 20, 40, 80 seconds
                print(f"    transient error ({type(e).__name__}); retrying in {wait}s "
                      f"(attempt {i + 1}/{attempts})")
                time.sleep(wait)

    def extract_narrative_intent(self, quotes_df) -> str:
        self.quote_ids = set(quotes_df["quote_id"])
        block = "\n".join(
            f"[{r.quote_id}] ({r.quarter}, {r.speaker}) {r.text}" for r in quotes_df.itertuples())
        return self._call(
            "Using ONLY the quotes below, state in 2 sentences what growth driver management "
            "emphasises. Cite quote ids in square brackets after each claim. Do not add facts.\n\n"
            + block)

    def run_adversarial_critique(self, audit: dict, peers: dict, falsification: dict) -> dict:
        prompt = f"""You are a sceptical financial analyst reviewing a hypothesis: that this company's
revenue growth is driven more by realisation per unit than by volume, contrary to management's volume narrative.
Be neutral: assess whether the data supports it.

Company metrics: {json.dumps(audit)}
Peer metrics: {json.dumps(peers)}
Coded falsification test result: {json.dumps(falsification)}

Return JSON with keys:
"counterargument": the strongest defence of the company (e.g. mix shift, cost pass-through, sector-wide pricing).
"peer_read": one sentence on whether peers show the same pattern (say 'no peer data' if empty).
"data_needed": list of up to 3 specific datasets that would best test the counterargument.
Do not invent figures."""
        text = self._call(prompt, json_out=True)
        text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
        return json.loads(text)

    def generate_final_report(self, narrative, audit, peers, critique, falsification,
                              sources_used, is_demo):
        demo_note = ("This run uses SYNTHETIC DEMO DATA: state that prominently and make no "
                     "real-world claims.") if is_demo else ""
        prompt = f"""Draft a discovery report in the ATMOS blueprint format.
Rules: use only the facts given. Every factual claim must carry a source id in square brackets
from the REGISTERED SOURCES list. Cite computed metrics as [ENGINE]. No investment recommendation.
{demo_note}

Management narrative: {narrative}
Company metrics [ENGINE]: {json.dumps(audit)}
Peer metrics [ENGINE]: {json.dumps(peers)}
Critique: {json.dumps(critique)}
Coded falsification result [ENGINE]: {json.dumps(falsification)}
REGISTERED SOURCES:
{self.registry.as_prompt_block(sources_used)}

Use exactly these headers:
Track & prompt: Track C - Find a company whose reported growth is driven by something different from what management emphasises.
The Discovery:
Why it matters:
Evidence trail:
Numbers:
Counterargument:
Falsification condition: (state it and the coded result)
Evidence strength: (Low/Moderate/High with one-line reason; Low if no peer data or channel gap unadjusted)"""
        report = self._call(prompt)
        try:
            self.validate_citations(report, self.quote_ids)
        except ValueError as e:
            report += f"\n\n[CITATION WARNING] {e}. Check these before submitting."
        return report

    def validate_citations(self, report: str, extra_ids=()) -> None:
        """Reject any bracketed id that is not a registered source, quote id or ENGINE."""
        allowed = self.registry.ids | {"ENGINE"} | set(extra_ids)
        unknown = set(CITE.findall(report)) - allowed
        if unknown:
            raise ValueError(f"Report cites unregistered ids: {sorted(unknown)}")
