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
import profile as prof
import contract as ct

st.set_page_config(page_title="Machine · Onboarding", layout="wide")

SOURCES = {
    "metriq_ads": "data/metriq_ads_export.csv",
    "lumen_search": "data/lumen_search_export.csv",
}

st.title("Client Data Onboarding — Reconciliation Review")
st.caption(
    "Slice: propose a semantic contract from conflicting sources, adjudicate the "
    "irreducible conflicts, serve a query that carries its own caveats. "
    "STUBBED: connectors, warehouse, auth, multi-tenancy, the agent layer."
)

tab_profile, tab_propose, tab_conflicts, tab_contract, tab_query = st.tabs(
    ["1 · Profile", "2 · Proposed mapping", "3 · Conflict queue", "4 · Contract", "5 · Query"]
)

with tab_profile:
    st.subheader("Deterministic profile")
    st.write("Real. Built in advance — no LLM call, no reason to spend one.")
    for name, path in SOURCES.items():
        p = prof.profile_source(path, name)
        st.markdown(f"**{name}** — {p.row_count} rows · grain `{p.detected_grain}` · "
                    f"{p.date_min} → {p.date_max}")
        st.code(prof.to_llm_context(p), language="text")

with tab_propose:
    st.subheader("Proposed field mappings")
    st.info("Not built yet — this is live-build iteration 1–2.")

with tab_conflicts:
    st.subheader("Conflicts requiring a decision")
    st.info("Not built yet — live-build iteration 3.")

with tab_contract:
    st.subheader("Semantic contract")
    p = Path("contracts/acme.yaml")
    if p.exists():
        st.code(p.read_text(), language="yaml")
        st.json(ct.review_burden(ct.load(p)))
    else:
        st.info("No contract written yet.")

with tab_query:
    st.subheader("Query through the contract")
    st.info("Not built yet — live-build iteration 5. The payoff.")
