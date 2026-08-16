"""
REAL — built in advance, deliberately.

Deterministic profiling of a source file. This is the cheap, boring, reliable
half of the problem and there is no reason to spend an LLM call (or live demo
minutes) on it. Say this out loud during the session: the profiler is the
evidence-gathering step, and it is deterministic on purpose so that the model's
proposal is grounded in observed facts rather than in the field name alone.

The output of this module is what gets fed to the LLM in propose.py. Keeping it
compact matters — you are paying for these tokens on every field of every source
of every client.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, asdict, field
from typing import Any

import pandas as pd

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")


@dataclass
class FieldProfile:
    name: str
    inferred_type: str
    null_pct: float
    distinct_count: int
    samples: list[Any] = field(default_factory=list)
    numeric_min: float | None = None
    numeric_max: float | None = None
    numeric_mean: float | None = None
    has_decimals: bool | None = None      # the tell that catches fractional conversions
    magnitude_hint: str | None = None     # the tell that catches micros
    to_dict = asdict


@dataclass
class SourceProfile:
    source_name: str
    row_count: int
    fields: list[FieldProfile]
    detected_grain: str | None = None
    date_field: str | None = None
    date_min: str | None = None
    date_max: str | None = None


def _magnitude_hint(s: pd.Series) -> str | None:
    """Flags values whose scale suggests a unit other than the obvious one."""
    m = s.dropna().abs().median()
    if pd.isna(m) or m == 0:
        return None
    if m > 1_000_000:
        return "median > 1e6 — check for micros / cents / minor units"
    if m < 0.01:
        return "median < 0.01 — check for a rate stored as a fraction"
    return None


def profile_field(name: str, s: pd.Series) -> FieldProfile:
    non_null = s.dropna()
    fp = FieldProfile(
        name=name,
        inferred_type="unknown",
        null_pct=round(float(s.isna().mean()) * 100, 2),
        distinct_count=int(non_null.nunique()),
        samples=[str(v) for v in non_null.head(4).tolist()],
    )

    if non_null.empty:
        return fp

    if non_null.astype(str).str.match(DATE_RE).all():
        fp.inferred_type = "date"
        return fp

    numeric = pd.to_numeric(non_null, errors="coerce")
    if numeric.notna().mean() > 0.95:
        fp.inferred_type = "numeric"
        fp.numeric_min = round(float(numeric.min()), 4)
        fp.numeric_max = round(float(numeric.max()), 4)
        fp.numeric_mean = round(float(numeric.mean()), 4)
        # A metric that is supposed to be a count but has decimals is almost
        # always a modelled/fractional metric. This single boolean is what
        # catches data-driven attribution without any LLM involvement.
        fp.has_decimals = bool((numeric % 1 != 0).any())
        fp.magnitude_hint = _magnitude_hint(numeric)
    else:
        fp.inferred_type = "string"

    return fp


def detect_grain(df: pd.DataFrame, date_field: str) -> str:
    d = pd.to_datetime(df[date_field], errors="coerce").dropna().sort_values().unique()
    if len(d) < 3:
        return "unknown"
    gaps = pd.Series(d).diff().dropna().dt.days
    mode = int(gaps.mode().iloc[0])
    return {1: "daily", 7: "weekly"}.get(mode, "monthly" if mode >= 28 else f"every_{mode}d")


def profile_source(path: str, source_name: str) -> SourceProfile:
    df = pd.read_csv(path)
    fields = [profile_field(c, df[c]) for c in df.columns]

    date_field = next((f.name for f in fields if f.inferred_type == "date"), None)
    grain = detect_grain(df, date_field) if date_field else None
    dmin = dmax = None
    if date_field:
        dt = pd.to_datetime(df[date_field], errors="coerce")
        dmin, dmax = str(dt.min().date()), str(dt.max().date())

    return SourceProfile(
        source_name=source_name,
        row_count=len(df),
        fields=fields,
        detected_grain=grain,
        date_field=date_field,
        date_min=dmin,
        date_max=dmax,
    )


def to_llm_context(p: SourceProfile) -> str:
    """Compact text form for the model. Token cost matters at 400 fields."""
    lines = [
        f"SOURCE: {p.source_name}",
        f"rows={p.row_count} grain={p.detected_grain} "
        f"date_field={p.date_field} range={p.date_min}..{p.date_max}",
        "FIELDS:",
    ]
    for f in p.fields:
        bits = [f"  - {f.name} [{f.inferred_type}]", f"distinct={f.distinct_count}"]
        if f.inferred_type == "numeric":
            bits.append(f"min={f.numeric_min} max={f.numeric_max} mean={f.numeric_mean}")
            bits.append(f"has_decimals={f.has_decimals}")
            if f.magnitude_hint:
                bits.append(f"!! {f.magnitude_hint}")
        bits.append(f"samples={f.samples}")
        lines.append(" ".join(bits))
    return "\n".join(lines)


if __name__ == "__main__":
    for path, name in [
        ("data/metriq_ads_export.csv", "metriq_ads"),
        ("data/lumen_search_export.csv", "lumen_search"),
    ]:
        print(to_llm_context(profile_source(path, name)))
        print()
