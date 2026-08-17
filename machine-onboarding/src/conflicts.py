"""
SKELETON — YOU BUILD THIS LIVE. Iteration 3.

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
from dataclasses import dataclass


@dataclass
class Conflict:
    kind: str
    severity: str            # AUTO | REVIEW | BLOCK
    canonical_key: str
    sources: list[str]
    detail: str
    options: list[str]       # the choices offered to the human
    recommended: str | None


def detect(profiles: dict, proposals: list, taxonomy_md: str) -> list[Conflict]:
    """TODO — build live."""
    raise NotImplementedError("Build me in the session.")
