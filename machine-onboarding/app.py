"""
Streamlit shell. RUNS AS-IS on minute one — shows real profiling, empty panels
for everything you're about to build. Start the session here so the panel sees
a working thing immediately, then fill the panels live.

    streamlit run app.py
"""
import sys
from pathlib import Path

sys.path.insert(0, "src")
import streamlit as st
import yaml

import profile as prof
import propose
import conflicts
import contract as ctr
import query

st.set_page_config(page_title="Machine · Onboarding", layout="wide")

CLIENT = "acme"
SOURCES = {
    "metriq_ads": "data/metriq_ads_export.csv",
    "lumen_search": "data/lumen_search_export.csv",
}
CANONICAL_PATH = "canonical/metrics.yaml"
TAXONOMY_PATH = "data/acme_taxonomy.md"

st.title("Client Data Onboarding — Reconciliation Review")
st.caption(
    "Slice: propose a semantic contract from conflicting sources, adjudicate the "
    "irreducible conflicts, serve a query that carries its own caveats. "
    "STUBBED: connectors, warehouse, auth, multi-tenancy."
)

st.session_state.setdefault("proposals", None)
st.session_state.setdefault("contract", None)
st.session_state.setdefault("conflicts", None)
st.session_state.setdefault("query_result", None)

profiles = {name: prof.profile_source(path, name) for name, path in SOURCES.items()}


def _axis_of(kind: str) -> str | None:
    return kind.split(":", 1)[1] if ":" in kind else None


def _contract_yaml(c: dict) -> str:
    return yaml.safe_dump(c, sort_keys=False, width=100)


TAB_LABELS = ["1 · Profile", "2 · Proposed mapping", "3 · Conflict queue", "4 · Contract", "5 · Query"]
# A real st.radio (not st.tabs) on purpose: st.tabs doesn't survive st.rerun()
# in this Streamlit version — it silently snaps back to the first tab, which
# would mean accepting a conflict resolution kicks the reviewer back to the
# Profile tab instead of showing them the contract they just wrote.
active_tab = st.radio("navigation", TAB_LABELS, horizontal=True, label_visibility="collapsed", key="active_tab")
st.divider()

if active_tab == TAB_LABELS[0]:
    st.subheader("Deterministic profile")
    st.write("Real. Built in advance — no LLM call, no reason to spend one.")
    for name, p in profiles.items():
        st.markdown(f"**{name}** — {p.row_count} rows · grain `{p.detected_grain}` · "
                    f"{p.date_min} → {p.date_max}")
        st.code(prof.to_llm_context(p), language="text")

elif active_tab == TAB_LABELS[1]:
    st.subheader("Proposed field mappings")
    st.caption(
        "One Claude call. The taxonomy doc is evidence, not authority — where it "
        "disagrees with the profiled data, the model reports the disagreement "
        "instead of silently picking a side, and returns \"unknown\" for any "
        "disclosure axis it can't determine."
    )
    if st.button("Generate proposals", type="primary"):
        with st.spinner("Calling Claude to propose mappings..."):
            profiles_text = "\n\n".join(prof.to_llm_context(p) for p in profiles.values())
            canonical_yaml = Path(CANONICAL_PATH).read_text()
            taxonomy_md = Path(TAXONOMY_PATH).read_text()
            proposals = propose.propose_mappings(profiles_text, canonical_yaml, taxonomy_md)

        c = ctr.new_contract(CLIENT)
        for p in proposals:
            if p.canonical_key:
                ctr.add_mapping(
                    c, source=p.source, source_field=p.source_field,
                    canonical_key=p.canonical_key, confidence=p.confidence,
                    transform=p.unit_transform, disclosures=p.disclosures,
                    evidence=p.evidence, auto=(p.confidence >= 0.9),
                )

        st.session_state.proposals = proposals
        st.session_state.contract = c
        st.session_state.conflicts = None  # stale — needs re-detect against new proposals
        st.session_state.query_result = None

    proposals = st.session_state.proposals
    if not proposals:
        st.info("Not generated yet — click the button above.")
    else:
        groups: dict = {}
        for p in proposals:
            groups.setdefault(p.canonical_key, []).append(p)
        # Unmapped fields need the most attention, so they sort first.
        ordered_keys = sorted(groups, key=lambda k: (k is not None, k or ""))

        for key in ordered_keys:
            group = groups[key]
            label = key or "— no canonical fit —"
            all_high_confidence = key is not None and all(p.confidence > 0.9 for p in group)
            with st.expander(f"{label}  ·  {len(group)} field(s)", expanded=not all_high_confidence):
                for p in group:
                    cols = st.columns([2, 2, 1, 2, 3])
                    cols[0].markdown(f"**{p.source}**")
                    cols[1].write(f"`{p.source_field}`")
                    cols[2].write(f"{p.confidence:.2f}")
                    cols[3].write(p.unit_transform or "—")
                    disclosures = ", ".join(f"{k}={v}" for k, v in (p.disclosures or {}).items()) or "—"
                    cols[4].write(disclosures)
                    st.caption(p.reasoning)
                    st.divider()

elif active_tab == TAB_LABELS[2]:
    st.subheader("Conflicts requiring a decision")
    st.caption(
        "Layer 1: a deterministic schema scan walks every canonical-key collision "
        "group against its disclosure_axes, grain, and date coverage. Layer 2: a "
        "tool-using agent looks for what the schema can't see — doc contradictions, "
        "mixed currency within one source, naming violations, entity scope. Python "
        "enforces a severity floor either layer can raise but neither can lower: "
        "attribution and currency divergence are always BLOCK."
    )
    proposals = st.session_state.proposals
    if not proposals:
        st.info("Generate proposals first (tab 2).")
    else:
        if st.button("Detect conflicts (schema scan + agent)", type="primary"):
            with st.spinner("Schema scan, then a tool-using agent investigates..."):
                taxonomy_md = Path(TAXONOMY_PATH).read_text()
                found = conflicts.detect(profiles, proposals, taxonomy_md)

            c = st.session_state.contract
            c["open_conflicts"] = [
                {
                    "kind": cf.kind, "canonical_key": cf.canonical_key, "axis": _axis_of(cf.kind),
                    "severity": cf.severity, "detail": cf.detail, "sources": cf.sources,
                    "options": cf.options, "recommended": cf.recommended,
                }
                for cf in found
            ]
            ctr.save(c)
            st.session_state.conflicts = found
            st.session_state.contract = c
            st.session_state.query_result = None

        found = st.session_state.conflicts
        if found is None:
            st.info("Not run yet — click the button above.")
        elif not found:
            st.success("No conflicts detected.")
        else:
            c = st.session_state.contract
            decided_by = st.text_input("Decided by", value="demo-reviewer", key="decided_by")
            severity_ui = {"BLOCK": st.error, "REVIEW": st.warning, "AUTO": st.success}
            resolutions = c.get("resolutions", [])

            for i, cf in enumerate(found):
                axis = _axis_of(cf.kind)
                resolution = next(
                    (r for r in resolutions
                     if r["conflict_kind"] == cf.kind and r["canonical_key"] == cf.canonical_key
                     and r.get("axis") == axis),
                    None,
                )
                with st.container(border=True):
                    severity_ui.get(cf.severity, st.info)(f"{cf.severity} · {cf.kind}  —  `{cf.canonical_key}`")
                    st.caption("sources: " + ", ".join(cf.sources))
                    st.write(cf.detail)
                    if resolution:
                        st.success(
                            f"Resolved: **{resolution['decision']}** — {resolution['rationale']}  \n"
                            f"_by {resolution['decided_by']} at {resolution['decided_at']}_"
                        )
                    else:
                        default_idx = cf.options.index(cf.recommended) if cf.recommended in cf.options else 0
                        choice = st.radio("Decision", cf.options, index=default_idx, key=f"choice_{i}")
                        rationale = st.text_input("Rationale", key=f"rationale_{i}")
                        if st.button("Accept resolution", key=f"accept_{i}"):
                            ctr.resolve(
                                c, conflict_kind=cf.kind, canonical_key=cf.canonical_key,
                                decision=choice, rationale=rationale or "(no rationale given)",
                                decided_by=decided_by or "unknown", axis=axis,
                            )
                            ctr.bump(c)
                            ctr.save(c)
                            st.session_state.contract = c
                            st.session_state.query_result = None
                            st.rerun()

            st.subheader("Contract (live)")
            st.caption(f"contracts/{CLIENT}.yaml — version {c['version']}")
            st.code(_contract_yaml(c), language="yaml")

elif active_tab == TAB_LABELS[3]:
    st.subheader("Semantic contract")
    c = st.session_state.contract
    if not c:
        st.info("Generate proposals first (tab 2).")
    else:
        burden = ctr.review_burden(c)
        cols = st.columns(4)
        cols[0].metric("Fields mapped", burden["fields_total"])
        cols[1].metric("Auto-accepted", f"{burden['auto_accepted']} ({burden['auto_rate']:.0%})")
        cols[2].metric("Open conflicts", burden["open_conflicts"])
        cols[3].metric("Resolutions recorded", burden["resolutions_recorded"])
        st.code(_contract_yaml(c), language="yaml")

elif active_tab == TAB_LABELS[4]:
    st.subheader("Query through the contract")
    c = st.session_state.contract
    if not c:
        st.info("Generate proposals first (tab 2).")
    else:
        st.caption(
            'Hardcoded question: "What was total media spend and conversions by '
            'campaign, across both platforms, for May 2026?" An agent would '
            "generate this query in production — this slice tests that the answer "
            "carries its own caveats, not the query planner."
        )
        if st.button("Run query", type="primary"):
            st.session_state.query_result = query.run_hardcoded_query(c, data_dir="data")

        result = st.session_state.query_result
        if result:
            st.markdown("**By campaign** (never joined across sources — entity resolution is out of scope)")
            st.dataframe(result["rows"], use_container_width=True)

            st.markdown("**Totals across both platforms**")
            metric_cols = st.columns(len(result["totals"]))
            for col, (metric, t) in zip(metric_cols, result["totals"].items()):
                if t["combined"] is not None:
                    col.metric(metric, f"{t['combined']:,.2f}")
                else:
                    col.metric(metric, "not summable")
                    col.caption(", ".join(f"{s}={v:,.2f}" for s, v in t["by_source"].items()))

            if result["caveats"]:
                st.markdown("**Caveats**")
                for cv in result["caveats"]:
                    st.error(f"**{cv['metric']}** ({cv['severity']}): {cv['text']}")
                    st.caption(
                        f"decided_by={cv['decided_by']}  ·  decided_at={cv['decided_at']}  ·  "
                        f"contract_version={cv['contract_version']}"
                    )
