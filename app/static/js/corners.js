/* Corner lab: one braking zone, every driver, every lap.
 *
 * Data: /api/sessions (pickers), /api/sessions/<key> (drivers, team colours,
 * corners, track), /api/corners/<key> (the clean dataset rows of that session:
 * one row per driver, lap and corner, exactly the rows the analysis used),
 * /api/features (what each measurement means, its per-lap error, its ICC).
 *
 * The chart is a "timing tower" dot plot: one row per driver, one dot per lap,
 * a white tick at the driver's median. Nothing is fitted or smoothed here.
 */
(() => {
  const page = document.getElementById("corners-page");
  const byId = (id) => document.getElementById(id);
  const ui = {
    season: byId("season"), event: byId("event"), corner: byId("corner"), feature: byId("feature"),
    orderButtons: [...document.querySelectorAll(".segmented button")],
    title: byId("lab-title"), reading: byId("lab-reading"), tower: byId("tower"), lights: byId("lights"),
    map: d3.select("#corner-map"), caption: byId("corner-caption"), facts: byId("feature-facts"),
  };
  const ROW_H = 32, LABEL_W = 186, VALUE_W = 112, TOP = 52, BOTTOM = 44;
  const CORNER_WINDOW = [-300, 200];

  // which way is "more" for each measurement, in words
  const DIRECTION = {
    brake_onset_m: "right = brakes later, closer to the marker",
    braking_distance_m: "right = a longer braking zone",
    mean_decel_ms2: "right = harder average deceleration",
    min_speed_kmh: "right = more speed at the slowest point",
    apex_m: "right = slowest point further along the corner",
    throttle_pickup_m: "right = back on the throttle later",
    full_throttle_m: "right = full throttle later",
    entry_speed_kmh: "right = faster on the way in",
    exit_speed_kmh: "right = faster on the way out",
    corner_time_s: "right = more time spent in the corner",
  };
  const DIGITS = { m: 1, "km/h": 1, s: 3, "m/s²": 1 };

  const state = { index: [], session: null, rows: [], features: [], corner: null, feature: "brake_onset_m",
    order: "value", request: 0 };

  const featureInfo = () => state.features.find((f) => f.key === state.feature);
  const cornerInfo = () => state.session.corners.find((c) => c.name === state.corner);
  // a real minus sign (−), as the axis and timing screens print it
  const format = (value, unit) => (value == null ? "–" : value.toFixed(DIGITS[unit] ?? 1).replace("-", "−"));

  // ---------------------------------------------------------------- pickers

  function option(value, text, disabled = false) {
    return AT.el("option", { value, disabled }, text);
  }

  function fillSeasons(year) {
    const years = [...new Set(state.index.map((s) => s.year))].sort((a, b) => b - a);
    ui.season.replaceChildren(...years.map((y) => option(y, y === 2025 ? `${y} · test` : String(y))));
    ui.season.value = year;
  }

  function fillEvents(year) {
    const rows = state.index.filter((s) => s.year === Number(year)).sort((a, b) => a.round - b.round);
    ui.event.replaceChildren(...rows.map((s) => {
      let text = `R${String(s.round).padStart(2, "0")} · ${s.location}`;
      if (!s.available) text += " · no lap data";
      else if (s.wet) text += " · wet laps removed";
      return option(s.key, text, !s.available);
    }));
  }

  function fillCorners() {
    ui.corner.replaceChildren(...state.session.corners.map((c) =>
      option(c.name, `${c.name} · ${c.type} · ${c.min_speed_kmh} km/h`)));
    ui.corner.value = state.corner;
  }

  function fillFeatures() {
    ui.feature.replaceChildren(...state.features.map((f) => option(f.key, `${f.label} (${f.unit})`)));
    ui.feature.value = state.feature;
  }

  // ---------------------------------------------------------------- loading

  async function init() {
    try {
      [state.index, { features: state.features }] = await Promise.all([AT.getJSON("/api/sessions"), AT.getJSON("/api/features")]);
    } catch (error) {
      ui.tower.append(AT.el("p", { class: "message" }, `Could not load the data (${error.message}).`));
      return;
    }
    const params = new URLSearchParams(location.search);
    const fromUrl = Number(params.get("session"));
    const key = state.index.some((s) => s.key === fromUrl && s.available) ? fromUrl : Number(page.dataset.defaultSession);
    if (state.features.some((f) => f.key === params.get("feature"))) state.feature = params.get("feature");
    const year = state.index.find((s) => s.key === key).year;
    fillSeasons(year);
    fillEvents(year);
    ui.event.value = key;
    fillFeatures();
    await loadSession(key, params.get("corner"));
  }

  async function loadSession(key, corner) {
    const request = ++state.request;
    ui.lights.hidden = false;
    try {
      const [session, rows] = await Promise.all([AT.getJSON(`/api/sessions/${key}`), AT.getJSON(`/api/corners/${key}`)]);
      if (request !== state.request) return;
      state.session = session;
      state.rows = rows.rows;
      state.corner = session.corners.some((c) => c.name === corner) ? corner : session.corners[0].name;
      fillCorners();
      render();
    } catch (error) {
      if (request === state.request) message(`Could not load this session (${error.message}).`);
    } finally {
      if (request === state.request) ui.lights.hidden = true;
    }
  }

  function message(text) {
    ui.tower.querySelectorAll(".tower-key, svg, .message, .tooltip").forEach((n) => n.remove());
    ui.tower.append(AT.el("p", { class: "message" }, text));
  }

  // ---------------------------------------------------------------- the tower

  /** Per driver: their laps' values at this corner, and the median. */
  function driverValues() {
    const byDriver = new Map();
    for (const row of state.rows) {
      if (row.corner !== state.corner || row[state.feature] == null) continue;
      if (!byDriver.has(row.driver)) byDriver.set(row.driver, { team: row.team, laps: [] });
      byDriver.get(row.driver).laps.push({ lap: row.lap, value: row[state.feature], lapTime: row.lap_time_s });
    }
    const drivers = [];
    for (const [code, entry] of byDriver) {
      const info = state.session.drivers.find((d) => d.code === code)
        || { code, team: entry.team, colour: "#888888", name: code };
      drivers.push({ code, info, laps: entry.laps, median: d3.median(entry.laps, (l) => l.value) });
    }
    return drivers;
  }

  function order(drivers) {
    if (state.order === "value") return drivers.sort((a, b) => a.median - b.median);
    // by team: teams ordered by their better driver, teammates next to each other
    const teamBest = new Map();
    for (const d of drivers) {
      const best = teamBest.get(d.info.team);
      teamBest.set(d.info.team, best === undefined ? d.median : Math.min(best, d.median));
    }
    return drivers.sort((a, b) => (teamBest.get(a.info.team) - teamBest.get(b.info.team))
      || a.info.team.localeCompare(b.info.team) || (a.median - b.median));
  }

  function render() {
    history.replaceState(null, "", `?session=${state.session.key}&corner=${state.corner}&feature=${state.feature}`);
    const feature = featureInfo();
    const corner = cornerInfo();
    const error = feature.by_corner_type[corner.type].measurement_error_per_lap;
    const drivers = order(driverValues());
    const lapCount = d3.sum(drivers, (d) => d.laps.length);

    ui.title.textContent = `${feature.label} at ${corner.name}`;
    ui.reading.textContent = `${corner.type} corner, ${corner.min_speed_kmh} km/h on the session's fastest lap · `
      + `${drivers.length} drivers, ${lapCount} laps · ${DIRECTION[feature.key]}`;
    renderFacts(feature, corner);
    renderMap(corner);
    ui.tower.querySelectorAll(".tower-key, svg, .message, .tooltip").forEach((n) => n.remove());
    if (!drivers.length) {
      message("No clean laps for this measurement here (for example, no braking event was found in this zone).");
      return;
    }

    // how to read the chart (a key, in words and marks)
    const keyOf = (draw, text) => {
      const key = AT.el("span", { class: "key" });
      draw(d3.select(key).append("svg").attr("width", 18).attr("height", 18));
      key.append(text);
      return key;
    };
    ui.tower.append(AT.el("div", { class: "chart-legend tower-key" },
      keyOf((s) => s.append("circle").attr("cx", 9).attr("cy", 9).attr("r", 5).attr("fill", "#b9b8b1"), "one lap"),
      keyOf((s) => s.append("line").attr("x1", 9).attr("x2", 9).attr("y1", 2).attr("y2", 16).attr("stroke", "#f2f1ed").attr("stroke-width", 2.5), "the driver's median"),
      keyOf((s) => s.append("line").attr("x1", 9).attr("x2", 9).attr("y1", 2).attr("y2", 16).attr("stroke", "#4a4c53").attr("stroke-width", 1.5), "median of all drivers"),
      keyOf((s) => s.append("path").attr("d", "M2 9H16M2 5V13M16 5V13").attr("stroke", "#f2f1ed").attr("stroke-width", 1.5).attr("fill", "none"), "± measurement error of one lap")));

    const width = ui.tower.clientWidth;
    const height = TOP + drivers.length * ROW_H + BOTTOM;
    const all = drivers.flatMap((d) => d.laps.map((l) => l.value));
    const fieldMedian = d3.median(all);
    let [low, high] = d3.extent(all);
    const pad = Math.max((high - low) * 0.06, error || 0.5);
    const x = d3.scaleLinear().domain([low - pad, high + pad]).nice().range([LABEL_W, width - VALUE_W]);
    const svg = d3.select(ui.tower).append("svg").attr("width", width).attr("height", height);

    // gridlines + axis
    svg.append("g").attr("class", "gridline").attr("transform", `translate(0,${height - BOTTOM})`)
      .call(d3.axisBottom(x).ticks(6).tickSize(-(height - BOTTOM - TOP + 8)).tickFormat(""));
    svg.append("g").attr("class", "axis").attr("transform", `translate(0,${height - BOTTOM})`)
      .call(d3.axisBottom(x).ticks(6).tickSizeOuter(0)).select(".domain").attr("stroke", "#3b3d44");
    svg.append("text").attr("class", "corner-tag").attr("x", width - VALUE_W).attr("y", height - 8).attr("text-anchor", "end")
      .text(feature.unit === "m" ? "METRES FROM THE CORNER MARKER · NEGATIVE = BEFORE IT" : feature.unit.toUpperCase());

    // field median
    svg.append("line").attr("x1", x(fieldMedian)).attr("x2", x(fieldMedian)).attr("y1", TOP - 8).attr("y2", height - BOTTOM)
      .attr("stroke", "#4a4c53");
    svg.append("text").attr("class", "corner-tag").attr("x", x(fieldMedian)).attr("y", TOP - 14).attr("text-anchor", "middle")
      .text(`FIELD MEDIAN ${format(fieldMedian, feature.unit)}`);

    // the measurement-error bar: how wide +-1 per-lap error is on this axis
    if (error) {
      const right = width - VALUE_W, left = x(x.invert(right) - 2 * error);
      const bar = svg.append("g").attr("transform", "translate(0,16)");
      bar.append("line").attr("x1", left).attr("x2", right).attr("y1", 0).attr("y2", 0).attr("stroke", "#f2f1ed").attr("stroke-width", 2);
      for (const end of [left, right]) {
        bar.append("line").attr("x1", end).attr("x2", end).attr("y1", -5).attr("y2", 5).attr("stroke", "#f2f1ed").attr("stroke-width", 2);
      }
      bar.append("text").attr("class", "corner-tag").attr("x", left - 8).attr("y", 0).attr("dominant-baseline", "central")
        .attr("text-anchor", "end").text(`ONE LAP IS MEASURED TO ABOUT ±${format(error, feature.unit)} ${feature.unit.toUpperCase()}`);
    }

    // rows
    const tooltip = AT.el("div", { class: "tooltip", hidden: true });
    ui.tower.append(tooltip);
    for (const [i, d] of drivers.entries()) {
      const y = TOP + i * ROW_H + ROW_H / 2;
      const row = svg.append("g");
      if (i % 2 === 0) {
        row.append("rect").attr("x", 0).attr("y", y - ROW_H / 2).attr("width", width).attr("height", ROW_H).attr("fill", "#101114");
      }
      row.append("rect").attr("x", 0).attr("y", y - 10).attr("width", 4).attr("height", 20).attr("fill", d.info.colour);
      row.append("text").attr("x", 14).attr("y", y).attr("dominant-baseline", "central").attr("class", "tower-code").text(d.code);
      row.append("text").attr("x", 60).attr("y", y).attr("dominant-baseline", "central").attr("class", "tower-team").text(d.info.team);
      row.append("line").attr("x1", x(d3.min(d.laps, (l) => l.value))).attr("x2", x(d3.max(d.laps, (l) => l.value)))
        .attr("y1", y).attr("y2", y).attr("stroke", "#2a2c32").attr("stroke-width", 2);
      for (const lap of d.laps) {
        const dot = row.append("circle").attr("cx", x(lap.value)).attr("cy", y).attr("r", 5.5)
          .attr("fill", d.info.colour).attr("stroke", "#0b0c0e").attr("stroke-width", 1.5);
        // a bigger invisible target, so a 5 px dot is easy to hover
        row.append("circle").attr("cx", x(lap.value)).attr("cy", y).attr("r", 12).attr("fill", "transparent")
          .style("cursor", "default")
          .on("pointerenter", (event) => {
            dot.attr("r", 7);
            tooltip.replaceChildren(
              AT.el("div", { class: "tt-head" }, `${d.code} · lap ${lap.lap}`),
              AT.el("table", {},
                AT.el("tr", {}, AT.el("td", { class: "k" }, feature.label), AT.el("td", { class: "v num" }, `${format(lap.value, feature.unit)} ${feature.unit}`)),
                AT.el("tr", {}, AT.el("td", { class: "k" }, "Lap time"), AT.el("td", { class: "v num" }, AT.lapTime(lap.lapTime))),
                AT.el("tr", {}, AT.el("td", { class: "k" }, "Driver median"), AT.el("td", { class: "v num" }, `${format(d.median, feature.unit)} ${feature.unit}`))));
            tooltip.hidden = false;
            const box = ui.tower.getBoundingClientRect();
            const left = event.clientX - box.left + 14;
            tooltip.style.left = `${left + 200 > box.width ? left - 220 : left}px`;
            tooltip.style.top = `${event.clientY - box.top - 10}px`;
          })
          .on("pointerleave", () => { dot.attr("r", 5.5); tooltip.hidden = true; });
      }
      row.append("line").attr("x1", x(d.median)).attr("x2", x(d.median)).attr("y1", y - 9).attr("y2", y + 9)
        .attr("stroke", "#f2f1ed").attr("stroke-width", 2.5).style("pointer-events", "none");
      row.append("text").attr("x", width - 10).attr("y", y).attr("dominant-baseline", "central").attr("text-anchor", "end")
        .attr("class", "tower-value").text(`${format(d.median, feature.unit)}`);
      row.append("text").attr("x", width - 70).attr("y", y).attr("dominant-baseline", "central").attr("text-anchor", "end")
        .attr("class", "tower-team").text(`${d.laps.length} lap${d.laps.length > 1 ? "s" : ""}`);
    }
    svg.append("text").attr("class", "corner-tag").attr("x", width - 10).attr("y", TOP - 14).attr("text-anchor", "end").text("MEDIAN");
  }

  // ---------------------------------------------------------------- side panels

  function iccWords(value) {
    if (value == null) return "not estimated";
    if (value < 0.1) return "barely carries over";
    if (value < 0.25) return "partly carries over";
    return "carries over fairly well";
  }

  function renderFacts(feature, corner) {
    const stats = feature.by_corner_type[corner.type];
    const ci = (pair) => (pair[0] == null ? "" : ` (95 % interval ${pair[0].toFixed(2)}–${pair[1].toFixed(2)})`);
    const error = stats.measurement_error_per_lap;
    ui.facts.replaceChildren(
      AT.el("h3", {}, feature.label),
      AT.el("p", {}, feature.meaning),
      AT.el("dl", {},
        AT.el("dt", {}, "Measurement error, one lap"),
        AT.el("dd", {}, error == null ? "not simulated (computed from other measurements)"
          : `about ±${format(error, feature.unit)} ${feature.unit}, from the Phase 2 simulation of this exact pipeline`),
        AT.el("dt", {}, `Repeatability at ${corner.type} corners, lap to lap`),
        AT.el("dd", {}, `ICC ${stats.icc_lap.toFixed(2)}${ci(stats.icc_lap_ci)}: ${Math.round(stats.icc_lap * 100)} % of the spread `
          + "between laps comes from differences between drivers."),
        AT.el("dt", {}, "Repeatability, weekend to weekend"),
        AT.el("dd", {}, `ICC ${stats.icc_weekend.toFixed(2)}${ci(stats.icc_weekend_ci)}: a driver's place on this measurement `
          + `${iccWords(stats.icc_weekend)} from one weekend to the next.`)),
      AT.el("p", { class: "facts-note" }, "Repeatability from all 2023–2024 drivers (H1), relative to the field at each corner."));
  }

  function renderMap(corner) {
    const svg = ui.map;
    svg.selectAll("*").remove();
    const track = state.session.track;
    const fit = AT.fitTrack(track.x, track.y, 400, 300, 26);
    const at = (s) => [fit.x(AT.interp(s, track.s, track.x)), fit.y(AT.interp(s, track.s, track.y))];
    const points = track.x.map((x, i) => [fit.x(x), fit.y(track.y[i])]);
    const line = d3.line().curve(d3.curveCatmullRom.alpha(0.5));
    svg.append("path").attr("d", line(points) + "Z").attr("fill", "none").attr("stroke", "#1f2126").attr("stroke-width", 11);
    svg.append("path").attr("d", line(points) + "Z").attr("fill", "none").attr("stroke", "#3d3f46").attr("stroke-width", 1.3);
    const [from, to] = [corner.s_m + CORNER_WINDOW[0], corner.s_m + CORNER_WINDOW[1]];
    const inside = track.s.map((s, k) => [s, k]).filter(([s]) => s > from && s < to).map(([, k]) => points[k]);
    svg.append("path").attr("d", line([at(Math.max(0, from)), ...inside, at(Math.min(track.length_m, to))]))
      .attr("fill", "none").attr("stroke", "#f2f1ed").attr("stroke-width", 4).attr("stroke-linecap", "round");
    const [px, py] = at(corner.s_m);
    svg.append("circle").attr("cx", px).attr("cy", py).attr("r", 5).attr("fill", "#ff3b1f").attr("stroke", "#0b0c0e").attr("stroke-width", 2);
    const cx = d3.mean(points, (p) => p[0]), cy = d3.mean(points, (p) => p[1]);
    for (const c of state.session.corners) {
      const [qx, qy] = at(c.s_m);
      const dx = qx - cx, dy = qy - cy, d = Math.hypot(dx, dy) || 1;
      svg.append("text").attr("class", "corner-tag").attr("x", qx + (dx / d) * 15).attr("y", qy + (dy / d) * 15)
        .attr("text-anchor", "middle").attr("dominant-baseline", "central")
        .attr("fill", c.name === corner.name ? "#f2f1ed" : null).text(c.name);
    }
    ui.caption.textContent = `${corner.name} · ${Math.round(corner.s_m).toLocaleString("en")} m`;
  }

  // ---------------------------------------------------------------- events

  ui.season.addEventListener("change", () => {
    fillEvents(ui.season.value);
    const first = [...ui.event.options].find((o) => !o.disabled);
    if (first) { ui.event.value = first.value; loadSession(Number(first.value), state.corner); }
  });
  ui.event.addEventListener("change", () => loadSession(Number(ui.event.value), state.corner));
  ui.corner.addEventListener("change", () => { state.corner = ui.corner.value; render(); });
  ui.feature.addEventListener("change", () => { state.feature = ui.feature.value; render(); });
  for (const button of ui.orderButtons) {
    button.addEventListener("click", () => {
      state.order = button.dataset.order;
      for (const b of ui.orderButtons) b.setAttribute("aria-pressed", String(b === button));
      render();
    });
  }
  let resizeTimer = null;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => { if (state.session) render(); }, 150);
  });

  init();
})();
