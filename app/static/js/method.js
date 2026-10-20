/* Method page: the measurement science (Phases 1-3) as live charts.
 *
 * Data: /api/method, written by experiments/16_app_data.py from the Phase 1-3
 * results files and the project's own functions (nothing is computed here
 * except unit conversions such as speed x interval = metres between samples).
 *
 * Colours: blue = the method the pipeline uses / normal samples, orange = what it
 * replaced or a feed dropout, grey = the truth or a baseline. Shapes and labels
 * always say the same thing as the colour.
 */
(() => {
  const C = { blue: "#3987e5", orange: "#d95926", grey: "#85847e", ink: "#f2f1ed", bg: "#0b0c0e", hair: "#2f3138" };
  const byId = (id) => document.getElementById(id);
  const tooltip = AT.el("div", { class: "tooltip", hidden: true });
  document.body.append(tooltip);
  let data = null;
  const state = { filter: "moving average 5, causal", cornerType: "heavy_braking" };

  // ---------------------------------------------------------------- small helpers

  function showTooltip(event, head, rows) {
    tooltip.replaceChildren(AT.el("div", { class: "tt-head" }, head),
      AT.el("table", {}, ...rows.map(([k, v]) => AT.el("tr", {}, AT.el("td", { class: "k" }, k), AT.el("td", { class: "v num" }, v)))));
    tooltip.hidden = false;
    const left = event.pageX + 14;
    tooltip.style.left = `${left + 260 > window.innerWidth ? event.pageX - 270 : left}px`;
    tooltip.style.top = `${event.pageY - 12}px`;
  }
  const hideTooltip = () => { tooltip.hidden = true; };

  function tile(label, value, sub) {
    return AT.el("div", { class: "tile" }, AT.el("div", { class: "tile-label" }, label),
      AT.el("div", { class: "tile-value" }, value), sub ? AT.el("div", { class: "tile-sub" }, sub) : null);
  }

  /** An SVG with a plot area, gridlines and axes. Returns {svg, x, y, plot}. */
  function frame(box, { width, height, x, y, xLabel, yLabel, xTicks = 6, yTicks = 5, xFormat = null, yFormat = null,
    margin = { left: 54, right: 16, top: 14, bottom: 44 } }) {
    const svg = d3.select(box).append("svg").attr("width", width).attr("height", height);
    x.range([margin.left, width - margin.right]);
    y.range([height - margin.bottom, margin.top]);
    svg.append("g").attr("class", "gridline").attr("transform", `translate(${margin.left},0)`)
      .call(d3.axisLeft(y).ticks(yTicks).tickSize(-(width - margin.left - margin.right)).tickFormat(""));
    svg.append("g").attr("class", "axis").attr("transform", `translate(0,${height - margin.bottom})`)
      .call(d3.axisBottom(x).ticks(xTicks).tickSizeOuter(0).tickFormat(xFormat));
    svg.append("g").attr("class", "axis").attr("transform", `translate(${margin.left},0)`)
      .call(d3.axisLeft(y).ticks(yTicks).tickSizeOuter(0).tickFormat(yFormat)).select(".domain").remove();
    svg.append("text").attr("class", "corner-tag").attr("x", width - margin.right).attr("y", height - 8)
      .attr("text-anchor", "end").text(xLabel);
    svg.append("text").attr("class", "corner-tag").attr("transform", `translate(12,${margin.top}) rotate(-90)`)
      .attr("text-anchor", "end").text(yLabel);
    const clipId = `clip-${box.id}`;
    svg.append("clipPath").attr("id", clipId).append("rect").attr("x", margin.left).attr("y", margin.top)
      .attr("width", width - margin.left - margin.right).attr("height", height - margin.top - margin.bottom);
    const plot = svg.append("g").attr("clip-path", `url(#${clipId})`);
    return { svg, x, y, plot, margin };
  }

  function legend(box, entries) {
    box.append(AT.el("div", { class: "chart-legend" }, ...entries.map(([label, draw]) => {
      const key = AT.el("span", { class: "key" });
      draw(d3.select(key).append("svg").attr("width", 22).attr("height", 12));
      key.append(label);
      return key;
    })));
  }
  const lineMark = (colour, width = 2) => (s) => s.append("line").attr("x1", 1).attr("x2", 21).attr("y1", 6).attr("y2", 6)
    .attr("stroke", colour).attr("stroke-width", width);
  const dotMark = (colour, hollow = false) => (s) => s.append("circle").attr("cx", 11).attr("cy", 6).attr("r", 4)
    .attr("fill", hollow ? C.bg : colour).attr("stroke", hollow ? colour : C.bg).attr("stroke-width", 2);
  const boxMark = (colour) => (s) => s.append("rect").attr("x", 4).attr("y", 1).attr("width", 14).attr("height", 10).attr("fill", colour);
  const fmt = (v, d = 1) => v.toFixed(d).replace("-", "−");

  // ---------------------------------------------------------------- 1. sampling

  function renderSampling() {
    const s = data.sampling;
    byId("sampling-tiles").replaceChildren(
      tile("Samples per second", s.rate_hz.toFixed(2), "on average"),
      tile("Typical interval", `${s.median_s.toFixed(2)} s`, `median; 95 % are under ${s.p95_s.toFixed(2)} s`),
      tile("Nyquist frequency", `${(s.rate_hz / 2).toFixed(2)} Hz`, "half the sample rate: the fastest change that can be seen"),
      tile("Longest dropout", `${s.max_s.toFixed(2)} s`, `${s.gaps} intervals longer than ${s.normal_max_s.toFixed(2)} s`));
    byId("max-gap").textContent = s.max_s.toFixed(2);

    const box = byId("sampling-chart");
    box.replaceChildren();
    legend(box, [["normal interval (40 ms steps)", boxMark(C.blue)], [`feed dropout (> ${s.normal_max_s.toFixed(2)} s)`, boxMark(C.orange)]]);
    const total = d3.sum(s.bins, (b) => b.count);
    const f = frame(box, { width: box.clientWidth, height: 300, x: d3.scaleLinear().domain([0, 1.45]),
      y: d3.scaleLinear().domain([0, d3.max(s.bins, (b) => b.count) * 1.08]), xLabel: "SECONDS BETWEEN TWO CAR SAMPLES",
      yLabel: "HOW MANY", xTicks: 8, yFormat: d3.format(",") });
    const barWidth = Math.max(2, f.x(0.02) - f.x(0) - 2);
    for (const bin of s.bins) {
      const dropout = bin.interval_s > s.normal_max_s;
      const top = Math.min(f.y(bin.count), f.y(0) - 3);            // a tiny bar still shows (min 3 px)
      f.plot.append("rect").attr("x", f.x(bin.interval_s) - barWidth / 2).attr("width", barWidth)
        .attr("y", top).attr("height", f.y(0) - top).attr("fill", dropout ? C.orange : C.blue)
        .on("pointermove", (event) => showTooltip(event, `${bin.interval_s.toFixed(2)} s between samples`, [
          ["Intervals", d3.format(",")(bin.count)], ["Share", `${(bin.count / total * 100).toFixed(1)} %`]]))
        .on("pointerleave", hideTooltip);
    }
    for (const [value, label] of [[s.median_s, "MEDIAN"], [s.p95_s, "95 %"]]) {
      f.plot.append("line").attr("x1", f.x(value)).attr("x2", f.x(value)).attr("y1", f.y.range()[1]).attr("y2", f.y(0))
        .attr("stroke", C.ink).attr("stroke-width", 1).attr("stroke-opacity", 0.5);
      f.svg.append("text").attr("class", "corner-tag").attr("x", f.x(value) + 4).attr("y", 26).text(label);
    }
    renderSpeed();
  }

  function renderSpeed() {
    const s = data.sampling;
    const kmh = Number(byId("speed-slider").value);
    const ms = kmh / 3.6;
    byId("speed-value").textContent = String(kmh);
    byId("speed-text").textContent = `At ${kmh} km/h (${ms.toFixed(0)} m/s) the car travels ${(ms * s.median_s).toFixed(0)} m `
      + `between two typical samples, ${(ms * s.p95_s).toFixed(0)} m at the 95th percentile, and ${(ms * s.max_s).toFixed(0)} m `
      + "across the longest dropout. A braking point has to be found somewhere inside those gaps.";
  }

  // ---------------------------------------------------------------- 2. filters

  const FILTER_LABELS = {
    "no filter": "No filter", "moving average 5, causal": "Moving average", "EMA alpha 0.5, causal": "EMA",
    "Butterworth 0.5 Hz, causal": "Butterworth", "moving average 5, zero-phase": "MA zero-phase",
    "Butterworth 0.5 Hz, zero-phase": "Butterworth zero-phase",
  };

  function renderFilterButtons() {
    byId("filter-buttons").replaceChildren(...data.filters.filters.map((f) => {
      const button = AT.el("button", { type: "button", "aria-pressed": String(f.name === state.filter) }, FILTER_LABELS[f.name]);
      button.addEventListener("click", () => { state.filter = f.name; renderFilterButtons(); renderFilter(); });
      return button;
    }));
  }

  function renderFilter() {
    const demo = data.filters;
    const chosen = demo.filters.find((f) => f.name === state.filter);
    const box = byId("filter-chart");
    box.replaceChildren();
    legend(box, [["truth (simulated corner)", lineMark(C.grey, 3)], ["feed samples", dotMark(C.ink)],
      [`after: ${state.filter}`, lineMark(C.blue)]]);
    const speeds = [...demo.truth.speed, ...demo.samples.speed];
    const f = frame(box, { width: box.clientWidth, height: 340, x: d3.scaleLinear().domain([-2, 3.5]),
      y: d3.scaleLinear().domain([d3.min(speeds) - 10, d3.max(speeds) + 10]).nice(),
      xLabel: "SECONDS FROM THE TRUE START OF BRAKING", yLabel: "SPEED, KM/H", xFormat: (d) => (d > 0 ? `+${d}` : d) });
    const line = (ts, vs) => d3.line().x((d, i) => f.x(ts[i])).y((d) => f.y(d))(vs);
    f.plot.append("line").attr("x1", f.x(-2)).attr("x2", f.x(3.5)).attr("y1", f.y(demo.level_kmh)).attr("y2", f.y(demo.level_kmh))
      .attr("stroke", C.hair);
    f.svg.append("text").attr("class", "corner-tag").attr("x", f.x(3.45)).attr("y", f.y(demo.level_kmh) - 6).attr("text-anchor", "end")
      .text("HALFWAY DOWN THE BRAKING");
    f.plot.append("path").attr("d", line(demo.truth.t, demo.truth.speed)).attr("fill", "none").attr("stroke", C.grey).attr("stroke-width", 3);
    f.plot.append("path").attr("d", line(chosen.t, chosen.speed)).attr("fill", "none").attr("stroke", C.blue).attr("stroke-width", 2);
    f.plot.append("g").selectAll("circle").data(demo.samples.t.map((t, i) => [t, demo.samples.speed[i]])).join("circle")
      .attr("cx", (d) => f.x(d[0])).attr("cy", (d) => f.y(d[1])).attr("r", 3).attr("fill", C.ink).attr("stroke", C.bg).attr("stroke-width", 1.2);
    // where each crosses the halfway level: the truth, and after the filter
    const y0 = f.y(demo.level_kmh);
    f.plot.append("circle").attr("cx", f.x(demo.true_mid_t)).attr("cy", y0).attr("r", 5).attr("fill", C.grey);
    f.plot.append("circle").attr("cx", f.x(chosen.mid_t)).attr("cy", y0).attr("r", 5).attr("fill", C.blue);
    if (Math.abs(chosen.mid_t - demo.true_mid_t) > 0.04) {
      f.plot.append("line").attr("x1", f.x(demo.true_mid_t)).attr("x2", f.x(chosen.mid_t)).attr("y1", y0 + 16).attr("y2", y0 + 16)
        .attr("stroke", C.ink).attr("stroke-width", 1.5);
      f.svg.append("text").attr("class", "point-label").attr("x", (f.x(demo.true_mid_t) + f.x(chosen.mid_t)) / 2).attr("y", y0 + 30)
        .attr("text-anchor", "middle").text(`${chosen.mid_shift_m_this_corner > 0 ? "+" : ""}${fmt(chosen.mid_shift_m_this_corner)} m`);
    }

    const shift = chosen.mean_shift_m;
    const causal = state.filter.includes("causal");
    byId("filter-text").textContent = state.filter === "no filter"
      ? "Without a filter the feed samples (white dots) follow the truth; only the sampling and rounding add error."
      : causal
        ? `A causal filter only uses past samples, so its output lags behind the truth: here the middle of the braking `
          + `zone appears ${fmt(chosen.mid_shift_m_this_corner)} m later than it really was. That is group delay, the same `
          + "property you would compute from the filter's phase response."
        : "A zero-phase filter runs forwards and then backwards over the data (filtfilt), so the two delays cancel: the middle "
          + `of the braking zone hardly moves (${fmt(chosen.mid_shift_m_this_corner)} m here). But it smears the sharp start of `
          + `braking, which then appears ${fmt(Math.abs(shift.onset_mean_shift_m))} m too early on average.`;
    const rows = demo.filters.map((f) => AT.el("tr", { class: f.name === state.filter ? "on" : "" },
      AT.el("td", {}, FILTER_LABELS[f.name]),
      AT.el("td", { class: "num" }, `${fmt(f.mean_shift_m.onset_mean_shift_m)} m`),
      AT.el("td", { class: "num" }, `${fmt(f.mean_shift_m.mid_mean_shift_m)} m`)));
    byId("filter-table").replaceChildren(
      AT.el("tr", {}, AT.el("th", {}, "Filter"), AT.el("th", {}, "Start of braking"), AT.el("th", {}, "Middle of braking")), ...rows);
    byId("filter-note").textContent = `Average shift over ${demo.corners_in_average} simulated heavy-braking corners (+ = later than the truth). `
      + "Conclusion used everywhere in the project: events are located on the raw samples; smoothing is only for display.";
  }

  // ---------------------------------------------------------------- 3. estimators

  const FEATURE_NAMES = { brake_onset_m: "Brake onset", apex_m: "Slowest point", throttle_pickup_m: "Throttle pickup (10 %)",
    full_throttle_m: "Full throttle (99 %)", min_speed_kmh: "Minimum speed", entry_speed_kmh: "Entry speed", exit_speed_kmh: "Exit speed" };
  const TYPE_LABELS = { heavy_braking: "Heavy braking", medium: "Medium", fast: "Fast" };

  function renderTypeButtons() {
    const types = [...new Set(data.estimators.rows.map((r) => r.corner_type))];
    byId("type-buttons").replaceChildren(...types.map((type) => {
      const button = AT.el("button", { type: "button", "aria-pressed": String(type === state.cornerType) }, TYPE_LABELS[type] || type);
      button.addEventListener("click", () => { state.cornerType = type; renderTypeButtons(); renderEstimators(); });
      return button;
    }));
  }

  function renderEstimators() {
    byId("mc-laps").textContent = d3.format(",")(data.estimators.laps_per_type);
    const rows = data.estimators.rows.filter((r) => r.corner_type === state.cornerType);
    const positionFeatures = ["brake_onset_m", "apex_m", "throttle_pickup_m", "full_throttle_m"];
    const items = positionFeatures.map((feature) => ({
      feature, all: rows.filter((r) => r.feature === feature),
      naive: rows.find((r) => r.feature === feature && r.naive), chosen: rows.find((r) => r.feature === feature && r.chosen),
    })).filter((item) => item.chosen);
    const box = byId("estimator-chart");
    box.replaceChildren();
    legend(box, [["obvious method", dotMark(C.orange, true)], ["method the pipeline uses", dotMark(C.blue)]]);
    // wide screens: names on the left; phones: each name on its own line above its row
    const width = box.clientWidth, narrow = width < 560;
    const ROW = narrow ? 62 : 52, LABEL = narrow ? 44 : 170;   // phones: room for a value label left of the first dot
    const height = 40 + items.length * ROW + 40;
    const maxError = d3.max(items, (i) => Math.max(i.chosen.rmse, i.naive ? i.naive.rmse : 0)) * 1.1;
    const f = frame(box, { width, height, x: d3.scaleLinear().domain([0, maxError]).nice(), y: d3.scaleLinear().domain([0, 1]),
      xLabel: "TYPICAL ERROR OF ONE MEASUREMENT (RMSE), METRES", yLabel: "", yTicks: 0,
      margin: { left: LABEL, right: 24, top: 20, bottom: 44 } });
    items.forEach((item, i) => {
      const y = 20 + i * ROW + ROW / 2 + (narrow ? 8 : 0);
      const g = f.svg.append("g");
      g.append("text").attr("x", 0).attr("y", narrow ? y - 22 : y - 6).attr("class", "tower-code").attr("dominant-baseline", "central")
        .text(FEATURE_NAMES[item.feature]);
      if (!narrow) {
        g.append("text").attr("x", 0).attr("y", y + 10).attr("class", "tower-team").attr("dominant-baseline", "central").text(item.chosen.estimator);
      }
      const same = item.naive && Math.abs(item.naive.rmse - item.chosen.rmse) < 0.15;   // e.g. full throttle: no gain
      if (item.naive && item.naive !== item.chosen && !same) {
        g.append("line").attr("x1", f.x(item.naive.rmse)).attr("x2", f.x(item.chosen.rmse)).attr("y1", y).attr("y2", y)
          .attr("stroke", C.hair).attr("stroke-width", 2);
        g.append("circle").attr("cx", f.x(item.naive.rmse)).attr("cy", y).attr("r", 6).attr("fill", C.bg).attr("stroke", C.orange).attr("stroke-width", 2.5);
        g.append("text").attr("class", "point-label").attr("x", f.x(item.naive.rmse) + 10).attr("y", y).attr("dominant-baseline", "central")
          .text(`${item.naive.rmse.toFixed(1)} m`);
      }
      g.append("circle").attr("cx", f.x(item.chosen.rmse)).attr("cy", y).attr("r", 6.5).attr("fill", C.blue).attr("stroke", C.bg).attr("stroke-width", 2);
      g.append("text").attr("class", "point-label").attr("x", f.x(item.chosen.rmse) - 10).attr("y", y).attr("text-anchor", "end")
        .attr("dominant-baseline", "central")
        .text(`${item.chosen.rmse.toFixed(1)} m${same ? (narrow ? " (same)" : " (no better method found)") : ""}`);
      g.append("rect").attr("x", 0).attr("y", y - ROW / 2).attr("width", width).attr("height", ROW).attr("fill", "transparent")
        .on("pointermove", (event) => showTooltip(event, `${FEATURE_NAMES[item.feature]}: every estimator tried`,
          item.all.map((r) => [r.estimator + (r.chosen ? " (used)" : ""), `RMSE ${r.rmse.toFixed(2)} · bias ${fmt(r.bias, 2)}`])))
        .on("pointerleave", hideTooltip);
    });
    const onset = items.find((i) => i.feature === "brake_onset_m");
    const speed = rows.find((r) => r.feature === "min_speed_kmh" && r.chosen);
    const peak = rows.filter((r) => r.feature === "peak_decel_ms2");
    byId("estimator-text").textContent = (onset && onset.naive
      ? `Taking the first sample with the brake flag on as the braking point is ${fmt(onset.naive.bias)} m late on average `
        + `(the true onset lies somewhere in the gap before it); the speed breakpoint inside that gap has ${onset.chosen.rmse.toFixed(1)} m error. `
      : "")
      + (speed ? `Minimum speed is measured to ${speed.rmse.toFixed(2)} km/h. ` : "")
      + (peak.length ? `Peak deceleration could not be measured (best error ${d3.min(peak, (r) => r.rmse).toFixed(1)} m/s²), `
        + "so the mean deceleration over the braking zone is used instead." : "");
  }

  // ---------------------------------------------------------------- 4. alignment

  function renderAlignment() {
    const al = data.alignment;
    const raw = al.offset.raw, smooth = al.offset.smooth, d = al.offset.d;
    const scatter = Math.sqrt(d3.mean(raw.map((v, i) => (v - smooth[i]) ** 2)));
    // the slow trend is not one steady drift: it wanders along the lap (speed-integration error
    // plus the car's line being longer or shorter than the reference path), so show its range
    const [low, high] = d3.extent(smooth);
    const integrated = al.gap_from_integrated.gap, projected = al.gap_from_projected.gap;
    byId("alignment-tiles").replaceChildren(
      tile("Position scatter", `±${scatter.toFixed(1)} m`, "per sample, projected X/Y around its smooth trend"),
      tile("Slow difference within a lap", `${(high - low).toFixed(0)} m`,
        `from ${fmt(low)} to ${fmt(high)} m along the lap; removed by the trend`),
      tile("Error in a corner window", `${al.window_error_m.toFixed(2)} m`, "the fused coordinate used for the features"),
      tile("Lap gap at the line", `${AT.signed(integrated[integrated.length - 1])} s`, `official ${AT.signed(al.lap_time_gap)} s`));

    // (a) the offset between the two coordinates along the lap
    let box = byId("offset-chart");
    box.replaceChildren();
    legend(box, [["position minus integrated speed, each sample", dotMark(C.grey)], ["its smooth trend (moving average)", lineMark(C.blue)]]);
    const values = [...raw, ...smooth];
    let f = frame(box, { width: box.clientWidth, height: 260, x: d3.scaleLinear().domain([0, d3.max(d)]),
      y: d3.scaleLinear().domain(d3.extent(values)).nice(), xLabel: "DISTANCE INTO THE LAP, M", yLabel: "DIFFERENCE, M",
      xFormat: d3.format(",") });
    f.plot.append("g").selectAll("circle").data(raw).join("circle").attr("cx", (v, i) => f.x(d[i])).attr("cy", (v) => f.y(v))
      .attr("r", 2.4).attr("fill", C.grey);
    f.plot.append("path").attr("d", d3.line().x((v, i) => f.x(d[i])).y((v) => f.y(v))(smooth)).attr("fill", "none")
      .attr("stroke", C.blue).attr("stroke-width", 2.5);
    byId("offset-note").textContent = `${al.driver}'s fastest lap, 2024 Abu Dhabi. The dots scatter because projecting X/Y onto the `
      + "track is noisy; the slow trend is integrated speed drifting away from position (speed-integration error, and the "
      + "car's line being longer or shorter than the reference path). A complementary filter keeps the smooth detail of "
      + "integrated speed and takes only the slow trend from position: fused = integrated + moving average (position − integrated).";

    // (b) the gap between the two hero laps, from each coordinate
    box = byId("gap-chart");
    box.replaceChildren();
    legend(box, [["from projected position", lineMark(C.orange, 1.5)], ["from integrated speed", lineMark(C.blue, 2.5)],
      ["official lap-time gap", dotMark(C.ink)]]);
    const all = [...integrated, ...projected, al.lap_time_gap];
    f = frame(box, { width: box.clientWidth, height: 260, x: d3.scaleLinear().domain([0, d3.max(al.gap_from_integrated.s)]),
      y: d3.scaleLinear().domain([Math.min(0, d3.min(all)), d3.max(all)]).nice(), xLabel: "DISTANCE INTO THE LAP, M",
      yLabel: `${al.other} BEHIND ${al.driver}, S`, xFormat: d3.format(","), yFormat: (v) => (v === 0 ? "0" : AT.signed(v, 1)) });
    f.plot.append("line").attr("x1", f.x.range()[0]).attr("x2", f.x.range()[1]).attr("y1", f.y(0)).attr("y2", f.y(0)).attr("stroke", "#4a4c53");
    const curve = (series) => d3.line().x((v, i) => f.x(series.s[i])).y((v) => f.y(v))(series.gap);
    f.plot.append("path").attr("d", curve(al.gap_from_projected)).attr("fill", "none").attr("stroke", C.orange).attr("stroke-width", 1.5);
    f.plot.append("path").attr("d", curve(al.gap_from_integrated)).attr("fill", "none").attr("stroke", C.blue).attr("stroke-width", 2.5);
    f.svg.append("circle").attr("cx", f.x.range()[1] - 4).attr("cy", f.y(al.lap_time_gap)).attr("r", 5).attr("fill", C.ink);
    byId("gap-note").textContent = `${al.other} vs ${al.driver}, same weekend. Built from projected position, the gap jumps around and `
      + `ends at ${AT.signed(projected[projected.length - 1])} s; from integrated speed it is smooth and ends at `
      + `${AT.signed(integrated[integrated.length - 1])} s, next to the official ${AT.signed(al.lap_time_gap)} s. Integration is a `
      + "low-pass filter, and its drift is nearly the same for both laps, so it cancels in the difference.";
  }

  // ---------------------------------------------------------------- 5. cleaning funnel

  function renderFunnel() {
    const dev = data.funnel.development, fin = data.funnel.final_2025;
    const steps = [
      { group: "2023–2024", label: "Corner passes found", n: dev.rows, note: "every kept lap × every detected braking zone" },
      { group: "2023–2024", label: "With complete data in the window", n: dev.usable,
        note: `${d3.format(",")(dev.excluded["feed gap in window"])} had a feed dropout inside the window, ${dev.excluded["no car/position data"] || 0} had no data` },
      { group: "2023–2024", label: "Dry and plausible (analysed)", n: dev.cleaning.clean_rows,
        note: `${d3.format(",")(dev.cleaning.dropped_not_dry)} not on dry tyres, ${dev.cleaning.dropped_min_speed_below_40} with an impossible minimum speed` },
      { group: "2025 (held out)", label: "With complete data in the window", n: fin.usable, note: "same pipeline, run once" },
      { group: "2025 (held out)", label: "Dry and plausible (analysed)", n: fin.cleaning.clean_rows,
        note: `${d3.format(",")(fin.cleaning.dropped_not_dry)} not on dry tyres, ${fin.cleaning.dropped_min_speed_below_40} with an impossible minimum speed` },
    ];
    const box = byId("funnel-chart");
    box.replaceChildren();
    // wide screens: label on the left, bar on the right; phones: label above its bar
    const width = box.clientWidth, narrow = width < 640;
    const LABEL = narrow ? 0 : Math.min(300, width * 0.36), ROW = narrow ? 70 : 46, TOP = narrow ? 18 : 0;
    const height = steps.length * ROW + 30;
    const x = d3.scaleLinear().domain([0, dev.rows]).range([LABEL, width - 70]);
    const svg = d3.select(box).append("svg").attr("width", width).attr("height", height);
    steps.forEach((step, i) => {
      const y = 10 + i * ROW;
      if (i === 3) svg.append("line").attr("x1", 0).attr("x2", width).attr("y1", y - 4).attr("y2", y - 4).attr("stroke", C.hair);
      svg.append("text").attr("x", 0).attr("y", y + 12).attr("class", "tower-code").text(step.label);
      svg.append("text").attr("x", narrow ? width : 0).attr("y", narrow ? y + 12 : y + 29).attr("text-anchor", narrow ? "end" : "start")
        .attr("class", "tower-team").text(step.group);
      svg.append("rect").attr("x", LABEL).attr("y", y + 4 + TOP).attr("width", Math.max(2, x(step.n) - LABEL)).attr("height", 20)
        .attr("fill", i === 2 || i === 4 ? C.blue : "#3a3c43");
      svg.append("text").attr("x", x(step.n) + 8).attr("y", y + 15 + TOP).attr("dominant-baseline", "central").attr("class", "tower-value")
        .text(d3.format(",")(step.n));
      svg.append("text").attr("x", LABEL).attr("y", y + 38 + TOP).attr("class", "tower-team").text(step.note);
    });
  }

  // ---------------------------------------------------------------- start

  async function init() {
    try {
      data = await AT.getJSON("/api/method");
    } catch (error) {
      byId("sampling-chart").append(AT.el("p", { class: "message" },
        `Could not load the method data (${error.message}${error.body && error.body.hint ? "; " + error.body.hint : ""}).`));
      return;
    }
    renderAll();
    byId("speed-slider").addEventListener("input", renderSpeed);
  }

  function renderAll() {
    renderSampling();
    renderFilterButtons();
    renderFilter();
    renderTypeButtons();
    renderEstimators();
    renderAlignment();
    renderFunnel();
  }

  let resizeTimer = null;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => { if (data) renderAll(); }, 150);
  });

  init();
})();
