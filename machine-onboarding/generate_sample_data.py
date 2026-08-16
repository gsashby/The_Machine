"""
Generates the two conflicting ad-platform exports + a contradicting taxonomy doc.

Every conflict below is PLANTED ON PURPOSE. Keep this file — when the panel asks
"how did you make the sample data?", this is the answer, and the comments are the
list of what your reconciliation layer is supposed to catch.

Planted conflicts (the answer key):
  1. NAMING      spend            vs cost_micros        -> same concept, different name
  2. UNIT        USD              vs micros (1e6)       -> silent 1,000,000x error if missed
  3. INCLUSION   spend ex-fees    vs cost incl-fees     -> invisible in data; only docs/priors know
  4. GRAIN       daily            vs weekly             -> cannot join without a decision
  5. DEFINITION  conv 7d-click/1d-view (int)
                 vs conv data-driven 30d (fractional)   -> VISIBLE tell: B has decimals
  6. DEFINITION  clicks = link clicks
                 vs clicks = all clicks                 -> INVISIBLE in data. Docs only.
  7. CURRENCY    B has a GBP campaign, A is USD-only    -> good curveball for the panel
  8. FIELD NAME  "impr." (literal period)               -> realistic export artifact
  9. ENTITY      same campaign, different IDs + names   -> out of scope; flag, don't solve
 10. DOC LIES    taxonomy.md asserts a naming convention
                 that ~40% of real campaigns violate,
                 and defines spend the OPPOSITE of A    -> doc is evidence, not authority
"""

import csv
import random
from datetime import date, timedelta

random.seed(1337)

START = date(2026, 4, 6)  # a Monday
DAYS = 91

# (concept, metriq_name, lumen_name, region, channel_ok)
CAMPAIGNS = [
    ("spring_brand", "ACME_NA_SOCIAL_Q2", "ACME_NA_SEARCH_Q2", "NA", True),
    ("always_on",    "ACME_NA_SOCIAL_ALWAYSON", "acme-na-search-alwayson", "NA", False),
    ("emea_launch",  "ACME_EMEA_SOCIAL_Q2", "ACME_EMEA_SEARCH_Q2", "EMEA", True),
    ("retarget",     "Retargeting Q2 (new)", "ACME_NA_SEARCH_RETARGET_Q2", "NA", False),
    ("apac_test",    "ACME_APAC_SOCIAL_Q2", "ACME-APAC-SEARCH-Q2", "APAC", False),
    ("promo_may",    "ACME_NA_SOCIAL_PROMO_Q2", "ACME_NA_SEARCH_PROMO_Q2", "NA", True),
]

OBJECTIVES = {
    "spring_brand": "OUTCOME_AWARENESS",
    "always_on": "OUTCOME_TRAFFIC",
    "emea_launch": "OUTCOME_AWARENESS",
    "retarget": "OUTCOME_SALES",
    "apac_test": "OUTCOME_TRAFFIC",
    "promo_may": "OUTCOME_SALES",
}

LUMEN_TYPES = {
    "spring_brand": "Search",
    "always_on": "Search",
    "emea_launch": "Performance Max",
    "retarget": "Search",
    "apac_test": "Display",
    "promo_may": "Shopping",
}


def daily_rows():
    """Platform A - 'Metriq Ads' (Meta-like). Daily grain, USD, integer conversions."""
    rows = []
    for i in range(DAYS):
        d = START + timedelta(days=i)
        weekend = d.weekday() >= 5
        for concept, mname, _, region, _ in CAMPAIGNS:
            if concept == "promo_may" and not (date(2026, 5, 4) <= d <= date(2026, 5, 24)):
                continue  # flighted campaign - creates real date gaps
            base = {"spring_brand": 1800, "always_on": 640, "emea_launch": 1400,
                    "retarget": 420, "apac_test": 260, "promo_may": 2200}[concept]
            spend = base * random.uniform(0.72, 1.31) * (0.68 if weekend else 1.0)
            cpm = random.uniform(6.2, 11.8)
            impressions = int(spend / cpm * 1000)
            ctr = random.uniform(0.006, 0.021)
            clicks = int(impressions * ctr)  # LINK clicks only
            cvr = random.uniform(0.015, 0.058)
            convs = int(clicks * cvr)  # integer: 7d-click + 1d-view
            rows.append({
                "date": d.isoformat(),
                "campaign_name": mname,
                "campaign_id": f"23848{abs(hash(concept)) % 100000:05d}",
                "adset_name": f"{mname}__AS{random.randint(1, 3)}",
                "objective": OBJECTIVES[concept],
                "spend": f"{spend:.2f}",          # USD, EXCLUDES platform fees
                "impressions": impressions,
                "clicks": clicks,                  # link clicks
                "conversions": convs,              # 7d click / 1d view
                "conversion_value": f"{convs * random.uniform(38, 96):.2f}",
            })
    return rows


def weekly_rows():
    """Platform B - 'Lumen Search' (Google-like). Weekly grain, micros, fractional convs."""
    rows = []
    for w in range(DAYS // 7):
        ws = START + timedelta(days=w * 7)
        for concept, _, lname, region, _ in CAMPAIGNS:
            if concept == "promo_may" and not (date(2026, 5, 1) <= ws <= date(2026, 5, 25)):
                continue
            base = {"spring_brand": 9100, "always_on": 3300, "emea_launch": 7400,
                    "retarget": 2600, "apac_test": 1500, "promo_may": 10200}[concept]
            cost = base * random.uniform(0.78, 1.26)   # INCLUDES platform fees
            cpc = random.uniform(0.94, 3.40)
            clicks = int(cost / cpc)                    # ALL clicks, not just link
            impressions = int(clicks / random.uniform(0.028, 0.091))
            convs = clicks * random.uniform(0.012, 0.049)  # FRACTIONAL: data-driven, 30d
            rows.append({
                "week_start_date": ws.isoformat(),
                "campaign": lname,
                "campaign_id": f"{random.randint(10, 21)}{abs(hash(concept)) % 1000000:06d}",
                "ad_group": f"{lname}::ag{random.randint(1, 4)}",
                "campaign_type": LUMEN_TYPES[concept],
                "currency": "GBP" if region == "EMEA" else "USD",  # curveball
                "cost_micros": int(cost * 1_000_000),   # MICROS
                "impr.": impressions,                    # literal period in header
                "clicks": clicks,
                "conversions": f"{convs:.2f}",           # fractional - the visible tell
                "conv_value": f"{convs * random.uniform(41, 112):.2f}",
            })
    return rows


def write(path, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {path}  ({len(rows)} rows, {len(rows[0])} cols)")


TAXONOMY = """# ACME Corp — Marketing Data Taxonomy & Measurement Standards

**Owner:** Marketing Operations
**Last reviewed:** 2024-11-08
**Status:** Approved — v3.1

---

## 1. Campaign Naming Convention

All paid media campaigns **must** follow:

```
{BRAND}_{REGION}_{CHANNEL}_{QUARTER}
```

- `BRAND` — always `ACME` for core brand activity.
- `REGION` — one of `NA`, `EMEA`, `APAC`, `LATAM`.
- `CHANNEL` — one of `SOCIAL`, `SEARCH`, `DISPLAY`, `VIDEO`.
- `QUARTER` — `Q1`–`Q4`.

Separator is the underscore character. Hyphens are not permitted.
Campaigns that do not conform should be renamed at the next flight.

## 2. Channel Taxonomy

| Channel code | Definition | Platforms |
|---|---|---|
| SOCIAL | Paid placements on social feeds | Metriq Ads |
| SEARCH | Keyword-targeted search results | Lumen Search |
| DISPLAY | Banner / programmatic display | Lumen Search, DSP |
| VIDEO | Pre-roll and in-stream video | Metriq Ads, DSP |

> Note: `Performance Max` and `Shopping` campaign types in Lumen Search are
> mapped to `SEARCH` for reporting purposes.

## 3. Metric Definitions

### 3.1 Spend
Media spend is reported in **USD** and is defined as **gross media cost,
inclusive of platform fees and exclusive of agency fees.**
All platforms report spend on this basis.

### 3.2 Clicks
A click is any user interaction that results in navigation to an ACME-owned
property. Platform-native engagement clicks (expands, profile taps, carousel
swipes) are excluded.

### 3.3 Conversions
A conversion is a completed purchase or qualified lead. ACME's standard
attribution window is **28-day click, 1-day view**, applied consistently
across all media platforms.

### 3.4 Reporting Grain
All performance data is reported at **daily** grain and rolled up weekly
for executive reporting.

## 4. Currency

All reporting is normalised to **USD** at the month-average rate published
by Treasury. Source systems should be configured to report in USD directly.

---

*Questions: marketing-ops@acme.example (Note: this alias is no longer
monitored; contact the Analytics team.)*
"""

if __name__ == "__main__":
    write("data/metriq_ads_export.csv", daily_rows())
    write("data/lumen_search_export.csv", weekly_rows())
    with open("data/acme_taxonomy.md", "w") as f:
        f.write(TAXONOMY)
    print("wrote data/acme_taxonomy.md")
