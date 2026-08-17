# Demo Script — Client Data Onboarding (Reconciliation Review)

**Audience:** technical interview / panel  
**Runtime:** ~60–75 minutes (15 min thesis + 45–60 min walkthrough)  
**Working directory:** `machine-onboarding/`  
**App URL:** http://localhost:8501  

This script walks the **running prototype** stage by stage: what you do, what the
system does, what to say, and what you should see. It assumes the live-build
modules (`propose`, `conflicts`, query tab, conflict queue) are already
implemented — use `RUNBOOK.md` + `prompts/LIVE_PROMPTS.md` if you are building
them live instead.

---

## 0. Pre-flight (before the call)

### Environment

```bash
cd machine-onboarding
pip install -r requirements.txt          # use the same Python as Streamlit
# Prefer Anaconda if that is where packages were installed:
#   /opt/anaconda3/bin/pip install -r requirements.txt
#   /opt/anaconda3/bin/streamlit run app.py
```

### Secrets

- Put `ANTHROPIC_API_KEY=…` in `machine-onboarding/.env` (loaded by `propose.py`
  via `python-dotenv`), **or** export it in the shell that launches Streamlit.
- Smoke-test one Claude call before the panel joins.

### Clean demo state

```bash
rm -f contracts/acme.yaml
python generate_sample_data.py
/opt/anaconda3/bin/streamlit run app.py
```

Confirm:

| Check | Expected |
|---|---|
| Tab **1 · Profile** | Two source profiles render with no errors |
| Tab **4 · Contract** | “No contract written yet.” |
| Tab **2 / 3 / 5** | Idle until you run proposal / detect / query |
| Browser | http://localhost:8501 |

### Planted conflicts (answer key)

Say this only if asked *“how did you make the sample data?”* — it lives in
`generate_sample_data.py`:

| # | Kind | What was planted |
|---|---|---|
| 1 | NAMING | `spend` vs `cost_micros` |
| 2 | UNIT | USD decimal vs micros (`×1e6`) |
| 3 | INCLUSION | spend ex-fees vs cost incl-fees (invisible in values) |
| 4 | GRAIN | daily (Metriq) vs weekly (Lumen) |
| 5 | DEFINITION | int conversions 7d/1d-view vs fractional data-driven 30d |
| 6 | DEFINITION | link clicks vs all clicks (docs only) |
| 7 | CURRENCY | Lumen EMEA rows in GBP |
| 8 | FIELD NAME | literal `impr.` column |
| 9 | ENTITY | same concept, different campaign IDs/names (out of scope) |
| 10 | DOC LIES | taxonomy asserts naming + spend rules the data violate |

---

## 1. Opening thesis (minutes 0–15)

**Do not open the app yet.** Land the argument first.

### Beats (say out loud)

1. **Reframe.** Onboarding takes weeks because of judgment calls (fees,
   attribution windows), not because extraction is hard. Those answers get
   Slack’d, hardcoded, and lost.
2. **Three layers.** Land → **Resolve (the product)** → Serve. The artifact is
   a versioned **semantic contract**.
3. **Irreducible conflict.** A 7-day-click conversion and a data-driven
   conversion are different events. Summing them is *data laundering*.
4. **Risks.** Silent wrong answers > treating the taxonomy doc as truth >
   work that doesn’t compound across clients > humans becoming the bottleneck
   on obvious fields.
5. **Slice metrics.** Time-to-first-*trusted*-query; auto-map rate across
   clients; human review minutes per source; contradiction escape rate.
6. **Real vs stubbed.** Name stubs: connectors, warehouse, auth, multi-tenancy,
   query agent. Real: profiler, LLM propose, conflict agent (schema scan +
   tools), contract YAML, caveat-bearing query.

**Transition line (minute ~15):**

> “I’ve deliberately left room for you to break this. Interrupt whenever.
> Streamlit is already running — let’s look at what the system does before a
> model is involved.”

---

## 2. Stage A — Profile (deterministic evidence)

**Tab:** `1 · Profile`  
**Code:** `src/profile.py` (pre-built)  
**LLM?** No.

### What you do

1. Open **1 · Profile**.
2. Scroll both sources: `metriq_ads`, `lumen_search`.

### What the system does

For each CSV:

1. Infer field types (date / numeric / string).
2. Compute null %, distinct count, sample values.
3. For numerics: min / max / mean, `has_decimals`, magnitude hints (micros).
4. Detect reporting **grain** from date gaps (`daily` vs `weekly`).
5. Render a compact text block (`to_llm_context`) — this is what later gets
   sent to Claude.

### What to point at

| Signal | Where | Line to say |
|---|---|---|
| `grain=daily` vs `grain=weekly` | Source headers | “Join is already a decision, not a SQL problem.” |
| `cost_micros` magnitude hint | Lumen fields | “Median > 1e6 — silent million× error if you map spend without a transform.” |
| `has_decimals=True` on Lumen `conversions` | Lumen fields | “That’s the tell for modelled attribution. The profiler found it; the model doesn’t get to invent it later.” |
| `campaign_id` micros false positive | Metriq | “Rules alone are brittle — the model adjudicates; rules catch unit/grain/definition after.” |

### Exit criteria

Panel has seen that **evidence gathering is deterministic and boring on purpose**.

---

## 3. Stage B — Propose mappings (LLM)

**Tab:** `2 · Proposed mapping`  
**Code:** `src/propose.py` → `propose_mappings`  
**LLM?** Yes — Claude (`claude-sonnet-4-6`).

### What you do

1. Open **2 · Proposed mapping**.
2. Click **Run proposal**.
3. Wait for the spinner (“Asking the model for mappings…”).
4. Expand a few low-confidence rows; leave high-confidence ones collapsed.

### What the system does

1. Builds profile text for both sources.
2. Loads `canonical/metrics.yaml` (target vocabulary + disclosure axes).
3. Loads `data/acme_taxonomy.md` (client standards — **evidence, not authority**).
4. Calls Claude with a system prompt that requires:
   - Doc vs data disagreements → **report**, don’t silently pick a side.
   - Undetermined disclosure axes → **`"unknown"`** (never guess attribution windows).
   - Strict JSON matching the `Proposal` dataclass (fences stripped defensively).
5. Stores `list[Proposal]` in Streamlit session state.
6. UI groups proposals by **`canonical_key`** so cross-source collisions appear
   together; collapses confidence **> 0.9** by default.

### What each proposal contains

| Field | Meaning |
|---|---|
| `source` / `source_field` | Origin column |
| `canonical_key` | Target metric/dimension (or unmapped) |
| `confidence` | Model certainty (UI collapse threshold 0.9) |
| `unit_transform` | e.g. `divide_by_1e6` for micros |
| `disclosures` | Axes like `fee_inclusion`, `attribution_window` |
| `evidence` / `reasoning` | Why — including doc/data tension |

### What you should see

- `metriq_ads.spend` and `lumen_search.cost_micros` both under **`media_spend`**,
  with transform on the micros field.
- `conversions` from both sources grouped together (definition conflict becomes
  visible once disclosures differ or look unknown).
- High-confidence identity fields (`date`, `impressions`, …) collapsed.

### Lines to say

> “The taxonomy doc is evidence, not authority. A mapping layer that never
> returns `unknown` is a mapping layer that lies.”

> “Grouping by canonical key is the whole UI trick — conflicts only appear when
> two sources claim the same metric.”

### Exit criteria

Session has proposals; collisions are visible under shared canonical keys.

---

## 4. Stage C — Detect conflicts (schema scan + agent)

**Tab:** `3 · Conflict queue`  
**Code:** `src/conflicts.py` → `detect`  
**LLM?** Schema scan is deterministic. Agent is a tool-using Claude loop.

### What you do

1. Stay on / open **3 · Conflict queue**.
2. Click **Detect conflicts**.
3. Point at the metrics: schema count vs agent-submitted vs turns.
4. Confirm `contracts/acme.yaml` appears (seeded with mappings + open conflicts).

### What the system does

**Layer 1 — schema scan** (no LLM). Collision groups × the disclosure axes on
that canonical metric in `metrics.yaml`. Adding an axis is a new conflict
class; you do not ship a new if-statement. Grain, unit transform, coverage,
and a mixed `currency` column come from the profiler.

**Layer 2 — agent** (tools). Inspects groups and sources, searches the taxonomy
doc, submits what the schema cannot see: `DOC_CONTRADICTION`, naming
violations, entity-scope. Python raises severity to the policy floor — the
agent cannot AUTO an irreducible definition.

| Kind | Severity floor | Typical trigger |
|---|---|---|
| **GRAIN_MISMATCH** | `REVIEW` | Profiles disagree (`daily` vs `weekly`) |
| **UNIT_MISMATCH** | `AUTO` | Same canonical key, different `unit_transform` |
| **DEFINITION_DIVERGENCE** | `BLOCK` if `attribution_model` / `attribution_window`; else `REVIEW` | Known disclosure values disagree (`unknown` ignored) |
| **CURRENCY_MIXED** | `BLOCK` | Distinct currency values in one source field |
| **COVERAGE_GAP** | `REVIEW` | Date ranges not aligned |
| **DOC_CONTRADICTION** (agent) | `REVIEW` | Taxonomy asserts X, data/proposals imply not-X |
| **NAMING_VIOLATION** (agent) | `REVIEW` | Campaign names break the documented convention |
| **ENTITY_SCOPE** (agent) | `REVIEW` | Same concept, different ID spaces — flag, don't solve |

Also on first detect:

1. Creates contract `client: acme` if missing.
2. Writes source metadata (path, grain, date_field).
3. Adds each mapped proposal via `contract.add_mapping` (auto if confidence > 0.9).
4. Sets `open_conflicts` from detect output.
5. Saves `contracts/acme.yaml`.

### Severity defense (say this)

| Tier | Meaning |
|---|---|
| **AUTO** | Deterministic transform — apply, log, don’t block the human |
| **REVIEW** | Reconcilable with loss (grain rollup) — decide with a default |
| **BLOCK** | Irreducible definition — **refuse to serve a harmonised number** until a human picks |

> “Blocking is the interesting one. A wrong conversions total is worse than no
> conversions total — especially if an agent acts on it.”

> “The model is allowed to notice. It is not allowed to AUTO two attribution
> windows. Python raises it to BLOCK even if the agent is polite. That’s the
> policy floor — and it’s why this is an agent with rails, not a list of
> if-statements and not a black box.”

### Exit criteria

Queue shows schema kinds (GRAIN / UNIT / DEFINITION / CURRENCY) plus at least
one agent-origin conflict (DOC / NAMING / ENTITY) if the call succeeded.
YAML exists under the tab. Metrics row shows schema count vs agent turns.

---

## 5. Stage D — Adjudicate (write the contract)

**Tab:** `3 · Conflict queue` (same tab) + **`4 · Contract`**  
**Code:** `src/contract.py` — `resolve` → `bump` → `save`  
**LLM?** No.

### What you do (for each open conflict you want to land)

1. Read **detail** + expand **Evidence from proposals**.
2. Pick a **Decision** radio (recommended is pre-selected).
3. Type a **Rationale** (required — empty rationale is rejected).
4. Click **Accept decision**.
5. Watch version bump and YAML refresh underneath.

### Suggested adjudication path (demo narrative)

Work **BLOCK → REVIEW → AUTO** (UI already sorts that way).

| Conflict | Pick | Rationale to type (example) |
|---|---|---|
| `DEFINITION_DIVERGENCE` on `conversions` / attribution | `keep_split_by_source` | “Metriq integer last-touch vs Lumen fractional modelled — not the same event; do not sum.” |
| `GRAIN_MISMATCH` on `date` | `rollup_to_weekly` | “Query grain is weekly; upward rollup is lossless.” |
| `UNIT_MISMATCH` on `media_spend` | apply `divide_by_1e6` … | “Lumen cost_micros → currency units; deterministic.” |
| Fee / click-type `REVIEW` divergences | keep split or prefer one source | Name the trade-off in one sentence. |

### What the system does on Accept

1. `contract.resolve(...)` — appends a resolution with `decided_by`,
   `decided_at`, decision, rationale; removes matching open conflict(s).
2. `contract.bump()` — patches version (`0.1.0` → `0.1.1` → …).
3. `contract.save(...)` — writes `contracts/acme.yaml`.
4. Reruns UI; queue shrinks; YAML block shows the artifact.

### What to show on tab 4

Open **4 · Contract**:

- Full YAML (mappings, resolutions, open_conflicts).
- `review_burden` JSON: fields total, auto-accept rate, open conflict count,
  resolutions recorded.

### Landing line

> “Onboarding didn’t produce a pipeline. It produced this file. Next quarter,
> when someone asks why Meta and Google conversions are reported separately,
> this file is the answer — with a name and a timestamp on it.”

### Exit criteria

At least one **BLOCK** resolution is in the YAML with author + time. Panel has
seen the artifact, not just the UI.

---

## 6. Stage E — Query with caveats (the payoff)

**Tab:** `5 · Query`  
**Code:** `src/query.py` → `run_hardcoded_query`  
**LLM?** No — executes through the contract.

### Hardcoded question (shown in UI)

> What was total media spend and conversions by campaign, across both
> platforms, for **May 2026**?

### What you do

1. Open **5 · Query**.
2. Click **Run query**.
3. Read caveats **before** interpreting the table.
4. Optionally expand **Raw result object**.

### What the system does

1. Loads both CSVs from contract `sources`.
2. Applies **mappings** + **transforms** (e.g. `divide_by_1e6`).
3. Filters to **May 2026**.
4. Rolls **daily → weekly** (Monday week start) for Metriq.
5. Aggregates `media_spend` and `conversions` by `campaign_name`.
6. For any metric with an **unresolved BLOCK** open conflict (or a resolution
   containing `keep_split`):
   - Does **not** sum across sources.
   - Emits split columns: `conversions__metriq_ads`, `conversions__lumen_search`, …
   - Attaches a **caveat** object on the result (`severity`, `text`,
     `decided_by` / `decided_at` when resolved, `contract_version`).
7. Summable metrics (e.g. spend with only AUTO unit conflict) remain a single
   numeric field.

### What you should see

| Situation | Table | Caveats |
|---|---|---|
| Conversions still BLOCK / keep_split | Split columns per source | Warning banner + BLOCK text |
| No BLOCK on conversions | Single `conversions` total | “No BLOCK caveats…” (still discuss that entity IDs aren’t resolved) |

### Line to say

> “An agent would generate this SQL. I hardcoded the question because the agent
> layer isn’t what I’m testing. What I *am* testing is that the caveat is a
> property of the result — not a footnote someone might skip.”

### Exit criteria

Panel sees a number that **refuses to launder** an irreducible conflict.

---

## 7. Close (minutes ~62–75)

### Compounding argument

> “Client two should be faster than client one, or this is an agency service,
> not a platform. Resolutions become priors — field-name patterns and
> definitional defaults carry across tenants even though **no client data**
> ever does.”

### Prepared answers (constraint changes)

| They say | You say |
|---|---|
| Third platform, novel schema | Contract isn’t source-specific; mappings are a list. Schema scan is N-way; a new disclosure axis is a yaml line. Entity resolution across ID spaces is what breaks — scoped out. |
| Why not three if-statements? | Schema scan scales with the ontology; the agent finds what rules cannot see. Python is the policy floor. |
| Client says doc is right, data wrong | Neither auto-wins; override with author + rationale; visible in git diff. |
| 400 fields, not 12 | Confidence tiering; metric is **human review minutes per source**. |
| How do you know the model mapped right? | You don’t from one run — need a golden set; gate prompt changes on it. |
| Onboard client #2 | Priors propagate; client data never does. |
| Why Streamlit? | UI isn’t the product; the contract is. |
| Humans forever? | For irreducible conflicts, yes. Goal is zero humans on the 380 obvious fields. |
| Anything unknown | “I’d check — instinct is X; here’s how I’d test.” Never bluff. |

### If behind on time

**Cut Stage E.** Keep the conflict queue + YAML sharp. A ratified contract
without the query beats a half-working query.

---

## 8. Stage checklist (operator card)

Copy this to a sticky note:

```
[ ] Env + API key + Streamlit up
[ ] Reset: rm contracts/acme.yaml && regenerate data
[ ] A  Profile          — grain, micros hint, has_decimals
[ ] B  Run proposal     — group by canonical_key; spend↔cost_micros
[ ] C  Detect conflicts — schema count vs agent turns; BLOCK on attribution
[ ] D  Accept BLOCK     — keep_split; show decided_by / decided_at YAML
[ ] E  Run query        — May 2026; caveats on split conversions
[ ] Close               — compounding + invite breaks
```

---

## 9. File map (what each stage touches)

```
machine-onboarding/
├── app.py                      UI tabs 1–5
├── generate_sample_data.py     planted conflicts
├── canonical/metrics.yaml      target vocabulary
├── data/
│   ├── metriq_ads_export.csv
│   ├── lumen_search_export.csv
│   └── acme_taxonomy.md
├── contracts/acme.yaml         written in Stages C–D
└── src/
    ├── profile.py              Stage A
    ├── propose.py              Stage B
    ├── conflicts.py            Stage C
    ├── contract.py             Stage D
    └── query.py                Stage E
```

---

## 10. Reset between rehearsals

```bash
cd machine-onboarding
rm -f contracts/acme.yaml
python generate_sample_data.py
# Restart Streamlit (clears session: proposals / conflicts / query_result)
pkill -f "streamlit run app.py" || true
/opt/anaconda3/bin/streamlit run app.py
```

Code stays; only artifact + session state clear.
