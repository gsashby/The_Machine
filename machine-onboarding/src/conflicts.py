"""
Conflict detection — the deep slice.

A hardcoded list of three checks does not survive a third platform or a new
disclosure axis. The scalable version is two layers:

  1. SCHEMA SCAN (deterministic). Collision groups × the disclosure axes on
     that canonical metric. Adding `viewability_basis` to metrics.yaml is a
     new conflict class; you do not ship a new if-statement. Grain, unit
     transform, and coverage come from the profiler, not the model.

  2. AGENT (tool-using). Discovers what the schema cannot see: a taxonomy doc
     that contradicts the data, a mixed-currency column, a naming convention
     the exports violate, a novel kind we did not enumerate.

Python is the policy floor. The agent may raise severity; it may not AUTO an
irreducible definition. Attribution model/window divergence is always BLOCK.

This split is the argument: the model is good at noticing. It is not the
thing you want quietly deciding that two attribution windows are comparable.
"""
from __future__ import annotations

import json
import os
from collections import defaultdict
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

import yaml

MODEL = "claude-sonnet-4-6"
MAX_TURNS = 10
CANONICAL_PATH = Path("canonical/metrics.yaml")

RANK = {"AUTO": 0, "REVIEW": 1, "BLOCK": 2}
IRREDUCIBLE_AXES = {"attribution_model", "attribution_window"}

# Floor by kind; DEFINITION_DIVERGENCE is further raised by axis in apply_policy.
SEVERITY_FLOOR = {
    "UNIT_MISMATCH": "AUTO",
    "GRAIN_MISMATCH": "REVIEW",
    "DEFINITION_DIVERGENCE": "REVIEW",
    "DOC_CONTRADICTION": "REVIEW",
    "CURRENCY_MIXED": "BLOCK",
    "COVERAGE_GAP": "REVIEW",
    "NAMING_VIOLATION": "REVIEW",
    "ENTITY_SCOPE": "REVIEW",
}

LAST_RUN: dict[str, Any] = {}


@dataclass
class Conflict:
    kind: str
    severity: str  # AUTO | REVIEW | BLOCK
    canonical_key: str
    sources: list[str]
    detail: str
    options: list[str]
    recommended: str | None
    evidence: list[str] = field(default_factory=list)
    axis: str | None = None
    origin: str = "schema"  # schema | agent


def _load_dotenv() -> None:
    env = Path(".env")
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip().strip("'").strip('"'))


def _client():
    import anthropic

    _load_dotenv()
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    return anthropic.Anthropic(api_key=key)


def load_ontology(path: str | Path = CANONICAL_PATH) -> dict:
    data = yaml.safe_load(Path(path).read_text()) or {}
    by_key: dict[str, dict] = {}
    for bucket in ("metrics", "dimensions"):
        for item in data.get(bucket, []) or []:
            by_key[item["key"]] = item
    return {
        "raw": data,
        "by_key": by_key,
        "axes": data.get("disclosure_axes", {}) or {},
    }


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _source_name(profile: Any) -> str:
    return _get(profile, "source_name") or _get(profile, "name") or "unknown"


def _normalize_profiles(profiles: dict) -> dict[str, Any]:
    out = {}
    for key, prof in (profiles or {}).items():
        out[_get(prof, "source_name") or key] = prof
    return out


def _mapped(proposals: list) -> list:
    return [p for p in proposals if _get(p, "canonical_key")]


def collision_groups(proposals: list) -> dict[str, list]:
    groups: dict[str, list] = defaultdict(list)
    for p in _mapped(proposals):
        groups[_get(p, "canonical_key")].append(p)
    return {
        key: items
        for key, items in groups.items()
        if len({_get(p, "source") for p in items}) >= 2
    }


def _field_profile(profile: Any, field_name: str) -> Any | None:
    for f in _get(profile, "fields") or []:
        if _get(f, "name") == field_name:
            return f
    return None


def _known(value: Any) -> bool:
    return value not in (None, "", "unknown")


def apply_policy(conflict: Conflict) -> Conflict:
    """The auditable rail. Model output may raise severity, never lower the floor."""
    floor = SEVERITY_FLOOR.get(conflict.kind, "REVIEW")
    if conflict.kind == "DEFINITION_DIVERGENCE" and conflict.axis in IRREDUCIBLE_AXES:
        floor = "BLOCK"
    if conflict.severity not in RANK:
        conflict.severity = floor
    elif RANK[conflict.severity] < RANK[floor]:
        conflict.severity = floor
    if conflict.recommended and conflict.recommended not in conflict.options:
        conflict.options = list(conflict.options) + [conflict.recommended]
    if not conflict.options:
        conflict.options = ["keep_split_by_source"]
        conflict.recommended = conflict.recommended or "keep_split_by_source"
    return conflict


def _conflict_id(c: Conflict) -> tuple:
    return (c.kind, c.canonical_key, c.axis or "", tuple(sorted(c.sources)))


def merge_conflicts(*batches: list[Conflict]) -> list[Conflict]:
    """Union by identity. If the same conflict arrives twice, keep the stricter severity."""
    by_id: dict[tuple, Conflict] = {}
    for batch in batches:
        for raw in batch:
            c = apply_policy(raw)
            ident = _conflict_id(c)
            existing = by_id.get(ident)
            if existing is None or RANK[c.severity] > RANK[existing.severity]:
                by_id[ident] = c
    ordered = list(by_id.values())
    ordered.sort(key=lambda c: (RANK.get(c.severity, 9), c.kind, c.canonical_key, c.axis or ""))
    return ordered


def _grain_options(grains: dict[str, str]) -> tuple[list[str], str]:
    values = {g for g in grains.values() if g}
    if "weekly" in values and "daily" in values:
        return (
            ["rollup_to_weekly", "keep_separate_by_source", "downsample_to_daily_lossy"],
            "rollup_to_weekly",
        )
    return ["keep_separate_by_source", "align_to_coarsest"], "keep_separate_by_source"


def scan_schema(profiles: dict, proposals: list, ontology: dict | None = None) -> list[Conflict]:
    """Deterministic, ontology-driven. Scales with metrics.yaml, not with Python checks."""
    ontology = ontology or load_ontology()
    profiles = _normalize_profiles(profiles)
    conflicts: list[Conflict] = []

    grains = {
        name: _get(p, "detected_grain")
        for name, p in profiles.items()
        if _get(p, "detected_grain")
    }
    if len(set(grains.values())) > 1:
        options, rec = _grain_options(grains)
        detail = ", ".join(f"{src}={grain}" for src, grain in sorted(grains.items()))
        conflicts.append(
            Conflict(
                kind="GRAIN_MISMATCH",
                severity="REVIEW",
                canonical_key="date",
                sources=sorted(grains),
                detail=f"Reporting grain disagrees ({detail}). Upward rollup is lossless; downward is not.",
                options=options,
                recommended=rec,
                evidence=[f"{src}.detected_grain={grain}" for src, grain in sorted(grains.items())],
                axis="grain",
                origin="schema",
            )
        )

    ranges = []
    for name, p in profiles.items():
        dmin, dmax = _get(p, "date_min"), _get(p, "date_max")
        if dmin and dmax:
            ranges.append((name, dmin, dmax))
    if len(ranges) >= 2:
        mins = {r[1] for r in ranges}
        maxes = {r[2] for r in ranges}
        if len(mins) > 1 or len(maxes) > 1:
            conflicts.append(
                Conflict(
                    kind="COVERAGE_GAP",
                    severity="REVIEW",
                    canonical_key="date",
                    sources=[r[0] for r in ranges],
                    detail="Date coverage is not aligned: "
                    + "; ".join(f"{n} {a}→{b}" for n, a, b in ranges),
                    options=["intersect_coverage", "keep_separate_by_source", "query_with_coverage_caveat"],
                    recommended="query_with_coverage_caveat",
                    evidence=[f"{n}: {a}..{b}" for n, a, b in ranges],
                    axis="coverage",
                    origin="schema",
                )
            )

    for name, p in profiles.items():
        for f in _get(p, "fields") or []:
            fname = str(_get(f, "name") or "")
            if fname.lower() == "currency" and int(_get(f, "distinct_count") or 0) > 1:
                samples = _get(f, "samples") or []
                conflicts.append(
                    Conflict(
                        kind="CURRENCY_MIXED",
                        severity="BLOCK",
                        canonical_key="media_spend",
                        sources=[name],
                        detail=(
                            f"{name}.{fname} has { _get(f, 'distinct_count') } distinct values "
                            f"{samples}. Summing mixed currencies is data laundering."
                        ),
                        options=["split_by_currency", "fx_to_usd_with_caveat", "drop_non_usd"],
                        recommended="split_by_currency",
                        evidence=[f"{name}.{fname} samples={samples}"],
                        axis="currency",
                        origin="schema",
                    )
                )

    by_key = ontology["by_key"]
    for key, group in collision_groups(proposals).items():
        sources = sorted({_get(p, "source") for p in group})

        transforms = []
        for p in group:
            transforms.append(
                (_get(p, "source"), _get(p, "source_field"), _get(p, "unit_transform"))
            )
        transform_values = {t[2] for t in transforms}
        if len(transform_values) > 1:
            options = []
            for src, field_name, transform in transforms:
                if transform:
                    options.append(f"apply {transform} to {src}.{field_name}")
            options.append("apply_no_transforms")
            recommended = next((o for o in options if o.startswith("apply ")), "apply_no_transforms")
            conflicts.append(
                Conflict(
                    kind="UNIT_MISMATCH",
                    severity="AUTO",
                    canonical_key=key,
                    sources=sources,
                    detail="Same canonical metric, different unit transforms: "
                    + "; ".join(
                        f"{src}.{fld} transform={tf or 'identity'}"
                        for src, fld, tf in transforms
                    ),
                    options=options,
                    recommended=recommended,
                    evidence=[
                        f"{src}.{fld}: unit_transform={tf or 'identity'}"
                        for src, fld, tf in transforms
                    ],
                    axis="unit",
                    origin="schema",
                )
            )

        spec = by_key.get(key) or {}
        for axis in spec.get("disclosure_axes") or []:
            observed: dict[str, Any] = {}
            for p in group:
                disclosures = _get(p, "disclosures") or {}
                val = disclosures.get(axis) if isinstance(disclosures, dict) else None
                src = _get(p, "source")
                if _known(val):
                    observed[src] = val
            if len(set(observed.values())) > 1:
                options = [f"use_{src}_({val})" for src, val in sorted(observed.items())]
                options.append("keep_split_by_source")
                severity = "BLOCK" if axis in IRREDUCIBLE_AXES else "REVIEW"
                recommended = "keep_split_by_source" if severity == "BLOCK" else options[0]
                conflicts.append(
                    Conflict(
                        kind="DEFINITION_DIVERGENCE",
                        severity=severity,
                        canonical_key=key,
                        sources=sorted(observed),
                        detail=(
                            f"{key}.{axis} disagrees: "
                            + ", ".join(f"{s}={v}" for s, v in sorted(observed.items()))
                            + (
                                ". These are not the same event; do not sum."
                                if severity == "BLOCK"
                                else "."
                            )
                        ),
                        options=options,
                        recommended=recommended,
                        evidence=[f"{s} {axis}={v}" for s, v in sorted(observed.items())],
                        axis=axis,
                        origin="schema",
                    )
                )

    return [apply_policy(c) for c in conflicts]


# ---------------------------------------------------------------------------
# Agent tools
# ---------------------------------------------------------------------------

def _proposal_brief(p: Any) -> dict:
    return {
        "source": _get(p, "source"),
        "source_field": _get(p, "source_field"),
        "canonical_key": _get(p, "canonical_key"),
        "confidence": _get(p, "confidence"),
        "unit_transform": _get(p, "unit_transform"),
        "disclosures": _get(p, "disclosures") or {},
        "evidence": _get(p, "evidence") or [],
        "reasoning": _get(p, "reasoning"),
    }


def _taxonomy_sections(taxonomy_md: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    current_title = "preamble"
    current: list[str] = []
    for line in (taxonomy_md or "").splitlines():
        if line.startswith("#"):
            if current:
                sections.append((current_title, "\n".join(current).strip()))
            current_title = line.lstrip("#").strip()
            current = [line]
        else:
            current.append(line)
    if current:
        sections.append((current_title, "\n".join(current).strip()))
    return sections


class _AgentWorld:
    def __init__(self, profiles: dict, proposals: list, taxonomy_md: str, ontology: dict,
                 schema_conflicts: list[Conflict]):
        self.profiles = _normalize_profiles(profiles)
        self.proposals = list(proposals)
        self.taxonomy_md = taxonomy_md or ""
        self.ontology = ontology
        self.schema_conflicts = schema_conflicts
        self.submitted: list[Conflict] = []
        self.finished = False

    def list_collision_groups(self) -> dict:
        groups = collision_groups(self.proposals)
        return {
            key: [
                {
                    "source": _get(p, "source"),
                    "source_field": _get(p, "source_field"),
                    "confidence": _get(p, "confidence"),
                    "unit_transform": _get(p, "unit_transform"),
                    "disclosures": _get(p, "disclosures") or {},
                }
                for p in items
            ]
            for key, items in groups.items()
        }

    def inspect_group(self, canonical_key: str) -> dict:
        spec = self.ontology["by_key"].get(canonical_key) or {}
        members = [p for p in self.proposals if _get(p, "canonical_key") == canonical_key]
        packed = []
        for p in members:
            src = _get(p, "source")
            field_name = _get(p, "source_field")
            prof = self.profiles.get(src)
            fp = _field_profile(prof, field_name) if prof is not None else None
            packed.append({
                **_proposal_brief(p),
                "field_profile": {
                    "inferred_type": _get(fp, "inferred_type") if fp else None,
                    "has_decimals": _get(fp, "has_decimals") if fp else None,
                    "magnitude_hint": _get(fp, "magnitude_hint") if fp else None,
                    "numeric_min": _get(fp, "numeric_min") if fp else None,
                    "numeric_max": _get(fp, "numeric_max") if fp else None,
                    "samples": _get(fp, "samples") if fp else None,
                } if fp is not None else None,
                "source_grain": _get(prof, "detected_grain") if prof is not None else None,
            })
        return {
            "canonical": {
                "key": canonical_key,
                "definition": spec.get("definition"),
                "dtype": spec.get("dtype"),
                "unit": spec.get("unit"),
                "disclosure_axes": spec.get("disclosure_axes") or [],
            },
            "proposals": packed,
        }

    def inspect_source(self, source_name: str) -> dict:
        prof = self.profiles.get(source_name)
        if prof is None:
            return {"error": f"unknown source {source_name}", "known": sorted(self.profiles)}
        fields_out = []
        for f in _get(prof, "fields") or []:
            fields_out.append({
                "name": _get(f, "name"),
                "inferred_type": _get(f, "inferred_type"),
                "distinct_count": _get(f, "distinct_count"),
                "has_decimals": _get(f, "has_decimals"),
                "magnitude_hint": _get(f, "magnitude_hint"),
                "samples": _get(f, "samples"),
            })
        return {
            "source_name": source_name,
            "row_count": _get(prof, "row_count"),
            "detected_grain": _get(prof, "detected_grain"),
            "date_field": _get(prof, "date_field"),
            "date_min": _get(prof, "date_min"),
            "date_max": _get(prof, "date_max"),
            "fields": fields_out,
        }

    def source_coverage(self) -> dict:
        return {
            name: {
                "grain": _get(p, "detected_grain"),
                "date_field": _get(p, "date_field"),
                "date_min": _get(p, "date_min"),
                "date_max": _get(p, "date_max"),
                "row_count": _get(p, "row_count"),
            }
            for name, p in self.profiles.items()
        }

    def search_taxonomy(self, query: str) -> dict:
        q = (query or "").lower().strip()
        if not q:
            return {"matches": [], "note": "empty query"}
        tokens = [t for t in q.replace("/", " ").split() if t]
        hits = []
        for title, body in _taxonomy_sections(self.taxonomy_md):
            blob = f"{title}\n{body}".lower()
            if any(tok in blob for tok in tokens):
                hits.append({"title": title, "excerpt": body[:1200]})
        return {"query": query, "matches": hits[:6]}

    def get_ontology(self) -> dict:
        return {
            "metrics": [
                {
                    "key": k,
                    "definition": v.get("definition"),
                    "disclosure_axes": v.get("disclosure_axes") or [],
                    "dtype": v.get("dtype"),
                    "unit": v.get("unit"),
                }
                for k, v in self.ontology["by_key"].items()
            ],
            "disclosure_axes": self.ontology["axes"],
            "irreducible_axes": sorted(IRREDUCIBLE_AXES),
            "severity_floors": SEVERITY_FLOOR,
        }

    def submit_conflict(self, payload: dict) -> dict:
        try:
            conflict = Conflict(
                kind=str(payload["kind"]).upper(),
                severity=str(payload.get("severity") or "REVIEW").upper(),
                canonical_key=str(payload["canonical_key"]),
                sources=list(payload.get("sources") or []),
                detail=str(payload.get("detail") or ""),
                options=list(payload.get("options") or []),
                recommended=payload.get("recommended"),
                evidence=list(payload.get("evidence") or []),
                axis=payload.get("axis"),
                origin="agent",
            )
        except (KeyError, TypeError, ValueError) as exc:
            return {"ok": False, "error": f"invalid conflict payload: {exc}"}
        if not conflict.sources:
            return {"ok": False, "error": "sources must be a non-empty list"}
        if not conflict.detail:
            return {"ok": False, "error": "detail is required"}
        before = conflict.severity
        conflict = apply_policy(conflict)
        ident = _conflict_id(conflict)
        if ident in {_conflict_id(c) for c in self.schema_conflicts}:
            return {
                "ok": True,
                "deduped": True,
                "note": "schema scan already recorded this conflict; not adding a duplicate",
            }
        self.submitted = [c for c in self.submitted if _conflict_id(c) != ident] + [conflict]
        return {
            "ok": True,
            "recorded": asdict(conflict),
            "policy_raised": before != conflict.severity,
        }

    def finish(self, note: str = "") -> dict:
        self.finished = True
        return {
            "ok": True,
            "submitted": len(self.submitted),
            "note": note,
        }


TOOLS = [
    {
        "name": "list_collision_groups",
        "description": "Canonical keys claimed by two or more sources, with per-source field, transform, and disclosures.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "inspect_group",
        "description": "Full evidence for one canonical key: canonical definition, proposals, field profiles, grain.",
        "input_schema": {
            "type": "object",
            "properties": {"canonical_key": {"type": "string"}},
            "required": ["canonical_key"],
            "additionalProperties": False,
        },
    },
    {
        "name": "inspect_source",
        "description": "Deterministic profiler output for one source: grain, date range, every field with samples and tells.",
        "input_schema": {
            "type": "object",
            "properties": {"source_name": {"type": "string"}},
            "required": ["source_name"],
            "additionalProperties": False,
        },
    },
    {
        "name": "source_coverage",
        "description": "Grain and date coverage for every source.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "search_taxonomy",
        "description": "Keyword search over the client taxonomy markdown. The doc is EVIDENCE, not authority.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_ontology",
        "description": "Canonical metrics, disclosure axes, irreducible axes, and severity floors.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "submit_conflict",
        "description": (
            "Record one conflict. Schema-scan duplicates are ignored. Python will raise severity "
            "to the policy floor if you set it too low. Prefer new kinds the schema cannot see."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "kind": {
                    "type": "string",
                    "description": "e.g. DOC_CONTRADICTION, NAMING_VIOLATION, ENTITY_SCOPE, or a new kind if warranted",
                },
                "severity": {"type": "string", "enum": ["AUTO", "REVIEW", "BLOCK"]},
                "canonical_key": {"type": "string"},
                "sources": {"type": "array", "items": {"type": "string"}},
                "detail": {"type": "string"},
                "options": {"type": "array", "items": {"type": "string"}},
                "recommended": {"type": "string"},
                "evidence": {"type": "array", "items": {"type": "string"}},
                "axis": {"type": "string"},
            },
            "required": ["kind", "severity", "canonical_key", "sources", "detail", "options"],
            "additionalProperties": False,
        },
    },
    {
        "name": "finish",
        "description": "Call when you have submitted every conflict the evidence supports.",
        "input_schema": {
            "type": "object",
            "properties": {"note": {"type": "string"}},
            "additionalProperties": False,
        },
    },
]

SYSTEM = """You are the conflict-detection agent for a marketing-data onboarding product.

Your job is to find definitional disagreements between sources that would make a
harmonised number a lie. You do NOT resolve conflicts. You surface them with
concrete options a human can pick between.

Two layers already exist:
- A deterministic SCHEMA SCAN has already run. It walked collision groups against
  the disclosure axes in the canonical ontology. You will be told what it found.
  Do not resubmit those. Add what the schema cannot see.
- PYTHON enforces severity floors after you submit. You cannot AUTO an irreducible
  definition. If you try, the floor wins. Irreducible axes: attribution_model,
  attribution_window → BLOCK. Mixed currency → BLOCK.

Look specifically for (open set — emit any kind the evidence supports):
- DOC_CONTRADICTION: taxonomy asserts X, observed data or proposals imply not-X.
  The taxonomy is EVIDENCE, NOT AUTHORITY. Report the disagreement; do not pick a side.
- NAMING_VIOLATION: campaign names that break the documented convention.
- ENTITY_SCOPE: same conceptual campaign, different ID spaces / names across platforms.
  Flag it; do not pretend to resolve entity matching.
- Invisible definitional issues (fee inclusion, click type) that only docs/priors show.
- Anything else that would make summing across sources dishonest.

Rules:
- Cite evidence. Do not invent disclosure values, grains, or transforms.
- Every conflict needs concrete options a human can select (not "look into it").
- For irreducible definitions, recommended should be keep_split_by_source.
- unknown on one side is not a divergence. Doc-vs-data still is.
- Prefer a few precise conflicts over a dump of maybes.
- Call finish when done.
"""


def _dispatch(world: _AgentWorld, name: str, payload: dict) -> Any:
    if name == "list_collision_groups":
        return world.list_collision_groups()
    if name == "inspect_group":
        return world.inspect_group(payload.get("canonical_key", ""))
    if name == "inspect_source":
        return world.inspect_source(payload.get("source_name", ""))
    if name == "source_coverage":
        return world.source_coverage()
    if name == "search_taxonomy":
        return world.search_taxonomy(payload.get("query", ""))
    if name == "get_ontology":
        return world.get_ontology()
    if name == "submit_conflict":
        return world.submit_conflict(payload)
    if name == "finish":
        return world.finish(payload.get("note", ""))
    return {"error": f"unknown tool {name}"}


def run_agent(profiles: dict, proposals: list, taxonomy_md: str,
              ontology: dict, schema_conflicts: list[Conflict]) -> list[Conflict]:
    world = _AgentWorld(profiles, proposals, taxonomy_md, ontology, schema_conflicts)
    schema_brief = [
        {
            "kind": c.kind,
            "canonical_key": c.canonical_key,
            "axis": c.axis,
            "severity": c.severity,
            "sources": c.sources,
        }
        for c in schema_conflicts
    ]
    user = (
        "SCHEMA SCAN already recorded these conflicts (do not resubmit):\n"
        + json.dumps(schema_brief, indent=2)
        + "\n\nSources: "
        + ", ".join(sorted(_normalize_profiles(profiles)))
        + "\nCollision groups: "
        + ", ".join(sorted(collision_groups(proposals)) or ["(none)"])
        + "\n\nInspect evidence with tools. Submit every additional conflict "
        "the evidence supports. Then finish."
    )

    client = _client()
    messages: list[dict] = [{"role": "user", "content": user}]
    turns = 0
    stop_reason = None

    while turns < MAX_TURNS and not world.finished:
        turns += 1
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=SYSTEM,
            tools=TOOLS,
            messages=messages,
        )
        stop_reason = response.stop_reason
        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason != "tool_use":
            break
        results = []
        for block in response.content:
            if getattr(block, "type", None) != "tool_use":
                continue
            output = _dispatch(world, block.name, block.input or {})
            results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps(output, default=str)[:12000],
            })
        if not results:
            break
        messages.append({"role": "user", "content": results})

    LAST_RUN.update({
        "agent": "ok",
        "turns": turns,
        "submitted": len(world.submitted),
        "stop_reason": stop_reason,
        "finished": world.finished,
    })
    return world.submitted


def detect(profiles: dict, proposals: list, taxonomy_md: str,
           canonical_path: str | Path = CANONICAL_PATH) -> list[Conflict]:
    """Schema scan always runs. Agent adds discoveries. Merge keeps the stricter severity."""
    LAST_RUN.clear()
    ontology = load_ontology(canonical_path)
    schema = scan_schema(profiles, proposals, ontology)
    LAST_RUN["schema"] = len(schema)
    try:
        discovered = run_agent(profiles, proposals, taxonomy_md, ontology, schema)
        LAST_RUN.setdefault("agent", "ok")
    except Exception as exc:  # noqa: BLE001 — demo must still show schema conflicts
        discovered = []
        LAST_RUN["agent"] = "error"
        LAST_RUN["agent_error"] = f"{type(exc).__name__}: {exc}"
    merged = merge_conflicts(schema, discovered)
    LAST_RUN["total"] = len(merged)
    return merged


def conflict_to_dict(c: Conflict) -> dict:
    return {f.name: getattr(c, f.name) for f in fields(c)}
