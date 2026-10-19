# Autonomous Financial Research Agent - ATMOS 2026 (Track C)

Hackathon: *Finding the Next Signal*, BITS Pilani Hyderabad. Track C (Consumer, FMCG & Retail), prompt 1:
find a company whose reported growth is driven by something different from what management emphasises.
Company under study: Mahindra & Mahindra.

## How it works

1. **Data loading** (`data_pipeline.py`, `sources.py`): reads CSVs. Every row and quote must carry a
   `source_id` registered in `data/sources.csv` (with URL). Unregistered sources stop the run.
2. **Deterministic engine** (`engine.py`): splits YoY revenue change into a volume effect and a
   realisation effect (midpoint method, reconciles exactly), builds an export-adjustable channel-gap
   proxy, compares peers, and evaluates the falsification condition in code.
3. **LLM agents** (`agents.py`): extract management narrative from quotes, argue the strongest
   counterargument, and draft the report. The LLM never supplies numbers or sources; citations are
   checked against the registry.
4. **Orchestration** (`main.py`): runs the steps and prints the report.

"Realisation" means revenue per unit (price + mix + scope). The data cannot separate pure price from mix.

## Files

| File | Purpose |
|---|---|
| `main.py` | Entry point, command-line options |
| `engine.py` | Decomposition, peer comparison, falsification test |
| `agents.py` | Gemini agents, retries, response cache, citation check |
| `data_pipeline.py` | CSV loaders with validation, synthetic demo data |
| `sources.py` | Source registry |
| `data/sources.csv` | One row per source document (URL required) |
| `data/mandm_quarterly.csv` | Quarterly figures (header only until you fill it) |
| `data/mandm_quotes.csv` | Real transcript excerpts (header only until you fill it) |

## Setup (Windows)

1. Install Python 3.10+ from python.org. **Tick "Add python.exe to PATH".**
2. Unzip the project, open Command Prompt in the folder that contains `main.py`
   (File Explorer address bar -> type `cmd` -> Enter).
3. Create and activate a virtual environment:
   ```
   python -m venv venv
   venv\Scripts\activate
   ```
4. Install libraries:
   ```
   python -m pip install pandas google-genai tabulate
   ```
5. Set your Gemini key (get one at aistudio.google.com). Never paste it into code, chats or screenshots:
   ```
   set GEMINI_API_KEY=your_key_here
   ```
   Optional model override (leave unset to use the default `gemini-3.8-flash`):
   ```
   set GEMINI_MODEL=real-model-name
   ```

## Running

```
python main.py --demo --no-llm     # engine only, synthetic data, no API needed
python main.py --demo              # full pipeline on synthetic data (3 API requests)
python main.py --no-llm            # engine only on your real CSVs
python main.py                     # full pipeline on real data
python main.py --peers Tata=data\tata.csv Maruti=data\maruti.csv
python main.py > report.txt        # save output
```

Demo data is synthetic and unsourced. It only proves the pipeline works. Never submit a finding built on it.

### CSV formats

- `sources.csv`: `source_id,company,doc_type,title,period,url,page_or_timestamp`
- `mandm_quarterly.csv`: `quarter,auto_revenue_cr,wholesale_units,export_units,retail_vahan_units,source_id`
  (need at least 5 quarters for YoY, ideally 8; leave `export_units` empty if unknown)
- `mandm_quotes.csv`: `quote_id,quarter,speaker,text,source_id`
- Peer files use the same format as `mandm_quarterly.csv`.
- Save as CSV (not .xlsx). Put quotes containing commas inside double quotes.

## Issues encountered and fixes

| # | Issue | Cause | Fix |
|---|---|---|---|
| 1 | `ModuleNotFoundError: No module named 'pandas'` | Libraries not installed in the venv | `python -m pip install pandas google-genai tabulate` in the activated venv |
| 2 | `404 NOT_FOUND ... gemini-2.5-flash no longer available to new users` | Outdated default model | Default is now `gemini-3.8-flash`; override with `GEMINI_MODEL` |
| 3 | `ServerError` / 503 during calls | Temporary Google overload | Automatic retry with backoff (5, 10, 20, 40, 80 s) |
| 4 | `RemoteProtocolError: Server disconnected` | Dropped connection; retry logic only recognised HTTP status codes | Network errors (httpx transport errors, timeouts) now retried |
| 5 | `IndentationError: unindent does not match any outer indentation level` | Mixed tabs/spaces from hand-pasted edits | Replace the whole `agents.py` instead of patching; use spaces only |
| 6 | `429 RESOURCE_EXHAUSTED ... PerDay ... limit: 20` | Free-tier daily quota (20 requests/model/day) used up, partly by retries | Wait for reset, use a model with free quota, or enable billing. Daily-quota errors now fail fast; responses cached in `.llm_cache.json` so reruns cost nothing |
| 7 | `No quarters with positive YoY revenue growth to audit` | Ran without `--demo` while `data/` CSVs were still header-only | Fill the CSVs (5+ quarters) or use `--demo` |
| 8 | `GEMINI_MODEL` set to placeholder text | Literal `model-name-from-that-page` was set | Clear it with `set GEMINI_MODEL=` |
| 9 | API key visible in a screenshot | Key typed in terminal and captured | Delete the key in AI Studio and create a new one; never share it |
| 10 | AFC notice about `generate_content` | Harmless library message | Ignore |

## Why it is not working: diagnostic checklist

Work through these in order. The first match is usually the cause.

1. **Nothing runs, "python is not recognized".** Python is not installed or not on PATH. Reinstall and tick "Add python.exe to PATH", or try `py main.py`.
2. **`ModuleNotFoundError`.** The venv is not active or the libraries are not installed. Run `venv\Scripts\activate`, then `python -m pip install pandas google-genai tabulate`.
3. **`No quarters with positive YoY revenue growth to audit` (the most common failure on real data).** The CSVs in `data/` are header-only, have fewer than 5 quarters, or revenue never grew year on year. This is not a code bug: fill `data/` with real figures, or run with `--demo`.
4. **`unregistered source_id`.** A `source_id` in a data or quotes file is missing from `data/sources.csv`. Add it, with a URL.
5. **`GEMINI_API_KEY not set`.** `set` only lasts for the current window. Set the key in the same window you run Python from.
6. **`404 NOT_FOUND` model error.** The model name is wrong or retired, or `GEMINI_MODEL` holds placeholder text. Clear it with `set GEMINI_MODEL=` or set a real model name from AI Studio.
7. **`429 RESOURCE_EXHAUSTED` with `PerDay`.** The free daily quota is used up. Waiting seconds does not help. Wait for the reset, switch to a model that still has quota, or enable billing. Cached responses cost no quota, so rerunning the same input is free.
8. **`ServerError` or `Server disconnected`.** Google's servers are overloaded or the connection dropped. The code retries automatically. If all 6 attempts fail, rerun later, turn off any VPN, or try a different network.
9. **`IndentationError`.** Mixed tabs and spaces from hand-edited code. Replace the whole file rather than patching it.
10. **Report cites sources that do not exist.** Look for a `[CITATION WARNING]` under the report and fix the source registry or the prompt before submitting.
11. **Output looks fine but is not a finding.** If it says SYNTHETIC DEMO DATA, the numbers are illustrative. A real discovery needs sourced M&M data and peers.

If none of these match, run `python main.py --demo --no-llm`. If that works, the engine is fine and the problem is the API side (items 5 to 8) or your data files (items 3 and 4).

## Methodology issues found in the original code (all fixed)

- Hardcoded, unsourced data and an unsourced management "quote" -> now CSV-only with source registry; demo data labelled synthetic.
- Decomposition omitted the cross term (shares did not sum to 100%) -> midpoint split with reconciliation assertion.
- "Price hikes" claimed from a blended revenue-per-unit figure -> renamed to realisation (price + mix + scope).
- Shares computed even when revenue fell -> left blank in those quarters.
- Channel gap ignored exports and was read as dealer inventory -> export-adjustable, flagged as a proxy.
- Adversarial prompt was leading and saw only aggregates -> neutral prompt with peer data and the coded falsification result.
- Falsification condition was only LLM text -> evaluated in code.
- Report could invent an evidence trail -> sources restricted to the registry, citations validated, Evidence strength header added.
- Retried every exception, including auth and model-name errors -> only transient errors are retried.

## Known limitations

- Demo output is not a finding. Real M&M data, quotes and peers still have to be added.
- In the demo report the critique's "data needed" list was tagged `[ENGINE]`, which is not strictly correct (it came from the LLM). Check citation tags before submitting.
- The channel gap is an unadjusted proxy unless export figures are supplied (Vahan lags and category mismatches are not corrected).
- Keep claims modest: the demo's "potential inventory build-up" wording is stronger than an unadjusted proxy supports.
- The brief gives conflicting Round 1 deadlines (15 October in one place, 19 October in another) and a "2025" typo for the finals date. Confirm with the organisers; assume the 15th.
- Python 3.14 is very new; if odd library errors appear, recreate the venv with Python 3.12.
- No investment recommendation is made or should be added (brief rule).
