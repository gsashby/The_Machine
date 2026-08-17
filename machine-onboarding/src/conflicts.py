"""
Iteration 3. Two layers, on purpose:

  1. SCHEMA SCAN (deterministic). Collision groups x the disclosure axes on
     that canonical metric. Adding `viewability_basis` to metrics.yaml is a
     new conflict class; you do not ship a new if-statement. Grain, unit
     transform, and date coverage come from the profiler, not the model.

  2. AGENT (tool-using). Discovers what the schema cannot see: a taxonomy doc
     that contradicts the data, a mixed-currency column, a naming convention
     the exports violate, a novel kind we did not enumerate.

Python is the policy floor. The agent may raise severity; it may not AUTO an
irreducible definition. Attribution model/window divergence is always BLOCK.
Mixed currency is always BLOCK, whether the schema scan or the agent finds it.

This split is the argument: the model is good at noticing. It is not the
thing you want quietly deciding that two attribution windows are comparable.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

import profile as prof
from propose import MODEL, _client as _anthropic_client

CANONICAL_PATH = Path("canonical/metrics.yaml")

MAX_AGENT_TURNS = 12

SEVERITY_ORDER = {"AUTO": 0, "REVIEW": 1, "BLOCK": 2}

# Axes/kinds that Python refuses to let anyone soften. The agent may still
# raise a conflict above its floor (e.g. mark a naming issue BLOCK); it can
# never pull one of these back down.
_FORCED_BLOCK_HINTS = ("ATTRIBUTION_MODEL", "ATTRIBUTION_WINDOW", "CURRENCY")


@dataclass
class Conflict:
    kind: str
    severity: str            # AUTO | REVIEW | BLOCK
    canonical_key: str
    sources: list[str]
    detail: str
    options: list[str]       # the choices offered to the human
    recommended: str | None


def _enforce_floor(hint: str, severity: str) -> str:
    """hint is an axis name (from the schema scan) or a Conflict.kind (from
    the agent) -- either way, if it smells like attribution or currency, the
    floor is BLOCK no matter what asked for less."""
    floor = "BLOCK" if any(h in hint.upper() for h in _FORCED_BLOCK_HINTS) else "AUTO"
    return severity if SEVERITY_ORDER.get(severity, 1) >= SEVERITY_ORDER[floor] else floor


def _load_canonical() -> dict:
    return yaml.safe_load(CANONICAL_PATH.read_text())


def _field_profile(profiles: dict, source: str, field_name: str):
    sp = profiles.get(source)
    if not sp:
        return None
    return next((f for f in sp.fields if f.name == field_name), None)


def _collision_groups(proposals: list) -> dict[str, dict[str, object]]:
    """canonical_key -> {source -> best (highest-confidence) Proposal}, for
    canonical_keys that more than one source maps into. A single-source
    mapping cannot collide with anything, so it is not a conflict candidate."""
    groups: dict[str, dict[str, object]] = {}
    for p in proposals:
        if not p.canonical_key:
            continue
        by_source = groups.setdefault(p.canonical_key, {})
        cur = by_source.get(p.source)
        if cur is None or p.confidence > cur.confidence:
            by_source[p.source] = p
    return {key: by_source for key, by_source in groups.items() if len(by_source) > 1}


def _collision_groups_summary(proposals: list) -> dict:
    """JSON-able view of _collision_groups, for the agent's inspect tool."""
    return {
        key: {
            source: {
                "source_field": p.source_field,
                "confidence": p.confidence,
                "disclosures": p.disclosures,
                "unit_transform": p.unit_transform,
            }
            for source, p in by_source.items()
        }
        for key, by_source in _collision_groups(proposals).items()
    }


# ---------------------------------------------------------------- layer 1 --

def _schema_scan(profiles: dict, proposals: list) -> list[Conflict]:
    canonical = _load_canonical()
    axes_by_key = {
        entry["key"]: entry.get("disclosure_axes", [])
        for entry in canonical.get("metrics", []) + canonical.get("dimensions", [])
    }

    groups = _collision_groups(proposals)
    conflicts: list[Conflict] = []

    for key, by_source in groups.items():
        axes_flagged: set[str] = set()
        for axis in axes_by_key.get(key, []):
            values = {s: (p.disclosures or {}).get(axis, "unknown") for s, p in by_source.items()}
            known = {v for v in values.values() if v and v != "unknown"}
            rendered = ", ".join(f"{s}={v}" for s, v in sorted(values.items()))
            if len(known) >= 2:
                axes_flagged.add(axis)
                conflicts.append(Conflict(
                    kind=f"DIVERGENT_DISCLOSURE:{axis}",
                    severity=_enforce_floor(axis, "REVIEW"),
                    canonical_key=key,
                    sources=sorted(by_source),
                    detail=f"Sources disagree on `{axis}` for `{key}`: {rendered}.",
                    options=sorted(known) + ["report_separately"],
                    recommended=None,
                ))
            elif known and "unknown" in values.values():
                conflicts.append(Conflict(
                    kind=f"UNDETERMINED_DISCLOSURE:{axis}",
                    severity="REVIEW",
                    canonical_key=key,
                    sources=[s for s, v in values.items() if v == "unknown"],
                    detail=f"`{axis}` for `{key}` is undetermined for some sources: {rendered}.",
                    options=sorted(known) + ["unknown", "investigate_further"],
                    recommended=next(iter(known)),
                ))

        # Backstop that does not depend on the model's disclosures being
        # right: has_decimals is the profiler's own tell for a fractional /
        # modelled count vs. a discrete one (see profile.py). If it disagrees
        # across sources on a metric that carries an attribution axis, that
        # IS attribution divergence evidence, whether or not the model's
        # disclosures caught it -- and the axis floor still forces BLOCK.
        attribution_axes = {a for a in ("attribution_model", "attribution_window") if a in axes_by_key.get(key, [])}
        if attribution_axes and not (axes_flagged & attribution_axes):
            decimals = {}
            for s, p in by_source.items():
                fp = _field_profile(profiles, s, p.source_field)
                if fp and fp.inferred_type == "numeric" and fp.has_decimals is not None:
                    decimals[s] = fp.has_decimals
            if len(set(decimals.values())) > 1:
                rendered = ", ".join(f"{s}={'fractional' if v else 'integer'}" for s, v in sorted(decimals.items()))
                conflicts.append(Conflict(
                    kind="FRACTIONAL_VS_INTEGER_MISMATCH",
                    severity=_enforce_floor("attribution_model", "REVIEW"),
                    canonical_key=key,
                    sources=sorted(decimals),
                    detail=(f"`{key}` is a fractional count on some sources and a discrete integer on "
                            f"others ({rendered}). That split is the standard signature of a "
                            "data-driven/modelled attribution model on one side and a rule-based one "
                            "(e.g. last-click) on the other -- these are not the same measurement even "
                            "if the model's own disclosures called them the same."),
                    options=["report_separately", "investigate_further"],
                    recommended="report_separately",
                ))

    # Grain and date coverage are properties of a SOURCE PAIR, not of any one
    # canonical key -- one conflict per pair (naming every key it affects),
    # not one per collision group, or the same two facts repeat N times.
    keys_by_pair: dict[frozenset, list[str]] = {}
    for key, by_source in groups.items():
        keys_by_pair.setdefault(frozenset(by_source), []).append(key)

    for pair, keys in keys_by_pair.items():
        sources = sorted(pair)
        keys = sorted(keys)
        affected = f"affects {len(keys)} shared canonical key{'s' if len(keys) != 1 else ''}: {', '.join(keys)}."

        grains = {s: profiles[s].detected_grain for s in sources if s in profiles}
        if len({g for g in grains.values() if g}) > 1:
            conflicts.append(Conflict(
                kind="GRAIN_MISMATCH",
                severity="REVIEW",
                canonical_key=", ".join(keys),
                sources=sources,
                detail=(f"{sources[0]} and {sources[1]} report at different grains ("
                        + ", ".join(f"{s}={g}" for s, g in sorted(grains.items()))
                        + f") -- {affected}"),
                options=["roll_up_to_coarsest_common_grain", "report_separately_by_grain"],
                recommended="roll_up_to_coarsest_common_grain",
            ))

        windows = {s: (profiles[s].date_min, profiles[s].date_max) for s in sources if s in profiles}
        if len({w for w in windows.values() if w != (None, None)}) > 1:
            conflicts.append(Conflict(
                kind="DATE_COVERAGE_GAP",
                severity="REVIEW",
                canonical_key=", ".join(keys),
                sources=sources,
                detail=(f"{sources[0]} and {sources[1]} cover different date windows ("
                        + ", ".join(f"{s}={a}..{b}" for s, (a, b) in sorted(windows.items()))
                        + f") -- {affected}"),
                options=["intersect_to_common_window", "report_separately_by_coverage"],
                recommended="intersect_to_common_window",
            ))

    return conflicts


# ---------------------------------------------------------------- layer 2 --

AGENT_SYSTEM = """You are a conflict-discovery agent for a marketing-data \
reconciliation pipeline.

A deterministic schema scan has already checked every canonical-key \
collision group against its disclosure_axes, grain, and date coverage. Call \
inspect_collision_groups first so you do not resubmit anything it already \
covers.

Your job is to find conflicts the schema scan structurally cannot see, \
because they are not encoded in any single field's disclosure value. \
Examples of the kinds you're looking for:
  - DOC_CONTRADICTION: the taxonomy doc asserts a definition, naming rule, or \
    currency policy that the observed data or the mapped canonical \
    definition contradicts.
  - MIXED_CURRENCY: a single source reports more than one currency across \
    its own rows (a divergence WITHIN one source, not between two).
  - NAMING_CONVENTION_VIOLATION: profiled sample names don't follow the \
    doc's stated naming convention.
  - ENTITY_SCOPE: the same real-world entity (e.g. a campaign) appears under \
    different IDs/names across sources with no reliable join key. Flag it —
    do not attempt to resolve it.
  - Anything else you notice that the schema scan structurally cannot, under \
    a kind name you choose.

Use inspect_source_profile and search_taxonomy_doc to gather evidence, but \
budget your tool calls: you have a limited number of turns. As soon as you \
have enough evidence for ONE finding, call submit_conflict for it immediately \
— do not keep searching for more evidence you don't need, and do not save up \
findings to submit in a batch at the end. Submit early and often; you can \
keep investigating other candidates afterward. Every submit_conflict call \
must cite concrete evidence in `detail` — field names, sample values, or a \
doc quote, not a hunch. Call submit_conflict once per distinct conflict. When \
you have nothing further to report, stop calling tools and end your turn.

You may set `severity`, but you do not have the final word: Python enforces \
a policy floor and will raise your severity for attribution and currency \
conflicts regardless of what you choose. You may never mark something AUTO — \
your job is to surface conflicts for a human to decide, not to resolve them \
yourself.
"""

_TOOLS = [
    {
        "name": "inspect_collision_groups",
        "description": (
            "Returns the canonical_key collision groups already found by the "
            "deterministic schema scan: which sources map into each canonical "
            "key, their disclosures, confidence, and unit_transform. Call this "
            "first."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "inspect_source_profile",
        "description": "Returns the deterministic field profile (types, samples, distinct counts) for one source.",
        "input_schema": {
            "type": "object",
            "properties": {"source": {"type": "string"}},
            "required": ["source"],
        },
    },
    {
        "name": "search_taxonomy_doc",
        "description": "Full-text search over the client taxonomy markdown. Returns matching sections.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "submit_conflict",
        "description": "Report one conflict the schema scan could not see.",
        "input_schema": {
            "type": "object",
            "properties": {
                "kind": {"type": "string"},
                "canonical_key": {"type": "string", "description": "Canonical metric/dimension key this concerns, or the closest one."},
                "sources": {"type": "array", "items": {"type": "string"}},
                "detail": {"type": "string", "description": "Concrete evidence: field names, sample values, or a doc quote."},
                "options": {"type": "array", "items": {"type": "string"}, "description": "Choices to offer the human adjudicating this."},
                "recommended": {"type": ["string", "null"]},
                "severity": {"type": "string", "enum": ["AUTO", "REVIEW", "BLOCK"]},
            },
            "required": ["kind", "canonical_key", "sources", "detail", "options", "severity"],
        },
    },
]


def _search_taxonomy(taxonomy_md: str, query: str) -> str:
    query_l = query.strip().lower()
    if not query_l:
        return "empty query"
    sections = re.split(r"\n(?=#{1,6}\s)", taxonomy_md)
    hits = [s.strip() for s in sections if query_l in s.lower()]
    if not hits:
        hits = [p.strip() for p in taxonomy_md.split("\n\n") if query_l in p.lower()]
    return "\n\n---\n\n".join(hits[:5]) if hits else "No matches."


def _agent_scan(profiles: dict, proposals: list, taxonomy_md: str) -> list[Conflict]:
    groups_summary = _collision_groups_summary(proposals)
    collected: list[Conflict] = []

    def handle(name: str, tool_input: dict) -> str:
        if name == "inspect_collision_groups":
            return json.dumps(groups_summary, indent=2)
        if name == "inspect_source_profile":
            source = tool_input.get("source")
            if source not in profiles:
                return f"unknown source {source!r}. Known sources: {sorted(profiles)}"
            return prof.to_llm_context(profiles[source])
        if name == "search_taxonomy_doc":
            return _search_taxonomy(taxonomy_md, tool_input.get("query", ""))
        if name == "submit_conflict":
            kind = tool_input["kind"]
            collected.append(Conflict(
                kind=kind,
                severity=_enforce_floor(kind, tool_input.get("severity", "REVIEW")),
                canonical_key=tool_input.get("canonical_key") or "UNSCOPED",
                sources=tool_input.get("sources") or [],
                detail=tool_input["detail"],
                options=tool_input.get("options") or ["accept_as_flagged"],
                recommended=tool_input.get("recommended"),
            ))
            return f"recorded: {kind} (severity={collected[-1].severity})"
        return f"unknown tool {name!r}"

    client = _anthropic_client()
    messages = [{
        "role": "user",
        "content": (
            f"Sources available: {sorted(profiles)}.\n"
            f"Schema-scan collision groups (canonical_key -> source -> mapping): "
            f"{sorted(groups_summary)}.\n\n"
            "Investigate and submit_conflict for anything the schema scan cannot "
            "see. Start by calling inspect_collision_groups."
        ),
    }]

    for _ in range(MAX_AGENT_TURNS):
        response = client.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=AGENT_SYSTEM,
            tools=_TOOLS,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason != "tool_use":
            break
        tool_results = [
            {
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": handle(block.name, block.input),
            }
            for block in response.content
            if block.type == "tool_use"
        ]
        messages.append({"role": "user", "content": tool_results})

    return collected


# --------------------------------------------------------------- combined --

def detect(profiles: dict, proposals: list, taxonomy_md: str) -> list[Conflict]:
    schema_conflicts = _schema_scan(profiles, proposals)
    agent_conflicts = _agent_scan(profiles, proposals, taxonomy_md)
    combined = schema_conflicts + agent_conflicts
    combined.sort(key=lambda c: -SEVERITY_ORDER.get(c.severity, 1))
    return combined
