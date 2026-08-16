# ACME Corp — Marketing Data Taxonomy & Measurement Standards

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
