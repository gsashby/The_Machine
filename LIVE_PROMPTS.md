# Prepared prompts for the live session

Have these in a scratch file. Do NOT paste them silently — read the intent aloud
as you send them. The panel is grading how you drive the tool, so narrate the
*why* of each prompt, not the text of it.

---

## Iteration 1 — the proposal prompt

> In `src/propose.py`, implement `propose_mappings`. It calls Claude with the
> profiled sources, `canonical/metrics.yaml`, and the client taxonomy markdown,
> and returns a list of `Proposal`.
>
> The system prompt must state three things explicitly:
> (1) the taxonomy doc is EVIDENCE, NOT AUTHORITY — where doc and observed data
> disagree, report the disagreement rather than picking a side;
> (2) every disclosure axis the evidence cannot determine must be returned as
> "unknown" — never guess an attribution window;
> (3) output strict JSON matching the Proposal dataclass, no markdown fences.
>
> Parse defensively — strip fences if present. Don't add retries yet.

## Iteration 2 — render it

> Wire the "Proposed mapping" tab in `app.py`. Group by canonical_key so fields
> from different sources that map to the same metric appear together — that
> grouping is what makes conflicts visible. Show confidence, transform, and
> disclosures. Collapse anything above 0.9 confidence by default.

## Iteration 3 — conflict agent (the deep slice)

> A list of three checks does not survive a third platform or a new disclosure
> axis. Implement `detect` in `src/conflicts.py` as two layers:
>
> (1) SCHEMA SCAN — deterministic, driven by `canonical/metrics.yaml`. For every
> collision group, walk that metric's `disclosure_axes`. Adding an axis to the
> yaml is a new conflict class; you do not ship a new if-statement. Grain, unit
> transform, and date coverage come from the profiler, not the model.
>
> (2) AGENT — tool-using. It can inspect collision groups, inspect a source
> profile, search the taxonomy doc, and submit conflicts the schema cannot see
> (DOC_CONTRADICTION, mixed currency, naming violations, entity-scope).
>
> Python enforces severity floors. The agent may raise severity; it may not
> AUTO a BLOCK. Attribution model/window divergence is always BLOCK. Mixed
> currency is always BLOCK. Each Conflict still carries concrete options a
> human can pick between.

## Iteration 4 — adjudicate

> Wire the "Conflict queue" tab. Each conflict renders with its evidence and its
> options as radio buttons plus a free-text rationale box. Accepting calls
> `contract.resolve` then `contract.bump` then `contract.save`. Show the written
> YAML immediately underneath so the artifact is visible.

## Iteration 5 — query with caveats

> Implement `run_hardcoded_query`. Load both CSVs, apply the accepted mappings
> and transforms from the contract, roll the daily source up to weekly, and
> return spend and conversions by campaign for May 2026. Any canonical metric
> with an unresolved BLOCK conflict must be returned SPLIT BY SOURCE, not summed,
> with the caveat text attached to the result object.

---

## Emergency prompts

**Model output won't parse:**
> Add a repair step: on JSON parse failure, send the raw output back with the
> error and ask for corrected JSON only. One retry, then fail loudly.

**Running out of time:**
> Skip the query tab. Instead add a `review_burden` summary to the contract tab
> showing auto-map rate and open conflict count.

**Something is broken and you need a beat:**
Talk while it runs. *"While that's going — the thing I'd want to add next is a
golden set of hand-labelled mappings so prompt changes can be regression-tested.
Right now I have no way to know if I made this worse."*
