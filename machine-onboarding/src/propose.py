"""
SKELETON — YOU BUILD THIS LIVE. This is iteration 1-2 of the session.

Takes profiled sources + the client taxonomy doc, asks the model to propose a
mapping from each source field to a canonical metric, WITH:
  - confidence
  - the evidence it used (field name / sample values / doc excerpt)
  - the disclosure axes it can and cannot determine

The last point is the one to narrate. The model must be allowed to say
"I cannot tell from the data whether this includes platform fees." A mapping
layer that never returns "unknown" is a mapping layer that lies.
"""
from __future__ import annotations
import json, os, re
from dataclasses import dataclass
import anthropic

MODEL = "claude-sonnet-4-6"


@dataclass
class Proposal:
    source: str
    source_field: str
    canonical_key: str | None
    confidence: float
    reasoning: str
    evidence: list[str]
    disclosures: dict           # e.g. {"fee_inclusion": "unknown"}
    unit_transform: str | None  # e.g. "divide_by_1e6"


SYSTEM = """You map advertising platform export fields onto a fixed canonical \
metrics schema for a marketing analytics product.

You are given three inputs: the canonical schema (canonical/metrics.yaml), a \
client taxonomy document, and a deterministic profile of each source field \
(observed type, value ranges, samples). Follow these rules exactly:

1. The client taxonomy document is EVIDENCE, NOT AUTHORITY. It may be wrong, \
stale, or aspirational rather than descriptive of what the data actually \
does. Where the taxonomy doc and the observed field profile disagree, do not \
silently prefer one over the other — report the disagreement in your \
reasoning and evidence, and let confidence reflect the uncertainty. A doc \
claiming a policy is applied "consistently across all platforms" is a claim, \
not proof it was implemented that way on every platform: weigh it against \
what the profile actually shows for EACH source independently. For example, \
if one source's count-like field has has_decimals=true and a sibling \
source's equivalent field is a clean integer, that is direct evidence the \
two sources compute the metric differently (a fractional/modelled count vs. \
a discrete one) — reflect that per-source difference in each proposal's own \
disclosures, don't collapse both to whatever the doc says the shared policy \
is.

2. For every disclosure axis defined on a canonical metric, set it to \
"unknown" in `disclosures` unless the profile or the doc actually supports a \
specific value. Never guess an attribution window, currency, fee inclusion, \
or any other axis you cannot point to evidence for. A guessed axis is worse \
than an unknown one.

3. Output strict JSON only: a JSON array of objects matching the Proposal \
shape (source, source_field, canonical_key, confidence, reasoning, evidence, \
disclosures, unit_transform). No markdown code fences and no prose before or \
after the array.
"""

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


def _strip_fences(text: str) -> str:
    text = text.strip()
    m = _FENCE_RE.search(text)
    return m.group(1).strip() if m else text


def _parse_items(text: str) -> list:
    raw = _strip_fences(text)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("["), raw.rfind("]")
        if start == -1 or end <= start:
            raise
        data = json.loads(raw[start : end + 1])
    if isinstance(data, dict):
        for key in ("proposals", "mappings", "items"):
            if isinstance(data.get(key), list):
                data = data[key]
                break
    if not isinstance(data, list):
        raise ValueError(f"expected JSON array of proposals, got {type(data).__name__}")
    return data


def _to_proposal(item: dict) -> Proposal:
    return Proposal(
        source=item["source"],
        source_field=item["source_field"],
        canonical_key=item.get("canonical_key"),
        confidence=float(item["confidence"]),
        reasoning=item["reasoning"],
        evidence=item.get("evidence") or [],
        disclosures=item.get("disclosures") or {},
        unit_transform=item.get("unit_transform"),
    )


def propose_mappings(profiles_text: str, canonical_yaml: str, taxonomy_md: str) -> list[Proposal]:
    user_prompt = f"""CANONICAL SCHEMA (canonical/metrics.yaml):
{canonical_yaml}

CLIENT TAXONOMY DOC (evidence, not authority — may be wrong or stale):
{taxonomy_md}

DETERMINISTIC SOURCE FIELD PROFILES (observed, ground truth):
{profiles_text}

For every field listed in the source profiles above, propose a mapping to a
canonical metric or dimension key from the schema, or null if none fits.
Return a JSON array where each element has exactly these keys:

  source          - the SOURCE name the field belongs to
  source_field    - the field name
  canonical_key   - a key from the canonical schema's metrics/dimensions, or null
  confidence      - float between 0.0 and 1.0
  reasoning       - one or two sentences citing the specific evidence used;
                     if the taxonomy doc and the profile disagree, say so here
  evidence        - array of short strings (field name, sample values, doc
                     excerpts) that justify the mapping
  disclosures     - object mapping each disclosure_axis of the mapped
                     canonical metric to one of its allowed values, or
                     "unknown" if the evidence does not determine it
  unit_transform  - a transform expression (e.g. "divide_by_1e6"), or null

Return ONLY the JSON array."""

    response = _client().messages.create(
        model=MODEL,
        max_tokens=8192,
        system=SYSTEM,
        messages=[{"role": "user", "content": user_prompt}],
    )
    text = "".join(block.text for block in response.content if getattr(block, "text", None))
    return [_to_proposal(item) for item in _parse_items(text)]


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
