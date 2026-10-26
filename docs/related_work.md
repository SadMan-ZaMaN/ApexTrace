# Related work tracker

One entry per paper or project: what they did, on what data, and how ApexTrace
differs. Read papers with Keshav's three-pass method ("How to Read a Paper"):
pass 1 = title, abstract, headings, conclusions (5–10 min); pass 2 = figures and
main argument; pass 3 = the details, only for papers we build on.

✅ = the paper and its citation details were found and checked on the web (date
given) · ⚠️ = something is still unverified (said what). Everything under "What
they did" comes from abstracts and listings until "Read" says otherwise.

| Read? | Meaning |
|---|---|
| — | not read yet |
| P1 / P2 / P3 | read up to pass 1, 2 or 3 |

---

## Search log

| Date | Engine | Keywords | Relevant hits |
|---|---|---|---|
| 2026-10-14 | web | F1 driving style clustering; driver identification telematics; driver vs constructor | 6 (seed list) |
| 2026-10-27 | web | Formula 1 telemetry driving style corner braking throttle | 1 paper (Taylor & Secco), several hobby projects |
| 2026-10-27 | web | driver identification from a single turn | Hallac et al. 2016; Chen et al. 2017 |
| 2026-10-27 | web | Bayesian F1 driver skill vs constructor advantage | van Kesteren & Bergkamp 2023; Lindner et al. 2026; Phillips 2014 |
| 2026-10-27 | web | racing driver identification motorsport telemetry | Löckel 2022; sim-racing studies |
| 2026-10-27 | web | driver fingerprinting CAN bus survey | Kidmose et al. 2025; steering-wheel review 2019; Lestyán et al. 2019 |
| 2026-10-27 | web | professional racing drivers braking telemetry study | Remonda et al. 2021; expert-interview study 2024 |
| 2026-10-27 | web | Eichenberger & Stadelmann; Phillips 2014 (citation checks) | 2 |

**Still to do:** the same keywords on Google Scholar, Semantic Scholar and arXiv
directly (the searches above used a general web search engine), and a forward-citation
check of Hallac et al. 2016 and van Kesteren & Bergkamp 2023 ("who cites them?").

**What the searches have NOT found so far (a gap, not a proof):** a study that
identifies drivers from real Formula 1 telemetry and tests it on held-out sessions;
a study that quantifies the measurement error of corner features at the public
feed's ~3.7 Hz; or a driver-vs-car study at the level of driving *style* (the
driver-vs-car literature models results: points, positions, lap times).

---

## Formula 1 and racing: driving style from telemetry

### Taylor & Secco, 2026 — "Can Unsupervised Learning Methods Reveal Distinct Driving Styles Among Formula 1 Drivers?" ✅ (2026-10-27)
- **Citation:** *International Journal of Modelling and Optimization*, 2026 (accepted
  version). Links: https://ojs.ejournal.net/index.php/ijmo/article/view/22205,
  https://hira.hope.ac.uk/id/eprint/4949/ (the repository copy is embargoed until 2027-06-30).
- **Read:** —
- **What they did:** clustering (K-Means, hierarchical, DBSCAN, Gaussian mixtures) +
  PCA on **race-level** features from the 2023 season (FastF1): lap-time consistency,
  tyre-degradation slope, overtaking efficiency, sector averages. 3–5 clusters; K-Means
  with k = 4 scored best.
- **How we differ:** corner-level signal features, not race summaries; supervised
  identification tested on unseen sessions and an unseen season; measured error bars;
  driver vs car.

### roeeam9/F1-Clustering-Project (GitHub) ✅ (2026-10-14) — the closest project
- **Link:** https://github.com/roeeam9/F1-Clustering-Project
- **Read:** —
- **What they did:** 12 per-corner features (entry/apex/exit speed, braking %,
  trail-braking %, coasting %, throttle after apex, minimum gear, …), z-scored per
  (track, corner); PCA + two-stage K-Means → 3 driving "archetypes".
- **Data:** OpenF1, four 2023 qualifying sessions, the fastest lap per driver only.
- **How we differ:** many laps per driver; measurement error quantified on synthetic
  laps; whole unseen sessions as the test; driver separated from car. Cite and differentiate.

### Löckel, 2022 — "Machine Learning for Modeling and Analyzing of Race Car Drivers" (doctoral thesis, TU Darmstadt) ✅ exists / ⚠️ method details
- **Link:** https://tuprints.ulb.tu-darmstadt.de/20218
- **Read:** —
- **What they did (from a secondary summary, to check in the thesis):** a driver
  identification and metric ranking method on lap-based metrics (feature selection +
  clustering), with transfer from a driving simulator to real-track data.
  Related: an imitation-learning driver model co-authored by Löckel (arXiv 2203.01909,
  IEEE Transactions on Systems, Man and Cybernetics, 2023).
- **How we differ (to confirm):** public broadcast-feed data at ~3.7 Hz instead of
  team-grade logging; teammates in the same car; a preregistered held-out season.

### Remonda, Veas & Luzhnica, 2021 — "Comparing driving behavior of humans and autonomous driving in a professional racing simulator" ✅ (2026-10-27)
- **Citation:** *PLOS ONE* 16(2): e0245320. DOI 10.1371/journal.pone.0245320.
- **Read:** —
- **What they did:** in a professional simulator, grouped human laps by lap time,
  analysed brake, throttle and steering telemetry, and compared them with a
  reinforcement-learning agent.
- **How we differ:** real cars and real races, at a much lower sample rate; we
  measure individual signatures, not skill levels.

### Other racing items found (⚠️ details not yet verified)
- "An AI Approach for Analyzing Driving Behaviour in Simulated Racing Using Telemetry
  Data" (University of Limerick; Assetto Corsa Competizione, 93 participants, MoTeC):
  https://pure.ul.ie/en/publications/an-ai-approach-for-analyzing-driving-behaviour-in-simulated-racin/
- FISITA 2018 paper F2018-VDY-050: supervised identification of a driver from control
  inputs in a race car near its limits: https://go.fisita.com/store/papers/F2018/F2018-VDY-050

### Frontiers in AI, 2025 — deep sequence models on F1 telemetry ✅ found / ⚠️ task unclear
- **Link:** https://doi.org/10.3389/frai.2025.1673148
- **Read:** —
- **What they did:** BiLSTM / GRU / TCN / CNN-BiLSTM on F1 telemetry, 2020–2024.
- **How we differ:** read it first to find out exactly which task they solve. Relevant
  to Phase 9 (DSP features vs a learned model).

---

## Driver identification from vehicle data (road cars): framing for H3

### Hallac et al., 2016 — "Driver Identification Using Automobile Sensor Data from a Single Turn" ✅ (2026-10-27) — the closest framing
- **Citation:** D. Hallac et al. IEEE International Conference on Intelligent
  Transportation Systems (ITSC), 2016. arXiv 1708.04636.
- **Read:** —
- **What they did:** time-series classification of which driver (from a known group)
  drove a single turn, from in-car sensor data of a test fleet (Stanford, Audi,
  Volkswagen ERL), on the 12 most frequent turns. Argues that **turns separate drivers
  better than straights**.
- **How we differ:** the same intuition (corners carry the signature), but racing laps,
  public data at ~3.7 Hz, teammates in identical cars, interpretable features with
  measured errors, and evaluation on unseen sessions and an unseen season.

### Chen, Cho & Shin, 2017 — "Mobile IMUs Reveal Driver's Identity From Vehicle Turns" ✅ (2026-10-27)
- **Citation:** ACM CoNEXT 2017; arXiv 1710.04578.
- **Read:** —
- **What they did:** "Dri-Fi" identifies a driver from phone/wearable motion sensors
  during turns, with three features (acceleration along the end-of-turn axis, its
  deviation, yaw-rate deviation): one turn gave 74.1 %, 83.5 % and 90.8 % accuracy for
  groups of 12, 8 and 5 drivers; several turns up to 95–97 %.
- **How we differ:** our groups are two teammates per car (harder: same car, both elite);
  our features are positions and speeds from the timing feed, not inertial sensors.

### Enev, Takakuwa, Koscher & Kohno, 2016 — "Automobile Driver Fingerprinting" ✅ (2026-10-19)
- **Citation:** *Proceedings on Privacy Enhancing Technologies* 2016(1), 34–51.
  DOI 10.1515/popets-2015-0029. Open access: https://petsymposium.org/popets/2016/popets-2015-0029.php
- **Read:** —
- **What they did:** identified drivers from short snippets of in-car sensor data
  (natural driving); with enough training data, the brake pedal alone was enough for
  high accuracy.
- **How we differ:** racing laps, an on/off brake at ~3.7 Hz, teammates in the same car,
  a held-out season.

### Driver identification on CAN data: reviews and datasets ✅ (2026-10-27)
- "Driver Identification via the Steering Wheel" (arXiv 1909.03953): its related-work
  section counts about 20 CAN-based driver-identification publications since 2005.
- Lestyán et al., 2019, "Extracting vehicle sensor signals from CAN logs for driver
  re-identification" (ICISSP 2019; arXiv 1902.08956): re-identification works even
  from raw CAN logs without decoding the protocol.
- Kidmose et al., 2025, "A Critical Roadmap to Driver Authentication via CAN Bus"
  (arXiv 2510.25856): reviews open datasets and notes that many use decoded diagnostic
  data, artificial routes or **low sampling rates**; introduces a 16-driver raw CAN dataset.
- arXiv 1911.08030 (✅ 2026-10-14): LSTM driver identification on road-car telematics.
- **Read:** —
- **How we differ:** the low-sample-rate problem is our main subject: we measure what
  it does to each feature instead of treating it as a limitation.

---

## Driver vs car: framing for H4

### Eichenberger & Stadelmann, 2009 — "Who is the best Formula 1 driver? An economic approach to evaluating talent" ✅ (2026-10-27)
- **Citation:** *Economic Analysis & Policy* 39(3), 389–406. DOI 10.1016/S0313-5926(09)50035-5.
- **Read:** —
- **What they did:** econometric separation of driver talent from car quality on 57
  years of results, accounting for finishing rates and breakdowns.

### Phillips, 2014 — "Uncovering Formula One driver performances from 1950 to 2013 by adjusting for team and competition effects" ⚠️ (citation from other papers' references)
- **Citation (to check on the publisher page):** *Journal of Quantitative Analysis in
  Sports* 10(2), 261–278.
- **What they did (secondary):** estimated driver, constructor and season effects on an
  adjusted points outcome. Identification of driver vs car rests on two facts: two cars
  per team (teammate comparison) and drivers switching teams, the same two facts our
  H3 and H4 use.

### Bell, Smith, Sabel & Jones, 2016 — "Formula for success" ✅ (2026-10-19)
- **Citation:** *Journal of Quantitative Analysis in Sports* 12(2), 99–112.
  DOI 10.1515/jqas-2015-0050.
- **Read:** —
- **What they did:** a cross-classified multilevel model of race points (1950–2014):
  team effects matter more than driver effects, increasingly so over time.

### van Kesteren & Bergkamp, 2023 — "Bayesian analysis of Formula One race results: disentangling driver skill and constructor advantage" ✅ (2026-10-27)
- **Citation:** *Journal of Quantitative Analysis in Sports* 19(4), 273–293; arXiv 2203.08489.
  Open access: https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10660124/
- **Read:** —
- **What they did:** a Bayesian multilevel rank-ordered logit model of finishing
  positions in the hybrid era (2014–2021); about 88 % of the variance in race results
  is explained by the constructor.

### Lindner, Almeida, Baştürk & Smeekes, 2026 — "Drivers of Success: A Bayesian State-Space Model to Disentangling Latent Driver and Constructor Abilities in Formula One" ✅ (2026-10-27, abstract and listing)
- **Citation:** arXiv 2608.04629 (2026).
- **Read:** —
- **What they did:** latent driver and constructor abilities that change at every
  Grand Prix, estimated from **qualifying lap times** and race rankings (2014–2021);
  driver abilities are more stable over time, constructor abilities vary more.
- **How we differ (for this whole section):** these studies separate driver and car
  in **results** (points, positions, lap times). We ask the same question of driving
  **style** (where and how a driver brakes and accelerates), using teammates and team
  changers. Our H4 result (not supported, 2 of 5 changers) is consistent with a strong
  car effect, but five changers are too few to show it; the 2026 test (Part C) adds more.
