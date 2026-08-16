"""
REAL (mostly) — built in advance.

The semantic contract: the actual product artifact. Plain YAML on purpose, so a
human can read it, edit it, and diff it in git. When the panel asks "why not a
database table?" the answer is: because the value of this thing is that a human
can review it and a reviewer can see what changed between versions. Reviewability
is the feature.

Note `decided_by` and `decided_at`. Every irreducible conflict resolution carries
an author and a timestamp. That is what makes it a decision rather than a guess.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import yaml

CONTRACT_DIR = Path("contracts")


def new_contract(client: str) -> dict:
    return {
        "client": client,
        "version": "0.1.0",
        "created_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "sources": {},
        "mappings": [],
        "resolutions": [],
        "open_conflicts": [],
    }


def add_mapping(contract: dict, *, source: str, source_field: str,
                canonical_key: str, confidence: float, transform: str | None,
                disclosures: dict, evidence: list[str], auto: bool) -> None:
    contract["mappings"].append({
        "source": source,
        "source_field": source_field,
        "canonical_key": canonical_key,
        "confidence": round(float(confidence), 3),
        "transform": transform,
        "disclosures": disclosures,
        "evidence": evidence,
        "accepted": "auto" if auto else "pending",
    })


def resolve(contract: dict, *, conflict_kind: str, canonical_key: str,
            decision: str, rationale: str, decided_by: str) -> None:
    """Record a human adjudication. This is the durable output of onboarding."""
    contract["resolutions"].append({
        "conflict_kind": conflict_kind,
        "canonical_key": canonical_key,
        "decision": decision,
        "rationale": rationale,
        "decided_by": decided_by,
        "decided_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
    })
    contract["open_conflicts"] = [
        c for c in contract["open_conflicts"]
        if not (c.get("kind") == conflict_kind and c.get("canonical_key") == canonical_key)
    ]


def bump(contract: dict) -> None:
    major, minor, patch = (int(x) for x in contract["version"].split("."))
    contract["version"] = f"{major}.{minor}.{patch + 1}"


def save(contract: dict, path: str | Path | None = None) -> Path:
    CONTRACT_DIR.mkdir(exist_ok=True)
    p = Path(path) if path else CONTRACT_DIR / f"{contract['client']}.yaml"
    p.write_text(yaml.safe_dump(contract, sort_keys=False, width=100))
    return p


def load(path: str | Path) -> dict:
    return yaml.safe_load(Path(path).read_text())


def review_burden(contract: dict) -> dict:
    """The metric that matters: how much human attention did onboarding cost?"""
    m = contract["mappings"]
    auto = sum(1 for x in m if x["accepted"] == "auto")
    return {
        "fields_total": len(m),
        "auto_accepted": auto,
        "auto_rate": round(auto / len(m), 3) if m else 0.0,
        "open_conflicts": len(contract["open_conflicts"]),
        "resolutions_recorded": len(contract["resolutions"]),
    }
