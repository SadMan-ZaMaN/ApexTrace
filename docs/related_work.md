# Related work tracker

One entry per paper or project: what they did, on what data, and how ApexTrace
differs. Read papers with Keshav's three-pass method ("How to Read a Paper"):
pass 1 = title, abstract, headings, conclusions (5–10 min); pass 2 = figures and
main argument; pass 3 = the details, only for papers we build on.

Seeded on 2026-10-14 from PROJECT_CONTEXT §12.2. ✅ = found and checked on the
web on 2026-10-14 · ⚠️ = not yet verified.

| Read? | Meaning |
|---|---|
| — | not read yet |
| P1 / P2 / P3 | read up to pass 1, 2 or 3 |

---

## F1 driving style and telemetry

### IJMO 2026 — "Can Unsupervised Learning Methods Reveal Distinct Driving Styles Among Formula 1 Drivers?" ✅
- **Link:** https://ojs.ejournal.net/index.php/ijmo/article/view/22205
- **Read:** —
- **What they did:** clustering (K-Means, hierarchical, DBSCAN, GMM) + PCA on
  **race-level** features: relative lap time, lap-time consistency (MAD),
  tyre-degradation slope, overtaking efficiency, sector averages. Finds 3–5
  clusters.
- **Data:** FastF1.
- **How we differ:** corner-level signal features (not race summaries);
  supervised identification on held-out sessions; measurement uncertainty;
  driver vs car.

### roeeam9/F1-Clustering-Project (GitHub) ✅ — closest to us
- **Link:** https://github.com/roeeam9/F1-Clustering-Project
- **Read:** —
- **What they did:** 12 per-corner features (entry/apex/exit speed, braking %,
  trail-braking %, coasting %, throttle after apex, min gear, …), z-scored per
  (track, corner); PCA + two-stage K-Means → 3 driving "archetypes".
- **Data:** OpenF1, four 2023 qualifying sessions (Monza, Spa, Singapore,
  Suzuka), **fastest lap per driver only**.
- **How we differ:** no held-out evaluation, no supervised identification, no
  team-change analysis, no measurement-uncertainty analysis there. We use many
  laps per driver, quantify measurement error on synthetic laps, test on whole
  unseen sessions, and separate driver from car. Cite it and differentiate.

### Frontiers in AI, 2025 — deep sequence models on F1 telemetry ✅ (found) / ⚠️ (task unclear)
- **Link:** https://doi.org/10.3389/frai.2025.1673148
- **Read:** —
- **What they did:** BiLSTM / GRU / TCN / CNN-BiLSTM on F1 telemetry, 2020–2024.
- **Data:** F1 telemetry 2020–2024 (source to check).
- **How we differ:** ⚠️ read it to find out exactly what task they solve before
  claiming a difference. Relevant to Phase 9 (DSP features vs learned models).

---

## Driver identification from vehicle data (road cars) — framing for H3

### arXiv 1911.08030 — LSTM driver identification on telematics ✅
- **Link:** https://arxiv.org/abs/1911.08030
- **Read:** —
- **What they did:** LSTM on road-car telematics to identify the driver.
- **How we differ:** racing telemetry at ~3.7 Hz, interpretable DSP features,
  leave-one-session-out evaluation, and the driver-vs-car question.

### Enev et al., 2016 — "Automobile Driver Fingerprinting" (PoPETs) ⚠️
- **Read:** —
- **Note:** verify the citation. Classic reference that drivers can be told
  apart from in-car sensor data.

---

## Driver vs car — framing for H4

### Bell et al., 2016 — multilevel model of F1 driver vs constructor performance ⚠️
- **Venue:** Journal of Quantitative Analysis in Sports (verify).
- **Read:** —
- **What they did:** separated driver and constructor effects on F1 **results**
  with a multilevel (mixed) model.
- **How we differ:** apply the same idea to corner-level **style** features,
  using drivers who changed teams.

---

## Searches still to do (before claiming anything is new, especially C4)

Google Scholar, Semantic Scholar and arXiv, with these keywords:
- "Formula 1 telemetry driving style"
- "driver identification telemetry"
- "racing driver behaviour"
- "driver fingerprinting vehicle data"
- "driver constructor multilevel"

Log each search here: date, engine, keywords, number of relevant hits.
