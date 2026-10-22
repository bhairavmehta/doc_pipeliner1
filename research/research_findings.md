# Research Findings – Taxonomy Discovery Pipeline (US 311617)

Summary of the external research used to refine the requirements document (October 2026).
Produced with Prompt 3 (`prompts/03_deep_research.md`). Public sources only.

## 1. ICAO / CICTT taxonomy status
- The current CICTT Aviation Occurrence Categories document is **v4.8 (May 2021)**. Its only change from v4.7 (Dec 2017) is a revised UIMC usage note. The list still has **36 codes**.
- ICAO Safety Reports 2025 and 2026 cite "CICTT Aviation Occurrence Categories (May 2021)". **Confirm the official CICTT PDF by hand**; the CICTT site could not be checked directly.
- CICTT is **multi-label**: an engine failure followed by loss of control is coded as both. OTHR should not be combined with other categories, UNK is used alone (except with F-POST), and F-POST is always paired with another category.
- An occurrence category describes **what happened, not the cause**.
- ADREP (ICAO) is maintained by the ECCAIRS Taxonomy Working Group. ECCAIRS 2 implements it, and EASA publishes version-to-version diff packages.
- **ICAO GASP 2026–2028 (Doc 10004)**: the 5 global high-risk categories are CFIT, LOC-I, MAC, RE and RI. The "other global risk categories" are ARC, SCF-NP and TURB.
- TURB had the most accidents in the ICAO Safety Reports for 2022 and 2023.
- The Boeing Statistical Summary uses CICTT categories assigned by CAST. CAST safety enhancements are tagged by CICTT code.

## 2. Taxonomies: primary tree vs. facets
| Taxonomy | Role |
|---|---|
| CICTT Occurrence Categories v4.8 | Level 1 (primary) |
| CICTT Phase of Flight v1.3 | Facet |
| ECCAIRS/ADREP events | Crosswalk for Level 2+ wording |
| ATA iSpec 2200 chapters | Facet for SCF-NP / SCF-PP (paid licence) |
| HFACS | Facet for contributing factors |
| EASA ERCS Key Risk Areas | Facet for severity |
| NASA ASRS anomaly codes | Crosswalk / weak labels |
| IATA IDX | Optional (contributor-only) |

## 3. Public data sources
| Source | Access | Watch for |
|---|---|---|
| NTSB CAROL / avall | Free; monthly + weekly updates; from 1962 | Long narratives; accidents + some incidents |
| NASA ASRS | Free; 10,000 records per export; monthly | Voluntary; counts are a lower bound, not prevalence; overlaps with ASAP |
| FAA AIDS | Bulk via ASIAS; incidents since 1978 | Incidents only; short narratives |
| FAA SDRS | Web database | Maintenance defects; known quality gaps |
| TSB Canada | Monthly CSV from 1995 | Some fields withheld; French text |
| ATSB | Dashboard; 200-row cap | Bulk needs a data request |

## 4. Automated taxonomy discovery (state of the art)
- **TnT-LLM (Microsoft, KDD 2024):** LLM builds and refines a taxonomy over batches, includes an "Other" class, then trains small classifiers for scale.
- **Clio (Anthropic, 2024):** extract facets → embed → cluster → LLM names clusters → hierarchy. Uses a minimum cluster size.
- **TopicGPT:** grows the taxonomy one text at a time; stops when about 200 texts add no new topic (saturation rule).
- **Hybrid top-down + bottom-up** methods beat either alone; bottom-up only struggles to form high-level categories.
- **Aviation:** SafeAeroBERT (NASA, trained on NTSB + ASRS) is a strong embedding baseline. BERTopic beat pLSA on NTSB reports (UNSW study), and cluster size drives fragmentation vs. merging. In an ADREP-coded airline dataset, 95% of occurrences had one category, 4% two and 1% more.
- **Reproducibility:** LLM label agreement between runs was 91% (temperature 1.0) and 97% (0.2), so cache model responses.
- **Agreement metrics:** report Cohen's kappa alongside raw agreement, and compare with a human-human baseline.

## 5. Build strategy (Cedar's question)
- A pure "most likely path first" approach is a poor fit: multi-label reports have no single path, and it cannot find categories outside the chosen path.
- **Recommended:** fixed Level 1 → Level 2 for every branch → depth by GASP tier with a saturation stop → residual sweep of OTHR/UNK to find emerging issues (e.g., GNSS interference).

## 6. Governance and AI assurance
- Copy the CICTT change-log format (date, version, section, change, migration notes) and ECCAIRS-style machine-readable diffs.
- A change to an external anchor (CICTT/ECCAIRS) should trigger at least a minor version and re-checking of the crosswalks.
- EASA AI Concept Paper Issue 02 (2024): Level 1 "human assistance", learning assurance and explainability. Proposed Issue 03 was consulted on until August 12, 2026 and is not final. Not binding for offline analytics, but worth mirroring.

## Caveats
- v4.8 status rests on ICAO Safety Report citations; confirm the official PDF.
- LLM/topic-model accuracy figures come from small academic studies and are indicative only.
- Use CICTT source text, not training material, for criteria cards.

## Key sources
- ICAO Safety Report 2026: https://www.icao.int/sites/default/files/sp-files/safety/Documents/ICAO_SR_2026.pdf
- ICAO Safety Report 2025: https://www.icao.int/sites/default/files/sp-files/safety/Documents/ICAO_SR_2025.pdf
- ICAO GASP 2026–2028 (Doc 10004): https://www.icao.int/sites/default/files/safety/GASP/Documents/Doc.10004.2026-2028.GASP_.EN_.pdf
- CICTT Occurrence Categories v4.7 (ICAO copy): https://www.icao.int/sites/default/files/APAC/Meetings/2024/2024%20NASP%20Workshop/Supporting%20Documents/CAST-ICAO-Taxonomy-Occurrences.pdf
- CICTT Phase of Flight (NTSB copy): https://www.ntsb.gov/safety/data/Documents/datafiles/PhaseofFlightDefinitions.pdf
- ECCAIRS taxonomy browser: https://aviationreporting.eu/en/taxonomy-browser
- ICAO ADREP taxonomy: https://www.icao.int/safety/AIG/taxonomy
- Boeing Statistical Summary: https://www.boeing.com/content/dam/boeing/v2/safety/statsum.pdf
- NASA ASRS database notes: https://asrs.arc.nasa.gov/search/dbol/aboutdata.html
- NTSB CAROL: https://www.ntsb.gov/Pages/CAROL.aspx
- FAA ASIAS AIDS: https://asip.faa.gov/explore/ntsb/info
- GAO on SDRS data quality: https://www.gao.gov/products/rced-91-24
- TSB Canada data: https://www.tsb.gc.ca/eng/stats/aviation/data-5.html
- ATSB database: https://www.atsb.gov.au/national-aviation-occurrence-database
- TnT-LLM (KDD 2024): https://dl.acm.org/doi/pdf/10.1145/3637528.3671647
- Clio (Anthropic): https://arxiv.org/pdf/2412.13678
- SafeAeroBERT (NASA): https://ntrs.nasa.gov/citations/20240003131
- BERTopic on NTSB reports (MDPI Aerospace): https://www.mdpi.com/2226-4310/12/6/551
- ICAO MID ASRG/8 report (GNSS interference): https://www.icao.int/sites/default/files/MID/MeetingDocs/2026/ASRG%208%20/Final-Report.pdf
