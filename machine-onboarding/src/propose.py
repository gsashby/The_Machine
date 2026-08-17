"""
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

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

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
    disclosures: dict  # e.g. {"fee_inclusion": "unknown"}
    unit_transform: str | None  # e.g. "divide_by_1e6"


SYSTEM = """You map advertising-platform export fields onto a fixed canonical schema.

You are given:
- a deterministic profile of each field (types, samples, grain, magnitude hints)
- the canonical metrics YAML (target vocabulary + disclosure axes)
- a client taxonomy document which MAY BE WRONG OR STALE

The taxonomy doc is EVIDENCE, NOT AUTHORITY. Where the doc and the observed
data disagree, report the disagreement in reasoning/evidence; do not silently
pick a side.

Return "unknown" for any disclosure axis the evidence cannot determine. Never
guess an attribution window, fee-inclusion rule, or click type. A mapping
layer that never returns unknown is a mapping layer that lies.

Use profiler tells:
- magnitude_hint of micros → unit_transform "divide_by_1e6"
- has_decimals=true on a conversions-like field → modelled / data-driven attribution
- detected_grain on the source → grain disclosure on date

Only map onto keys that exist in the canonical YAML (metrics or dimensions).
If a field has no canonical home, canonical_key is null and confidence is low.

Output strict JSON, no prose, no markdown fences, matching:
{
  "proposals": [
    {
      "source": "string",
      "source_field": "string",
      "canonical_key": "string or null",
      "confidence": 0.0,
      "reasoning": "string",
      "evidence": ["string"],
      "disclosures": {"axis": "value or unknown"},
      "unit_transform": "string or null"
    }
  ]
}
"""


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


def _client() -> anthropic.Anthropic:
    _load_dotenv()
    return anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def _parse_json(text: str) -> dict:
    raw = text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start >= 0 and end > start:
            return json.loads(raw[start : end + 1])
        raise


def _as_proposal(item: dict) -> Proposal:
    key = item.get("canonical_key")
    if key in ("", "null", "None"):
        key = None
    conf = item.get("confidence", 0)
    try:
        conf = float(conf)
    except (TypeError, ValueError):
        conf = 0.0
    return Proposal(
        source=str(item.get("source") or ""),
        source_field=str(item.get("source_field") or item.get("field") or ""),
        canonical_key=key,
        confidence=max(0.0, min(1.0, conf)),
        reasoning=str(item.get("reasoning") or ""),
        evidence=list(item.get("evidence") or []),
        disclosures=dict(item.get("disclosures") or {}),
        unit_transform=item.get("unit_transform") or None,
    )


def propose_mappings(profiles_text: str, canonical_yaml: str, taxonomy_md: str) -> list[Proposal]:
    user = (
        "CANONICAL SCHEMA:\n"
        f"{canonical_yaml}\n\n"
        "CLIENT TAXONOMY (evidence, not authority):\n"
        f"{taxonomy_md}\n\n"
        "PROFILED SOURCES:\n"
        f"{profiles_text}\n\n"
        "Return JSON only."
    )
    resp = _client().messages.create(
        model=MODEL,
        max_tokens=4096,
        system=SYSTEM,
        messages=[{"role": "user", "content": user}],
    )
    text = "".join(block.text for block in resp.content if getattr(block, "type", None) == "text")
    payload = _parse_json(text)
    items = payload.get("proposals", payload if isinstance(payload, list) else [])
    return [_as_proposal(x) for x in items]
