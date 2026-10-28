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
| 2026-10-28 | Semantic Scholar API | Formula 1 telemetry; Formula One driver identification; racing driver telemetry driving style | 75 records; new: Vogel et al. 2022, Tahmasbi et al. 2018, Govers et al. 2024, Lucaciu & Győrödi 2026 (review) |
| 2026-10-28 | OpenAlex API | motorsport telemetry driver; Formula One driver constructor performance; racing driver identification | 75 records; new: Xun 2024 (Elo), Fry et al. 2024, Peitzmeier et al. 2022, Avignone et al. 2025 |
| 2026-10-28 | OpenAlex API | **who cites** Hallac et al. 2016 (126 works) and van Kesteren & Bergkamp 2023 (3 works) | none of the 126 applies turn-based identification to racing; 1 F1 paper among the 3 (results metrics) |

**Done on 2026-10-28:** academic-index searches (Semantic Scholar; OpenAlex when
Semantic Scholar's free tier refused more requests) and the forward-citation check.
**Still to do:** Google Scholar by hand (no API), and pass 2 (figures, main argument) of
the five closest papers: Hallac 2016, Chen 2017, Taylor & Secco 2026, Lindner 2026,
roeeam9.

**What the searches have NOT found so far (a gap, not a proof; checked again on 2026-10-28 in two
academic indexes and in the 126 papers that cite Hallac et al. 2016):** a study that
identifies drivers from real Formula 1 telemetry and tests it on held-out sessions;
a study that quantifies the measurement error of corner features at the public
feed's ~3.7 Hz; or a driver-vs-car study at the level of driving *style* (the
driver-vs-car literature models results: points, positions, lap times).

---

## Formula 1 and racing: driving style from telemetry

### Taylor & Secco, 2026 — "Can Unsupervised Learning Methods Reveal Distinct Driving Styles Among Formula 1 Drivers?" ✅ (2026-10-27)
- **Citation:** A. J. W. Taylor, E. Secco. *International Journal of Modeling and
  Optimization* 16 (2026). DOI 10.7763/IJMO.2026.V16.881. Links: https://ojs.ejournal.net/index.php/ijmo/article/view/22205,
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

### Vogel, Schmidsberger, Kühn et al., 2022 — "You can't drive my car: a method to fingerprint individual driving styles in a sim-racing setting" ✅ (listing, 2026-10-28)
- **Citation:** ICECET 2022. DOI 10.1109/ICECET55527.2022.9872663 (the Hochschule
  Mittweida item found on 2026-10-27).
- **Read:** —
- **How we differ:** simulator logging vs the public feed of real races.

### Lucaciu & Győrödi, 2026 — "Artificial Intelligence in Motorsport: A Scoping Review of Applications, Challenges, and Research Gaps" ✅ (2026-10-28)
- **Citation:** *International Journal of Advanced Computer Science and Applications*
  17(5), 2026. DOI 10.14569/ijacsa.2026.01705101.
- **Read:** P1 (abstract)
- **What they found:** six domains (vehicle tuning, race strategy, autonomous racing,
  telemetry and race data analysis, driver coaching and simulation, predictive
  maintenance); strategy and vehicle optimisation "relatively well-covered",
  predictive maintenance and computer vision "largely unexplored". The abstract does
  not mention driver identification or driving style. **Read the full review (pass 2)
  before any novelty claim**: it is the best single check of the gap.

### More racing items found on 2026-10-28 (listings only)
- Peitzmeier, Mockenhaupt, Reith et al., 2022, "Optimum Real Time Estimation and
  Interfacing of Braking Points for Racing Car", *IEEE Transactions on Vehicular
  Technology*, DOI 10.1109/TVT.2022.3211840: braking points, from the control side.
- Avignone, Chiusano, Peroni, 2025, "Mine4Race: A user-friendly toolset for enhancing
  racing telemetry analysis and visualization", *Results in Engineering*,
  DOI 10.1016/j.rineng.2025.108865.
- Gabiccini, Bartali, Guiggiani et al., 2021, "Analysis of driving styles of a GP2 car via
  minimum lap-time direct trajectory optimization", *Multibody System Dynamics*,
  DOI 10.1007/s11044-021-09789-7: "driving style" from optimal control, not from data.
- Bugeja, Spina, Buhagiar et al., 2017, "Telemetry-based optimisation for user training in
  racing simulators", VS-Games 2017, DOI 10.1109/VS-GAMES.2017.8055808.

### Other racing items found (⚠️ details not yet verified)
- "An AI Approach for Analyzing Driving Behaviour in Simulated Racing Using Telemetry
  Data" (University of Limerick; Assetto Corsa Competizione, 93 participants, MoTeC):
  https://pure.ul.ie/en/publications/an-ai-approach-for-analyzing-driving-behaviour-in-simulated-racin/
- FISITA 2018 paper F2018-VDY-050: supervised identification of a driver from control
  inputs in a race car near its limits: https://go.fisita.com/store/papers/F2018/F2018-VDY-050

### Sasikumar, Leema & Balakrishnan, 2025 — "Data-driven pit stop decision support for Formula 1 using deep learning models" ✅ (2026-10-28)
- **Citation:** *Frontiers in Artificial Intelligence* 8 (2025). DOI 10.3389/frai.2025.1673148.
- **Read:** P1
- **What they did:** predicts whether a lap ends in a pit stop (binary label) from
  FastF1 data 2020–2024 (~100,000 laps), with Bi-LSTM, TCN-GRU, GRU, InceptionTime and
  CNN-BiLSTM; the test set is the last eight races of 2024 (held out by race). Bi-LSTM
  best (F1-score 0.81).
- **How we differ:** a different task (strategy, not driving style). Useful for Phase 9
  as an example of deep learning on FastF1 data with a race-held-out test.

---

## Driver identification from vehicle data (road cars): framing for H3

### Hallac et al., 2016 — "Driver Identification Using Automobile Sensor Data from a Single Turn" ✅ (2026-10-28) — the closest framing
- **Citation:** D. Hallac, A. Sharang, R. Stahlmann, A. Lamprecht, M. Huber, M. Roehder,
  R. Sosič, J. Leskovec. *2016 IEEE 19th International Conference on Intelligent
  Transportation Systems (ITSC)*, 953–958. DOI 10.1109/ITSC.2016.7795670. arXiv 1708.04636.
- **Read:** P1 (abstract; it gives no accuracy numbers, so pass 2 is needed for them)
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
- Girma, Yan & Homaifar, 2019, "Driver Identification Based on Vehicle Telematics Data
  using LSTM-Recurrent Neural Network" (IEEE ICTAI 2019; arXiv 1911.08030; ✅ P1
  2026-10-28): three naturalistic driving datasets; robust to noisy data; the abstract
  gives no numbers.
- Govers et al., 2024, "Time-Shifted Transformers for Driver Identification Using
  Vehicle Data", *IEEE Transactions on Intelligent Transportation Systems*,
  DOI 10.1109/TITS.2023.3326652 (✅ listing, 2026-10-28).
- Tahmasbi, Wang, Chen et al., 2018, "Your Phone Tells Us The Truth: Driver Identification
  Using Smartphone on One Turn", ACM MobiCom 2018, DOI 10.1145/3241539.3267769 (✅ listing).
- **Read:** —
- **How we differ:** the low-sample-rate problem is our main subject: we measure what
  it does to each feature instead of treating it as a limitation.

---

## Driver vs car: framing for H4

### More driver-vs-car items found on 2026-10-28 (listings only)
- Xun, 2024, "From Pole to Podium: Adjusting Elo Method to Separate Car and Driver in
  Formula One Racing", *SIAM Undergraduate Research Online*, DOI 10.1137/22S1522899.
- Fry, Brighton, Fanzon et al., 2024, "Faster identification of faster Formula 1 drivers
  via time-rank duality", *Economics Letters*, DOI 10.1016/j.econlet.2024.111671.
- Almarri et al., 2026, "Formula 1 Race Performance Study: A Comparative Analysis of Driver
  and Constructor Metrics", IEEE SMIRC 2026, DOI 10.1109/SMIRC70459.2026.11706677 (cites
  van Kesteren & Bergkamp; results metrics).

### Eichenberger & Stadelmann, 2009 — "Who is the best Formula 1 driver? An economic approach to evaluating talent" ✅ (2026-10-27)
- **Citation:** *Economic Analysis & Policy* 39(3), 389–406. DOI 10.1016/S0313-5926(09)50035-5.
- **Read:** —
- **What they did:** econometric separation of driver talent from car quality on 57
  years of results, accounting for finishing rates and breakdowns.

### Phillips, 2014 — "Uncovering Formula One driver performances from 1950 to 2013 by adjusting for team and competition effects" ✅ citation (2026-10-28)
- **Citation:** A. J. Phillips. *Journal of Quantitative Analysis in Sports* 10(2),
  261–278 (2014). DOI 10.1515/jqas-2013-0031 (the DOI resolves to the journal; the same
  record in Semantic Scholar; the publisher page refuses automated reading, so the
  abstract itself is not read yet).
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
- **Citation:** *Journal of Quantitative Analysis in Sports* 19(4), 273–293;
  DOI 10.1515/jqas-2022-0021; arXiv 2203.08489.
  Open access: https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10660124/
- **Read:** —
- **What they did:** a Bayesian multilevel rank-ordered logit model of finishing
  positions in the hybrid era (2014–2021); about 88 % of the variance in race results
  is explained by the constructor.

### Lindner, Almeida, Baştürk & Smeekes, 2026 — "Drivers of Success: A Bayesian State-Space Model to Disentangling Latent Driver and Constructor Abilities in Formula One" ✅ (2026-10-27, abstract and listing)
- **Citation:** arXiv 2608.04629 (submitted 5 August 2026).
- **Read:** P1 (abstract)
- **What they did:** latent driver and constructor abilities that change at every
  Grand Prix, estimated from **qualifying lap times** and race rankings (2014–2021);
  driver abilities are more stable over time, constructor abilities vary more.
- **How we differ (for this whole section):** these studies separate driver and car
  in **results** (points, positions, lap times). We ask the same question of driving
  **style** (where and how a driver brakes and accelerates), using teammates and team
  changers. Our H4 result (not supported, 2 of 5 changers) is consistent with a strong
  car effect, but five changers are too few to show it; the 2026 test (Part C) adds more.
