# Runbook — 75 minutes

## The one rule

You have **five** planned iterations and **three** open slots. Say this out loud
at minute 16: *"I've deliberately left about a third of the hour empty so you can
break this. Interrupt whenever."* That single sentence converts their constraint
changes from a threat into the thing you prepared for.

If you are behind at minute 45, **cut iteration 5 and keep the conflict queue
polished.** A working conflict queue with no query beats a half-working query.

---

## Minutes 0–15 · Presentation

| Time | Beat |
|---|---|
| 0–2 | **Reframe.** The weeks aren't in the pipes; extraction is a commodity. They're in the judgment calls — does Meta's conversion count post-view, does spend include platform fees — which get answered once, hardcoded into pipeline logic, and lost. |
| 2–5 | **Three layers.** Land (buy) → Resolve (*the product*) → Serve. The artifact that connects them is a versioned semantic contract. |
| 5–8 | **The money slide: irreducible conflict.** Meta and Google don't disagree from sloppy naming; they measure different events. A 7-day-click conversion and a data-driven conversion aren't the same thing. Summing them produces a confidently wrong number an agent then acts on. *Harmonization without provenance is data laundering.* |
| 8–11 | **Risks ranked:** silent wrong answers → doc-as-truth → doesn't compound across clients → human becomes the new bottleneck. |
| 11–13 | **The slice + metrics:** time-to-first-*trusted*-query; auto-map rate trended across clients; human review minutes per source; contradiction escape rate. |
| 13–15 | **What I built vs. what I'm about to build, and what I stubbed.** Name every stub. |

Slides: 8 max. You are talking, not reading.

---

## Minutes 15–75 · Live build

**Minute 15–17 — orient.** `streamlit run app.py` is already running. Show the
Profile tab working. Say: *"The deterministic profiler is pre-built on purpose —
it's cheap and boring and I don't want to spend an LLM call or a demo minute on
it. Notice it flags `campaign_id` as possible micros. That's a false positive,
and it's why the model adjudicates rather than the rules deciding alone."*

**Iteration 1 (~17–25) — the proposal prompt.** Build `propose.py`'s system
prompt live in Claude Code. The line to say while typing: *"The most important
instruction here is that the taxonomy doc is evidence, not authority, and the
model is allowed to return `unknown`. A mapping layer that never says 'I can't
tell' is a mapping layer that lies."*

**Iteration 2 (~25–33) — run it, render it.** Wire the Proposed-mapping tab.
Expect the model to catch `spend`↔`cost_micros` and the micros transform. When
it does, point at the profiler's `has_decimals=True` on Lumen's conversions:
*"That's the tell. Fractional conversions mean modelled attribution. The rules
found that, not the model."*

**Iteration 3 (~33–43) — the conflict agent (deep slice).** `conflicts.py`. This
is not a list of three checks. Point at the two layers: the schema scan walks
collision groups against `disclosure_axes` in `metrics.yaml` — a new axis is a
new conflict class, no new Python — then the agent uses tools to find what the
schema cannot see (doc vs data, naming, mixed currency). Defend the policy
floor: *"the model is allowed to notice. It is not allowed to AUTO two
attribution windows. Python raises it to BLOCK even if the agent is polite."*

**Iteration 4 (~43–52) — adjudicate and write the contract.** Accept a decision
in the UI, watch the YAML get written with `decided_by` and `decided_at`. This is
the moment the demo lands. *"Onboarding didn't produce a pipeline. It produced
this file. Next quarter, when someone asks why our Meta and Google conversions
are reported separately, this file is the answer — with a name on it."*

**Iteration 5 (~52–62) — query with caveats.** Only if you're on time. Show the
number carrying its own disclosure.

**~62–75 — their curveballs and close.** Close on the compounding argument:
*"Client two should be faster than client one, or this is an agency service, not
a platform. The mechanism is that resolutions become priors — the field-name
patterns and definitional defaults carry across tenants even though no client
data ever does."*

---

## Prepared answers for the constraint changes

| They say | You say |
|---|---|
| "A third platform arrives, novel schema." | Nothing about the contract is source-specific — mappings are a list, canonical is fixed. The schema scan is N-way: a third source is another member of the collision group, and a new disclosure axis is a yaml line, not a new check. What still breaks is entity resolution across three ID spaces, which I scoped out. |
| "Why not just three if-statements?" | Because checks 4–n are where the product lives, and they don't fit in a list. The schema scan scales with the ontology; the agent finds doc-vs-data and novel kinds. Python is the policy floor so the model cannot quietly AUTO an irreducible definition. |
| "Client insists the doc is right, the data is wrong." | Neither auto-wins. It's an override, recorded with an author and a rationale, and it's now visible in the diff when someone disagrees in Q3. |
| "400 fields, not 12." | Confidence tiering. Auto-accept above threshold, and the metric I'd run the roadmap on is human review minutes per source, not fields mapped. |
| "How do you know the model mapped it right?" | I don't, from one run. You need a golden set — hand-labelled mappings across ~10 real client sources — and you gate prompt changes on it. That's the first thing I'd build after this slice. |
| "Now onboard client #2." | Resolutions become priors. Patterns propagate, client data never does — that's the multi-tenancy line and it's a hard boundary. |
| "Why Streamlit and not a real frontend?" | Because the UI isn't the product here, the contract is. In production this is a review surface inside The Machine; for a one-hour slice, UI scaffolding is dead time. |
| "This seems like it needs a human forever." | For irreducible conflicts, yes — and that's correct. The goal isn't zero humans, it's zero humans on the 380 obvious fields so they have attention left for the 6 that matter. |
| *Anything you don't know* | "I'd have to check — my instinct is X, here's how I'd test it." Never bluff to this panel. |

---

## Pre-flight checklist

- [ ] `pip install -r requirements.txt`
- [ ] `ANTHROPIC_API_KEY` exported **and a real call tested**
- [ ] `streamlit run app.py` already running before the call starts
- [ ] Claude Code open, in this directory, authenticated
- [ ] `git init && git add -A && git commit` — so you can `git diff` the contract live
- [ ] Notifications off, one clean screen, terminal font size up
- [ ] `data/` regenerable: `python generate_sample_data.py`
