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
import json, os
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


SYSTEM = """TODO — build live.

Sketch of what belongs here (do NOT paste this in as-is; write it with the
panel watching so they see you shaping it):
  - You map advertising platform export fields onto a fixed canonical schema.
  - You are given: a deterministic profile of each field, and a client taxonomy
    doc which MAY BE WRONG OR STALE.
  - The taxonomy doc is EVIDENCE, NOT AUTHORITY. Where the doc and the observed
    data disagree, report the disagreement; do not silently pick a side.
  - Return "unknown" for any disclosure axis the evidence cannot determine.
  - Output strict JSON, no prose, no markdown fences.
"""


def propose_mappings(profiles_text: str, canonical_yaml: str, taxonomy_md: str) -> list[Proposal]:
    """TODO — build live."""
    raise NotImplementedError("Build me in the session.")


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
