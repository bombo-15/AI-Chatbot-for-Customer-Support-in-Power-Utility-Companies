# Ghana Electricity Tariffs Dataset (2000–2026)

**File:** `ghana_electricity_tariffs_2000_2026.csv` (272 rows)

A row-per-observation dataset of PURC-approved electricity tariffs in Ghana,
compiled for the power chatbot project. Built by combining PURC's own
primary-source decision papers/gazettes (downloaded and text-extracted
directly) with PURC's Dec-2020 "Trends in Electricity Tariffs" research
report and a small number of news reports for gaps that have no public
gazette PDF.

## Columns

| Column | Meaning |
|---|---|
| `effective_date` | Date the tariff took effect (YYYY-MM-DD). For pre-2010 rows this is the month PURC's own historical note attaches to the event, not a specific gazette date. |
| `year` | Calendar year, for easy filtering/grouping. |
| `review_type` | `Major` (multi-year review), `AAF`/`Quarterly` (Automatic Adjustment Formula routine review), `No change`, `Policy`, `Ad hoc`, `Proposal`. |
| `granularity` | `narrative` (2000s, no numeric rate found), `blended_average` (2010–2020, one blended GHp/kWh per broad category), `per_band_exact` (2022–2026, exact per-consumption-band gazette figures), `computed_partial`/`computed_derived` (see below). |
| `customer_category` | e.g. Residential, Residential Lifeline, Non-Residential, SLT-LV/MV/HV/Mines, EV Charging. |
| `band` | Consumption band (kWh/month) or charge type, where applicable. |
| `measure` | `GHp/kWh` (energy charge) or `Service Charge` (flat monthly charge). |
| `value` | The number itself. Blank where only a % change is known (see `source_type`). |
| `unit` | Unit of `value`. |
| `pct_change` | % change vs. the previous tariff decision, where PURC published one. |
| `source_type` | See **Confidence levels** below. |
| `source` | Document/URL the row was taken from. |
| `notes` | Context: why the change happened, what it replaced, caveats. |

## Confidence levels (`source_type`)

- **`exact_gazette`** — copied directly from a PURC gazette ("Publication of
  Electricity Tariffs") or an official Decision Paper's approved-tariff
  appendix/table. Highest confidence; these are the legally binding figures.
- **`exact_published`** — copied directly from PURC's own Trends study
  Table 5 (2010–2020 blended averages). PURC-published, but blended across
  sub-bands rather than the raw gazette figure for each band.
- **`computed_from_pct`** — not found as a gazetted figure; derived by
  applying a *PURC-published* percentage change to the nearest exact
  anchor point (used only for Jul 2024, which sits between two exact
  anchors — Sep 2023 and Oct 2024 — and for which the underlying gazette
  PDF (No. 116, 2 Jul 2024) is a scanned image with no extractable text).
- **`narrative_only`** — no numeric rate available at all, only a dated
  event description and/or a percentage change reported in the press or
  in PURC's own historical narrative. Covers 2000–2009 almost entirely,
  plus the residential/non-residential/SLT-LV % changes for Apr 2024 that
  PURC did not break down by consumption band.

**Do not treat `narrative_only` or `computed_from_pct` rows as gazetted
fact** — they are the best reconstruction available from public sources,
clearly flagged so a reader (or the chatbot) can qualify the answer
accordingly.

## Known gaps / limitations

- **2000–2009**: No PURC gazette PDFs for this period could be found
  online. All 2000s rows are narrative/event-only, sourced from a
  historical-overview passage inside PURC's own 2020 Trends report
  (which in turn cites Edjekumhene et al. 2001 and an ESMAP 2005 paper).
  Numeric GHp/kWh rates for this decade are **not** in the dataset.
- **2006–2009**: Only two dated events are known (Apr 2006 ~+35% major
  review; Nov 2007 an ECG increase of unspecified size). The 2007–2009
  gap is real — PURC's own account jumps from Q2 2006 straight to the
  Nov 2009/2010 proposals.
- **Apr 2024**: PURC published only average percentage changes for
  categories ≥300 kWh/month (Residential −6.56%, Non-Residential −4.98%,
  SLT-LV −4.88%) and that Lifeline was unchanged (0%); the exact new
  per-band GHp/kWh table for this date was not found publicly (source
  PDF is a scanned image).
- **Jul 2024**: figures are derived (see `computed_from_pct` above), not
  gazetted directly.
- **Band structure changes over time**: PURC has restructured the
  residential/SLT bands more than once (e.g. 4 residential bands in 2023
  down to 3 by Oct 2024; SLT-MV and SLT-HV merged into SLT-MV/HV in Apr
  2024; a new SLT-MV2 and, later, EV-charging category introduced). The
  `band` and `customer_category` values reflect whatever structure PURC
  used *at that date* — do not assume a band label means the same
  consumption range across the whole time series.

## Primary sources used

- PURC Research Department, *A Study on the Trends in Electricity Tariffs
  in Ghana Between 2010 and 2020* (Dec 2020)
- PURC Press Release, *2022–2025 Multi-Year Major Tariff Review* (Sep 2022)
- PURC gazettes / quarterly Decision Papers for Feb 2023, Sep 2023 (via
  2024 Q1 decision appendix), Oct 2024, May 2025, Jul 2025, Oct 2025
- PURC, *2026–2030 Electricity, Water and Natural Gas Major Tariff Review
  Decision* (Jan 2026) and *2026 Second Quarter Tariff Review Decision*
  (Mar 2026)
- Graphic Online / GNA / allAfrica / The Fourth Estate news reports, used
  only to fill percentage-change gaps where no PURC PDF was found

Full URLs are in the `source` column of the CSV itself.

## `source_pdfs/`

The actual PURC gazettes and decision papers downloaded and text-extracted
to build this dataset, kept for provenance/verification (e.g. for a
supervisor or examiner to spot-check a figure against the original
document). Includes the 2010-2020 Trends study, the Sep-2022 major review
press release, gazettes/decision papers for Feb 2023, Apr 2024/Sep 2023,
Oct 2024, May 2025, Jul 2025, Oct 2025, and the Jan 2026 MYTO + Apr 2026
decision papers.

## How this feeds the chatbot

`backend/purc_knowledge.txt` (section `historical_tariff_timeline`)
contains a prose summary of this same data for the chatbot's knowledge
base. This CSV is the more granular/queryable version behind that
summary — useful for charts, tables, or any analysis component of the
project.
