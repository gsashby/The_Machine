"""
SKELETON — YOU BUILD THIS LIVE. Iteration 5, if you get there.

The payoff. Executes ONE hardcoded question through the ratified contract and
returns the number WITH its caveats attached.

Hardcoded question: "What was total media spend and conversions by campaign,
across both platforms, for May 2026?"

Say clearly: an agent would generate this query. I am hardcoding it because the
agent layer is not what I'm testing. What I AM testing is that the answer
carries its own provenance — that the caveat is a property of the result, not
a footnote someone might read.

Target shape of the return value:
    {
      "rows": [...],
      "caveats": [
        {"metric": "conversions", "severity": "BLOCK",
         "text": "metriq_ads uses 7d-click/1d-view; lumen_search uses
                  data-driven 30d. These are NOT summable. Shown separately.",
         "decided_by": "…", "decided_at": "…", "contract_version": "…"}
      ]
    }
"""
from __future__ import annotations


def run_hardcoded_query(contract: dict, data_dir: str = "data") -> dict:
    """TODO — build live. duckdb or pandas, whichever is faster to type."""
    raise NotImplementedError("Build me in the session.")
