"""Schema-scan tests — no API key required.

The scalable claim is that adding a disclosure axis to metrics.yaml creates a
new conflict class without a new if-statement. These tests lock that in.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

import profile as prof  # noqa: E402
from conflicts import (  # noqa: E402
    Conflict,
    apply_policy,
    load_ontology,
    scan_schema,
)
from propose import Proposal  # noqa: E402


def _profiles():
    return {
        "metriq_ads": prof.profile_source(str(ROOT / "data/metriq_ads_export.csv"), "metriq_ads"),
        "lumen_search": prof.profile_source(str(ROOT / "data/lumen_search_export.csv"), "lumen_search"),
    }


def _proposals():
    return [
        Proposal("metriq_ads", "spend", "media_spend", 0.96, "", [],
                 {"fee_inclusion": "excl_platform_fees", "currency": "USD"}, None),
        Proposal("lumen_search", "cost_micros", "media_spend", 0.94, "", [],
                 {"fee_inclusion": "incl_platform_fees", "currency": "USD"}, "divide_by_1e6"),
        Proposal("metriq_ads", "conversions", "conversions", 0.91, "", [],
                 {"attribution_model": "last_click", "attribution_window": "7d_click_1d_view"}, None),
        Proposal("lumen_search", "conversions", "conversions", 0.9, "", [],
                 {"attribution_model": "data_driven", "attribution_window": "30d_any"}, None),
        Proposal("metriq_ads", "clicks", "clicks", 0.88, "", [],
                 {"click_type": "link_clicks"}, None),
        Proposal("lumen_search", "clicks", "clicks", 0.87, "", [],
                 {"click_type": "all_clicks"}, None),
        Proposal("metriq_ads", "date", "date", 0.99, "", [], {"grain": "daily"}, None),
        Proposal("lumen_search", "week_start_date", "date", 0.99, "", [], {"grain": "weekly"}, None),
    ]


def test_schema_scan_is_ontology_driven():
    conflicts = scan_schema(_profiles(), _proposals(), load_ontology(ROOT / "canonical/metrics.yaml"))
    kinds = {(c.kind, c.canonical_key, c.axis) for c in conflicts}

    assert ("GRAIN_MISMATCH", "date", "grain") in kinds
    assert ("UNIT_MISMATCH", "media_spend", "unit") in kinds
    assert ("DEFINITION_DIVERGENCE", "conversions", "attribution_model") in kinds
    assert ("DEFINITION_DIVERGENCE", "conversions", "attribution_window") in kinds
    assert ("DEFINITION_DIVERGENCE", "clicks", "click_type") in kinds
    assert ("DEFINITION_DIVERGENCE", "media_spend", "fee_inclusion") in kinds
    assert ("CURRENCY_MIXED", "media_spend", "currency") in kinds

    by = {(c.kind, c.axis): c for c in conflicts}
    assert by[("DEFINITION_DIVERGENCE", "attribution_model")].severity == "BLOCK"
    assert by[("DEFINITION_DIVERGENCE", "click_type")].severity == "REVIEW"
    assert by[("UNIT_MISMATCH", "unit")].severity == "AUTO"
    assert by[("CURRENCY_MIXED", "currency")].severity == "BLOCK"


def test_unknown_is_not_a_divergence():
    proposals = [
        Proposal("metriq_ads", "conversions", "conversions", 0.9, "", [],
                 {"attribution_model": "unknown"}, None),
        Proposal("lumen_search", "conversions", "conversions", 0.9, "", [],
                 {"attribution_model": "data_driven"}, None),
    ]
    conflicts = scan_schema(_profiles(), proposals, load_ontology(ROOT / "canonical/metrics.yaml"))
    axes = {c.axis for c in conflicts if c.kind == "DEFINITION_DIVERGENCE"}
    assert "attribution_model" not in axes


def test_policy_floor_cannot_auto_attribution():
    lowered = apply_policy(Conflict(
        kind="DEFINITION_DIVERGENCE",
        severity="AUTO",
        canonical_key="conversions",
        sources=["metriq_ads", "lumen_search"],
        detail="should be raised",
        options=["keep_split_by_source"],
        recommended="keep_split_by_source",
        axis="attribution_window",
        origin="agent",
    ))
    assert lowered.severity == "BLOCK"


if __name__ == "__main__":
    test_schema_scan_is_ontology_driven()
    test_unknown_is_not_a_divergence()
    test_policy_floor_cannot_auto_attribution()
    print("ok")
