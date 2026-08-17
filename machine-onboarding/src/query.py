"""
Iteration 5. The payoff.

Executes ONE hardcoded question through the ratified contract and returns the
number WITH its caveats attached: "What was total media spend and
conversions by campaign, across both platforms, for May 2026?"

An agent would generate this query in production; it is hardcoded here on
purpose -- the agent layer is not what this slice tests. What IS being
tested is that the answer carries its own provenance: the caveat is a
property of the result object, not a footnote someone might not read.

Campaign identity is never joined across sources -- entity resolution across
platform-scoped campaign_ids is explicitly out of scope (see
canonical/metrics.yaml's note on campaign_id), so `rows` is always split by
source at the campaign grain. `totals` additionally rolls each metric up
across BOTH platforms -- but only when nothing in the contract says that sum
is unsafe. Any canonical metric with an unresolved BLOCK conflict (or a
resolution whose decision was to keep sources separate) gets `combined: None`
plus a caveat instead of a number.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

MAY_START = pd.Timestamp("2026-05-01")
MAY_END = pd.Timestamp("2026-05-31")

_TRANSFORM_RE = re.compile(r"^(?P<op>divide_by|multiply_by)_(?P<factor>[0-9.eE]+)$")


def _apply_transform(values: pd.Series, transform: str | None) -> pd.Series:
    if not transform or transform.strip().lower() in {"none", "identity"}:
        return values
    m = _TRANSFORM_RE.match(transform.strip())
    if not m:
        return values  # unrecognised transform string -- no-op rather than guess
    factor = float(m.group("factor"))
    return values / factor if m.group("op") == "divide_by" else values * factor


def _mapping_for(maps: dict, canonical_key: str) -> dict | None:
    return next((m for m in maps.values() if m["canonical_key"] == canonical_key), None)


def _monthly_campaign_totals(source: str, data_dir: str, mappings: list) -> pd.DataFrame:
    """One row per campaign_name for this source, summed over May 2026, after
    reconciling grain: a daily source is rolled up to weekly buckets first so
    both sources are aggregated at the same period boundary before summing."""
    df = pd.read_csv(Path(data_dir) / f"{source}_export.csv")
    maps = {m["source_field"]: m for m in mappings if m["source"] == source}

    date_map = _mapping_for(maps, "date")
    campaign_map = _mapping_for(maps, "campaign_name")
    if date_map is None or campaign_map is None:
        return pd.DataFrame(columns=["campaign_name", "media_spend", "conversions"])

    work = pd.DataFrame({
        "campaign_name": df[campaign_map["source_field"]],
        "event_date": pd.to_datetime(df[date_map["source_field"]]),
    })
    for key in ("media_spend", "conversions"):
        metric_map = _mapping_for(maps, key)
        if metric_map is None:
            work[key] = 0.0
            continue
        values = pd.to_numeric(df[metric_map["source_field"]], errors="coerce").fillna(0.0)
        work[key] = _apply_transform(values, metric_map.get("transform"))

    grain = (date_map.get("disclosures") or {}).get("grain", "unknown")
    if grain == "daily":
        work["week_start_date"] = work["event_date"] - pd.to_timedelta(work["event_date"].dt.weekday, unit="D")
    else:
        work["week_start_date"] = work["event_date"]

    weekly = work.groupby(["campaign_name", "week_start_date"], as_index=False)[["media_spend", "conversions"]].sum()
    may = weekly[(weekly["week_start_date"] >= MAY_START) & (weekly["week_start_date"] <= MAY_END)]
    return may.groupby("campaign_name", as_index=False)[["media_spend", "conversions"]].sum()


def _blocked_metrics(contract: dict) -> dict[str, dict]:
    """canonical_key -> the fact that makes summing it across sources unsafe,
    whether that's still an open BLOCK or a resolution that chose to keep
    sources separate rather than harmonise them."""
    blocked = {}
    for oc in contract.get("open_conflicts", []):
        if oc.get("severity") == "BLOCK":
            blocked[oc["canonical_key"]] = {
                "text": oc.get("detail", ""), "decided_by": None, "decided_at": None,
            }
    for res in contract.get("resolutions", []):
        if "separat" in (res.get("decision") or "").lower():
            blocked[res["canonical_key"]] = {
                "text": res.get("rationale", ""),
                "decided_by": res.get("decided_by"), "decided_at": res.get("decided_at"),
            }
    return blocked


def run_hardcoded_query(contract: dict, data_dir: str = "data") -> dict:
    mappings = contract.get("mappings", [])
    sources = sorted({m["source"] for m in mappings})

    rows = []
    by_source_totals = {"media_spend": {}, "conversions": {}}
    for source in sources:
        monthly = _monthly_campaign_totals(source, data_dir, mappings)
        for _, r in monthly.iterrows():
            spend, convs = round(float(r["media_spend"]), 2), round(float(r["conversions"]), 2)
            rows.append({
                "source": source,
                "campaign_name": r["campaign_name"],
                "media_spend": spend,
                "conversions": convs,
            })
            by_source_totals["media_spend"][source] = by_source_totals["media_spend"].get(source, 0.0) + spend
            by_source_totals["conversions"][source] = by_source_totals["conversions"].get(source, 0.0) + convs
    rows.sort(key=lambda r: (r["source"], r["campaign_name"]))

    blocked = _blocked_metrics(contract)
    totals, caveats = {}, []
    for key in ("media_spend", "conversions"):
        by_source = {s: round(v, 2) for s, v in by_source_totals[key].items()}
        block = blocked.get(key)
        totals[key] = {"by_source": by_source, "combined": None if block else round(sum(by_source.values()), 2)}
        if block:
            caveats.append({
                "metric": key,
                "severity": "BLOCK",
                "text": block["text"],
                "decided_by": block["decided_by"],
                "decided_at": block["decided_at"],
                "contract_version": contract.get("version"),
            })

    return {"rows": rows, "totals": totals, "caveats": caveats}
