# Client Data Onboarding — Reconciliation Review

Prototype slice for The Machine: turn conflicting marketing exports into a
ratified **semantic contract**, then serve queries that carry their own caveats.

## Thesis

Onboarding doesn't take weeks because pipelines are hard. It takes weeks because
the definitional questions — does spend include platform fees, does this
conversion count post-view — get answered in Slack, hardcoded into pipeline
logic, and lost. The deliverable of onboarding should not be a pipeline. It
should be a versioned, reviewable, authored contract.

Some conflicts are **irreducible**: two platforms measuring genuinely different
events. The product's job is not to erase that disagreement but to detect it,
force a decision once, record who decided and why, and carry the caveat forward.

## Run

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python generate_sample_data.py     # regenerate the fixtures
streamlit run app.py
```

## What's real vs. stubbed

| Real | Stubbed (on purpose) |
|---|---|
| Deterministic profiler | Connectors — CSVs on disk; extraction is a commodity |
| LLM mapping proposal (live, uncanned) | Warehouse — pandas/duckdb in memory |
| Conflict detection rules | Auth, multi-tenancy — one hardcoded client |
| Contract read/write + versioning | Agent layer — one hardcoded query |
| Caveat propagation into results | Confidence calibration — raw model output |

## Layout

```
generate_sample_data.py   fixtures + the planted-conflict answer key
canonical/metrics.yaml    the target vocabulary + disclosure axes
src/profile.py            REAL  — deterministic profiling
src/propose.py            LIVE  — LLM mapping proposal
src/conflicts.py          LIVE  — deterministic conflict checks
src/contract.py           REAL  — the artifact
src/query.py              LIVE  — query with caveats
app.py                    Streamlit shell
RUNBOOK.md                minute-by-minute session plan
prompts/LIVE_PROMPTS.md   prepared prompts
```
