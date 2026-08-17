"""
Streamlit shell. Profile is deterministic and pre-built. Mapping proposal and
the conflict agent are live model calls. Start here so the panel sees a working
thing immediately.

    streamlit run app.py
"""
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, "src")
import streamlit as st
import profile as prof
import contract as ct
import propose as pr
import conflicts as cfl

st.set_page_config(page_title="Machine · Onboarding", layout="wide")

SOURCES = {
    "metriq_ads": "data/metriq_ads_export.csv",
    "lumen_search": "data/lumen_search_export.csv",
}
CONTRACT_PATH = Path("contracts/acme.yaml")
CANONICAL_PATH = Path("canonical/metrics.yaml")
TAXONOMY_PATH = Path("data/acme_taxonomy.md")


def _load_dotenv() -> None:
    env = Path(".env")
    if not env.exists():
        return
    import os

    for line in env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip().strip("'").strip('"'))


_load_dotenv()

st.title("Client Data Onboarding — Reconciliation Review")
st.caption(
    "Slice: propose a semantic contract from conflicting sources, adjudicate the "
    "irreducible conflicts, serve a query that carries its own caveats. "
    "STUBBED: connectors, warehouse, auth, multi-tenancy, the query agent."
)

profiles = {name: prof.profile_source(path, name) for name, path in SOURCES.items()}
taxonomy_md = TAXONOMY_PATH.read_text() if TAXONOMY_PATH.exists() else ""
canonical_yaml = CANONICAL_PATH.read_text() if CANONICAL_PATH.exists() else ""

tab_profile, tab_propose, tab_conflicts, tab_contract, tab_query = st.tabs(
    ["1 · Profile", "2 · Proposed mapping", "3 · Conflict queue", "4 · Contract", "5 · Query"]
)

with tab_profile:
    st.subheader("Deterministic profile")
    st.write("Real. Built in advance — no LLM call, no reason to spend one.")
    for name, path in SOURCES.items():
        p = profiles[name]
        st.markdown(
            f"**{name}** — {p.row_count} rows · grain `{p.detected_grain}` · "
            f"{p.date_min} → {p.date_max}"
        )
        st.code(prof.to_llm_context(p), language="text")

with tab_propose:
    st.subheader("Proposed field mappings")
    st.caption(
        "LLM. Taxonomy is evidence, not authority. Undetermined disclosure axes "
        "must come back as `unknown`."
    )
    if st.button("Run proposal", type="primary"):
        profiles_text = "\n\n".join(prof.to_llm_context(p) for p in profiles.values())
        with st.spinner("Asking the model for mappings…"):
            st.session_state.proposals = pr.propose_mappings(
                profiles_text, canonical_yaml, taxonomy_md
            )

    proposals = st.session_state.get("proposals") or []
    if not proposals:
        st.info("Run the proposal to map source fields onto the canonical schema.")
    else:
        grouped: dict[str, list] = defaultdict(list)
        unmapped = []
        for item in proposals:
            key = item.canonical_key or "(unmapped)"
            if item.canonical_key:
                grouped[key].append(item)
            else:
                unmapped.append(item)
        for key in sorted(grouped):
            items = grouped[key]
            st.markdown(f"### `{key}`")
            for item in sorted(items, key=lambda x: x.confidence):
                collapsed = item.confidence > 0.9
                title = (
                    f"{item.source}.{item.source_field}  ·  "
                    f"confidence {item.confidence:.2f}  ·  "
                    f"transform `{item.unit_transform or 'identity'}`"
                )
                with st.expander(title, expanded=not collapsed):
                    st.write(item.reasoning)
                    st.json({
                        "disclosures": item.disclosures,
                        "evidence": item.evidence,
                    })
        if unmapped:
            st.markdown("### Unmapped")
            for item in unmapped:
                st.write(f"- `{item.source}.{item.source_field}` ({item.confidence:.2f}) — {item.reasoning}")

with tab_conflicts:
    st.subheader("Conflicts requiring a decision")
    st.caption(
        "Two layers: a schema scan walks collision groups against "
        "`canonical/metrics.yaml` disclosure axes, then a tool-using agent "
        "finds what the schema cannot see. Python enforces severity floors — "
        "the model cannot AUTO an irreducible definition."
    )
    if not st.session_state.get("proposals"):
        st.warning("Run the mapping proposal first — the agent inspects collisions, not raw CSVs.")
    else:
        if st.button("Detect conflicts", type="primary"):
            with st.spinner("Schema scan + conflict agent…"):
                detected = cfl.detect(
                    profiles, st.session_state.proposals, taxonomy_md
                )
                st.session_state.conflicts = detected
                contract = ct.new_contract("acme")
                for name, path in SOURCES.items():
                    p = profiles[name]
                    contract["sources"][name] = {
                        "path": path,
                        "grain": p.detected_grain,
                        "date_field": p.date_field,
                    }
                for item in st.session_state.proposals:
                    if not item.canonical_key:
                        continue
                    ct.add_mapping(
                        contract,
                        source=item.source,
                        source_field=item.source_field,
                        canonical_key=item.canonical_key,
                        confidence=item.confidence,
                        transform=item.unit_transform,
                        disclosures=item.disclosures,
                        evidence=item.evidence,
                        auto=item.confidence > 0.9,
                    )
                contract["open_conflicts"] = [cfl.conflict_to_dict(c) for c in detected]
                ct.save(contract, CONTRACT_PATH)
                st.session_state.contract = contract

        status = cfl.LAST_RUN
        if status:
            cols = st.columns(4)
            cols[0].metric("Schema conflicts", status.get("schema", "—"))
            cols[1].metric("Agent submitted", status.get("submitted", "—"))
            cols[2].metric("Agent turns", status.get("turns", "—"))
            cols[3].metric("Queue total", status.get("total", "—"))
            if status.get("agent") == "error":
                st.error(f"Agent failed; showing schema scan only. {status.get('agent_error')}")
            elif status.get("agent") == "ok":
                st.success(
                    f"Agent finished in {status.get('turns')} turn(s); "
                    f"policy merge kept {status.get('total')} conflicts."
                )

        queue = st.session_state.get("conflicts") or []
        if not queue:
            st.info("No conflicts detected yet.")
        else:
            for i, conf in enumerate(queue):
                badge = f"{conf.severity} · {conf.kind} · {conf.origin}"
                header = f"`{conf.canonical_key}` — {badge}"
                with st.container(border=True):
                    st.markdown(f"**{header}**")
                    st.write(conf.detail)
                    if conf.evidence:
                        with st.expander("Evidence"):
                            for ev in conf.evidence:
                                st.write(f"- {ev}")
                    if conf.axis:
                        st.caption(f"axis: `{conf.axis}` · sources: {', '.join(conf.sources)}")
                    decision = st.radio(
                        "Decision",
                        conf.options,
                        index=conf.options.index(conf.recommended)
                        if conf.recommended in conf.options
                        else 0,
                        key=f"opt_{i}_{conf.kind}_{conf.canonical_key}_{conf.axis}",
                    )
                    rationale = st.text_area(
                        "Rationale",
                        key=f"rat_{i}_{conf.kind}_{conf.canonical_key}_{conf.axis}",
                        placeholder="Required. This becomes the authored record.",
                    )
                    if st.button("Accept decision", key=f"acc_{i}_{conf.kind}_{conf.canonical_key}_{conf.axis}"):
                        if not rationale.strip():
                            st.error("Rationale is required — a decision without a why is a guess.")
                        else:
                            contract = st.session_state.get("contract")
                            if contract is None and CONTRACT_PATH.exists():
                                contract = ct.load(CONTRACT_PATH)
                            if contract is None:
                                st.error("No contract to write to — run detect first.")
                            else:
                                ct.resolve(
                                    contract,
                                    conflict_kind=conf.kind,
                                    canonical_key=conf.canonical_key,
                                    decision=decision,
                                    rationale=rationale.strip(),
                                    decided_by="live-session",
                                    axis=conf.axis,
                                )
                                ct.bump(contract)
                                ct.save(contract, CONTRACT_PATH)
                                st.session_state.contract = contract
                                st.session_state.conflicts = [
                                    c for c in queue
                                    if not (
                                        c.kind == conf.kind
                                        and c.canonical_key == conf.canonical_key
                                        and c.axis == conf.axis
                                    )
                                ]
                                st.rerun()

        if CONTRACT_PATH.exists():
            st.markdown("#### Contract YAML")
            st.code(CONTRACT_PATH.read_text(), language="yaml")

with tab_contract:
    st.subheader("Semantic contract")
    p = CONTRACT_PATH
    if p.exists():
        st.code(p.read_text(), language="yaml")
        st.json(ct.review_burden(ct.load(p)))
    else:
        st.info("No contract written yet.")

with tab_query:
    st.subheader("Query through the contract")
    st.info("Not built yet — live-build iteration 5. The payoff.")
