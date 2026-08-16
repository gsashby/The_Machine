"""
SKELETON — YOU BUILD THIS LIVE. Iteration 3.

Deterministic checks that run AFTER the model proposes. Two source fields that
both map to the same canonical metric are a conflict candidate; the checks below
decide whether the conflict is reconcilable or irreducible.

This split is the argument of the whole prototype: the model is good at
"cost_micros probably means spend". It is NOT the thing you want deciding
whether two attribution windows are comparable. That is a rule, and rules are
auditable.

Checks to implement (in rough priority order):
  1. GRAIN_MISMATCH        daily vs weekly -> reconcilable by rollup, lossy downward
  2. UNIT_MISMATCH         micros vs decimal -> reconcilable, deterministic transform
  3. DEFINITION_DIVERGENCE differing disclosure axis values -> IRREDUCIBLE, needs a human
  4. DOC_CONTRADICTION     taxonomy asserts X, observed data implies not-X
  5. CURRENCY_MIXED        multiple currencies in one field
  6. COVERAGE_GAP          date ranges don't align across sources

Severity model — recommend three tiers and be ready to defend them:
  AUTO      apply the transform, log it, don't interrupt anyone
  REVIEW    surface in the queue, propose a default
  BLOCK     refuse to serve a harmonised number until a human decides
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
