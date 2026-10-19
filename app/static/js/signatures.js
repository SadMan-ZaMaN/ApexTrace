/* Driver vs car: H3 (teammate identification) and H4 (drivers who changed teams).
 *
 * Data: /api/identification (per team-season balanced accuracy, 2023-2025),
 * /api/signatures (the H4 season signatures, checked against the frozen results
 * by the export script), /api/features (feature names).
 *
 * Colours (validated with the dataviz palette checker on the dark surface):
 * blue = our corner features / drivers who stayed, orange = raw lap statistics /
 * drivers who changed teams, grey hollow ring = the lap-time baseline.
 * Heat cells: blue (below the average 2024 driver) - grey (average) - red (above).
 */
(() => {
  const C = { blue: "#3987e5", orange: "#d95926", grey: "#85847e", ink: "#f2f1ed", bg: "#0b0c0e" };
  const HEAT = d3.scaleLinear().domain([-2, 0, 2]).range(["#3987e5", "#383835", "#e66767"])
    .interpolate(d3.interpolateLab).clamp(true);
  const SHORT = {
    brake_onset_m: "Brake on", braking_distance_m: "Brake dist.", mean_decel_ms2: "Decel.", min_speed_kmh: "Min speed",
    apex_m: "Apex", throttle_pickup_m: "Throttle on", full_throttle_m: "Full thr.", entry_speed_kmh: "Entry spd",
    exit_speed_kmh: "Exit spd", corner_time_s: "Corner time",
  };
  const POSITIVE_MEANS = {
    brake_onset_m: "brakes later", braking_distance_m: "brakes over a longer distance", mean_decel_ms2: "decelerates harder",
    min_speed_kmh: "carries more minimum speed", apex_m: "reaches the slowest point later",
    throttle_pickup_m: "gets on the throttle later", full_throttle_m: "reaches full throttle later",
    entry_speed_kmh: "enters faster", exit_speed_kmh: "exits faster", corner_time_s: "spends more time in the corner",
  };
  const CORNER_TYPES = ["slow", "medium", "fast"];

  const state = { identification: null, signatures: null, features: null, year: 2025, selected: "HAM" };
  const byId = (id) => document.getElementById(id);
  const tooltip = AT.el("div", { class: "tooltip", hidden: true });
  document.body.append(tooltip);

  function pValue(p) {
    if (p < 0.001) return "p < 0.001";
    return `p = ${p < 0.01 ? p.toFixed(4) : p.toFixed(3)}`;
  }

  function showTooltip(event, head, rows) {
    tooltip.replaceChildren(AT.el("div", { class: "tt-head" }, head),
      AT.el("table", {}, ...rows.map(([k, v]) => AT.el("tr", {}, AT.el("td", { class: "k" }, k), AT.el("td", { class: "v num" }, v)))));
    tooltip.hidden = false;
    const left = event.pageX + 14;
    tooltip.style.left = `${left + 240 > window.innerWidth ? event.pageX - 250 : left}px`;
    tooltip.style.top = `${event.pageY - 12}px`;
  }
  const hideTooltip = () => { tooltip.hidden = true; };

  function tile(label, value, sub) {
    return AT.el("div", { class: "tile" }, AT.el("div", { class: "tile-label" }, label),
      AT.el("div", { class: "tile-value" }, value), sub ? AT.el("div", { class: "tile-sub num" }, sub) : null);
  }

  // ---------------------------------------------------------------- H3

  function renderTabs() {
    const tabs = byId("season-tabs");
    tabs.replaceChildren(...[2025, 2024, 2023].map((year) => {
      const button = AT.el("button", { type: "button", "aria-pressed": String(year === state.year) },
        year === 2025 ? "2025 · test" : String(year));
      button.addEventListener("click", () => { state.year = year; renderTabs(); renderH3(); });
      return button;
    }));
  }

  function renderH3() {
    const id = state.identification;
    const final = state.year === 2025;
    const block = final ? id.final_2025 : id.development_2023_2024;
    const range = (k) => `95 % interval ${block[k].ci95[0].toFixed(3)}–${block[k].ci95[1].toFixed(3)}`;
    byId("h3-tiles").replaceChildren(
      tile("Corner features", block.ours.mean.toFixed(3), range("ours")),
      tile("Lap time only", block.lap_time.mean.toFixed(3), range("lap_time")),
      tile("Raw lap statistics", block.raw.mean.toFixed(3), range("raw")),
      tile("Corner features, weekend vote", block.vote.mean.toFixed(3), "all laps of a weekend vote together"));
    const lt = block.ours_vs_lap_time, raw = block.ours_vs_raw;
    byId("h3-verdict").textContent = final
      ? `Held-out 2025: corner features beat lap time for ${lt.wins} of ${lt.teams} teams (Wilcoxon ${pValue(lt.p)}), `
        + `so H3 is replicated on data the method never saw. They do not beat simple whole-lap statistics `
        + `(${raw.wins} of ${raw.teams}, ${pValue(raw.p)}).`
      : `Development, 2023 and 2024 together (tiles: all ${lt.teams} team-seasons): corner features beat lap time for `
        + `${lt.wins} of ${lt.teams} (${pValue(lt.p)}); raw lap statistics: ${raw.wins} of ${raw.teams} (${pValue(raw.p)}). `
        + `The chart shows ${state.year} only.`;
    drawH3(id.teams.filter((t) => t.year === state.year).sort((a, b) => b.ours - a.ours));
  }

  /** A legend row in HTML (wraps on a phone): each entry = a small SVG mark + words (never colour alone). */
  function htmlLegend(entries) {
    return AT.el("div", { class: "chart-legend" }, ...entries.map(([label, draw]) => {
      const key = AT.el("span", { class: "key" });
      const svg = d3.select(key).append("svg").attr("width", 16).attr("height", 16);
      draw(svg.append("g"), 8, 8);
      key.append(label);
      return key;
    }));
  }

  function drawH3(teams) {
    const box = byId("h3-chart");
    box.replaceChildren(htmlLegend([
      ["Lap time only", (g, cx, cy) => drawMark(g, "ring", cx, cy)],
      ["Raw lap statistics", (g, cx, cy) => drawMark(g, "diamond", cx, cy)],
      ["Corner features", (g, cx, cy) => drawMark(g, "dot", cx, cy)]]));
    const width = box.clientWidth, narrow = width < 640;
    const LABEL = narrow ? 128 : 230, RIGHT = 14, TOP = 22, ROW = narrow ? 38 : 34, BOTTOM = 40;
    const height = TOP + teams.length * ROW + BOTTOM;
    const x = d3.scaleLinear().domain([0.3, 1.0]).range([LABEL, width - RIGHT]);
    const ticks = narrow ? 4 : 7;
    const svg = d3.select(box).append("svg").attr("width", width).attr("height", height);
    svg.append("g").attr("class", "gridline").attr("transform", `translate(0,${height - BOTTOM})`)
      .call(d3.axisBottom(x).ticks(ticks).tickSize(-(height - TOP - BOTTOM + 6)).tickFormat(""));
    svg.append("g").attr("class", "axis").attr("transform", `translate(0,${height - BOTTOM})`)
      .call(d3.axisBottom(x).ticks(ticks).tickSizeOuter(0)).select(".domain").attr("stroke", "#3b3d44");
    svg.append("line").attr("x1", x(0.5)).attr("x2", x(0.5)).attr("y1", TOP - 10).attr("y2", height - BOTTOM).attr("stroke", "#5a5c63");
    svg.append("text").attr("class", "corner-tag").attr("x", x(0.5) + 6).attr("y", TOP - 6).text("GUESSING");

    for (const [i, team] of teams.entries()) {
      const y = TOP + i * ROW + ROW / 2;
      const g = svg.append("g");
      if (i % 2 === 0) g.append("rect").attr("x", 0).attr("y", y - ROW / 2).attr("width", width).attr("height", ROW).attr("fill", "#101114");
      g.append("text").attr("x", 0).attr("y", y - 6).attr("class", "tower-code").attr("dominant-baseline", "central").text(team.team);
      g.append("text").attr("x", 0).attr("y", y + 9).attr("class", "tower-team").attr("dominant-baseline", "central")
        .text(narrow ? team.drivers : `${team.drivers} · ${team.sessions} weekends`);
      const values = [team.lap_time, team.raw, team.ours];
      g.append("line").attr("x1", x(d3.min(values))).attr("x2", x(d3.max(values))).attr("y1", y).attr("y2", y)
        .attr("stroke", "#2f3138").attr("stroke-width", 2);
      drawMark(g, "ring", x(team.lap_time), y);
      drawMark(g, "diamond", x(team.raw), y);
      drawMark(g, "dot", x(team.ours), y);
      g.append("rect").attr("x", 0).attr("y", y - ROW / 2).attr("width", width).attr("height", ROW).attr("fill", "transparent")
        .on("pointermove", (event) => showTooltip(event, `${team.team} ${team.year} · ${team.drivers}`, [
          ["Corner features", team.ours.toFixed(3)], ["Raw lap statistics", team.raw.toFixed(3)],
          ["Lap time only", team.lap_time.toFixed(3)], ["Weekend vote", team.vote.toFixed(3)],
          ["Shuffled labels", team.shuffled.toFixed(3)], ["Laps · weekends", `${team.laps} · ${team.sessions}`]]))
        .on("pointerleave", hideTooltip);
    }
  }

  function drawMark(g, shape, cx, cy) {
    if (shape === "ring") {
      g.append("circle").attr("cx", cx).attr("cy", cy).attr("r", 5.5).attr("fill", C.bg).attr("stroke", C.grey).attr("stroke-width", 2);
    } else if (shape === "diamond") {
      g.append("path").attr("d", d3.symbol(d3.symbolDiamond, 90)()).attr("transform", `translate(${cx},${cy})`)
        .attr("fill", C.orange).attr("stroke", C.bg).attr("stroke-width", 2);
    } else {
      g.append("circle").attr("cx", cx).attr("cy", cy).attr("r", 6.5).attr("fill", C.blue).attr("stroke", C.bg).attr("stroke-width", 2);
    }
  }

  // ---------------------------------------------------------------- H4 scatter

  function renderH4() {
    const s = state.signatures.summary;
    byId("h4-tiles").replaceChildren(
      tile("Team changers: own past closer", `${s.changers_own_closer} of ${s.changers}`, `sign test ${pValue(s.p)} · not supported`),
      tile("Drivers who stayed: own past closer", `${s.stayers_own_closer} of ${s.stayers}`, `same comparison · exploratory`));
    drawScatter();
    renderChips();
    renderFingerprint();
  }

  function drawScatter() {
    const box = byId("h4-chart");
    const dot = (colour, hollow) => (g, cx, cy) => g.append("circle").attr("cx", cx).attr("cy", cy).attr("r", 5)
      .attr("fill", hollow ? C.bg : colour).attr("stroke", hollow ? colour : C.bg).attr("stroke-width", 2);
    box.replaceChildren(htmlLegend([["stayed in the team", dot(C.blue, false)],
      ["changed team (preregistered)", dot(C.orange, false)], ["changed team (not preregistered)", dot(C.orange, true)]]));
    const size = Math.min(box.clientWidth, 560);
    const M = { left: 52, right: 16, top: 16, bottom: 46 };
    const x = d3.scaleLinear().domain([0.3, 1.7]).range([M.left, size - M.right]);
    const y = d3.scaleLinear().domain([0.3, 1.7]).range([size - M.bottom, M.top]);
    const svg = d3.select(box).append("svg").attr("width", size).attr("height", size);
    svg.append("g").attr("class", "gridline").attr("transform", `translate(0,${size - M.bottom})`)
      .call(d3.axisBottom(x).ticks(7).tickSize(-(size - M.top - M.bottom)).tickFormat(""));
    svg.append("g").attr("class", "gridline").attr("transform", `translate(${M.left},0)`)
      .call(d3.axisLeft(y).ticks(7).tickSize(-(size - M.left - M.right)).tickFormat(""));
    svg.append("g").attr("class", "axis").attr("transform", `translate(0,${size - M.bottom})`).call(d3.axisBottom(x).ticks(7).tickSizeOuter(0));
    svg.append("g").attr("class", "axis").attr("transform", `translate(${M.left},0)`).call(d3.axisLeft(y).ticks(7).tickSizeOuter(0));
    svg.append("line").attr("x1", x(0.3)).attr("y1", y(0.3)).attr("x2", x(1.7)).attr("y2", y(1.7)).attr("stroke", "#5a5c63");
    const small = size < 480;
    svg.append("text").attr("class", "corner-tag").attr("x", x(0.34)).attr("y", y(1.64))
      .text(small ? "OWN PAST CLOSER" : "OWN PAST CLOSER · STYLE FOLLOWED THE DRIVER");
    svg.append("text").attr("class", "corner-tag").attr("x", x(1.66)).attr("y", y(0.36)).attr("text-anchor", "end")
      .text(small ? "TEAMMATE CLOSER" : "TEAMMATE CLOSER · CAR DOMINATED");
    svg.append("text").attr("class", "corner-tag").attr("x", size - M.right).attr("y", size - 8).attr("text-anchor", "end")
      .text("DISTANCE TO OWN 2024 SIGNATURE");
    svg.append("text").attr("class", "corner-tag").attr("transform", `translate(12,${M.top}) rotate(-90)`).attr("text-anchor", "end")
      .text("DISTANCE TO 2025 TEAMMATE");

    // points, labels placed where they don't collide
    const placed = [];
    const drivers = state.signatures.drivers;
    for (const d of drivers) {
      const px = x(d.distance_own_2024), py = y(d.distance_teammate_2025);
      const colour = d.changed ? C.orange : C.blue;
      const hollow = d.changed && !d.preregistered_changer;
      const g = svg.append("g").style("cursor", "pointer");
      if (d.driver === state.selected) {
        g.append("circle").attr("cx", px).attr("cy", py).attr("r", 12).attr("fill", "none").attr("stroke", C.ink).attr("stroke-width", 1.5);
      }
      g.append("circle").attr("cx", px).attr("cy", py).attr("r", d.changed ? 7 : 6)
        .attr("fill", hollow ? C.bg : colour).attr("stroke", hollow ? colour : C.bg).attr("stroke-width", hollow ? 2.5 : 2);
      const label = d.driver, w = label.length * 7.5 + 4, h = 12;
      const options = [[10, 0, "start"], [-10, 0, "end"], [0, -14, "middle"], [0, 15, "middle"]];
      let choice = options[0];
      for (const option of options) {
        const lx = option[2] === "start" ? px + option[0] : option[2] === "end" ? px + option[0] - w : px - w / 2;
        const ly = py + option[1] - h / 2;
        if (!placed.some((b) => lx < b.x + b.w && lx + w > b.x && ly < b.y + b.h && ly + h > b.y)) {
          choice = option;
          placed.push({ x: lx, y: ly, w, h });
          break;
        }
      }
      g.append("text").attr("x", px + choice[0]).attr("y", py + choice[1]).attr("text-anchor", choice[2])
        .attr("dominant-baseline", "central").attr("class", "point-label").text(label);
      g.append("circle").attr("cx", px).attr("cy", py).attr("r", 14).attr("fill", "transparent")
        .on("click", () => select(d.driver))
        .on("pointermove", (event) => showTooltip(event, `${d.driver} · ${d.team_2024} 2024 → ${d.team_2025} 2025`, [
          ["To own 2024 signature", d.distance_own_2024.toFixed(3)],
          [`To 2025 teammate (${d.teammate_2025})`, d.distance_teammate_2025.toFixed(3)],
          ["Closer to", d.distance_own_2024 < d.distance_teammate_2025 ? "own past" : "teammate"]]))
        .on("pointerleave", hideTooltip);
    }
  }

  function renderChips() {
    const drivers = [...state.signatures.drivers].sort((a, b) => (b.changed - a.changed) || a.driver.localeCompare(b.driver));
    byId("driver-chips").replaceChildren(...drivers.map((d) => {
      const button = AT.el("button", { type: "button", class: "driver-chip", "aria-pressed": String(d.driver === state.selected) },
        AT.el("span", { class: "chip-bar", style: { background: d.colour_2025 } }), d.driver,
        d.changed ? AT.el("small", {}, "moved") : null);
      button.addEventListener("click", () => select(d.driver));
      return button;
    }));
  }

  function select(code) {
    state.selected = code;
    drawScatter();
    renderChips();
    renderFingerprint();
  }

  // ---------------------------------------------------------------- fingerprint heat strip

  function renderFingerprint() {
    const box = byId("fingerprint");
    box.replaceChildren();
    const d = state.signatures.drivers.find((r) => r.driver === state.selected);
    const columns = state.signatures.columns;
    const featureOrder = state.features.map((f) => f.key);
    const label = Object.fromEntries(state.features.map((f) => [f.key, f.label]));
    // reorder the 30 columns: grouped by corner type, features in their usual order
    const order = [];
    for (const type of CORNER_TYPES) {
      for (const feature of featureOrder) {
        const index = columns.findIndex((c) => c.feature === feature && c.corner_type === type);
        if (index >= 0) order.push(index);
      }
    }
    const ownCloser = d.distance_own_2024 < d.distance_teammate_2025;
    box.append(
      AT.el("div", { class: "fp-head" },
        AT.el("h3", {}, `${d.driver}: ${d.team_2024} 2024 → ${d.team_2025} 2025`),
        AT.el("p", { class: "num" }, `2025 signature to own 2024: ${d.distance_own_2024.toFixed(2)} · to teammate ${d.teammate_2025} 2025: `
          + `${d.distance_teammate_2025.toFixed(2)} → ${ownCloser ? "own past is closer" : "the teammate is closer"}`)));

    const rows = [
      { name: `${d.driver} 2024`, team: d.team_2024, colour: d.colour_2024, values: d.own_2024 },
      { name: `${d.driver} 2025`, team: d.team_2025, colour: d.colour_2025, values: d.own_2025 },
      { name: `${d.teammate_2025} 2025`, team: `${d.team_2025} teammate`, colour: d.colour_2025, values: d.teammate_2025_signature },
    ];
    // on a phone the strip keeps a readable width and scrolls sideways inside its own box
    const holder = AT.el("div", { class: "fingerprint-scroll" });
    box.append(holder);
    const width = Math.max(holder.clientWidth, 760), LABEL = 170, GROUP_GAP = 14, TOP = 30, ROW = 34, GAP = 3, BOTTOM = 92;
    const cell = (width - LABEL - 2 * GROUP_GAP) / order.length;
    const height = TOP + rows.length * (ROW + GAP) + BOTTOM;
    const svg = d3.select(holder).append("svg").attr("width", width).attr("height", height);
    const xOf = (k) => LABEL + k * cell + Math.floor(k / featureOrder.length) * GROUP_GAP;

    CORNER_TYPES.forEach((type, g) => {
      svg.append("text").attr("class", "corner-tag").attr("x", xOf(g * featureOrder.length)).attr("y", 14)
        .text(`${type.toUpperCase()} CORNERS`);
    });
    rows.forEach((row, r) => {
      const y = TOP + r * (ROW + GAP);
      svg.append("rect").attr("x", 0).attr("y", y + 7).attr("width", 4).attr("height", ROW - 14).attr("fill", row.colour);
      svg.append("text").attr("x", 12).attr("y", y + ROW / 2 - 6).attr("class", "tower-code").attr("dominant-baseline", "central").text(row.name);
      svg.append("text").attr("x", 12).attr("y", y + ROW / 2 + 9).attr("class", "tower-team").attr("dominant-baseline", "central").text(row.team);
      order.forEach((index, k) => {
        const value = row.values[index];
        const column = columns[index];
        svg.append("rect").attr("x", xOf(k) + 1).attr("y", y).attr("width", Math.max(1, cell - 2)).attr("height", ROW)
          .attr("fill", value == null ? "#16171b" : HEAT(value))
          .on("pointermove", (event) => showTooltip(event, `${row.name} · ${label[column.feature]}, ${column.corner_type} corners`, [
            ["z-score", value == null ? "no data" : AT.signed(value, 2)],
            ["Positive means", POSITIVE_MEANS[column.feature]],
            ["Compared with", "the average 2024 driver"]]))
          .on("pointerleave", hideTooltip);
      });
    });
    // feature names under the cells
    order.forEach((index, k) => {
      const cx = xOf(k) + cell / 2, cy = TOP + rows.length * (ROW + GAP) + 6;
      svg.append("text").attr("class", "fp-col").attr("transform", `translate(${cx},${cy}) rotate(-55)`)
        .attr("text-anchor", "end").text(SHORT[columns[index].feature]);
    });
    // colour legend
    const legendWidth = 220, lx = width - legendWidth, ly = height - 18;
    const gradient = svg.append("defs").append("linearGradient").attr("id", "heat-gradient");
    [-2, -1, 0, 1, 2].forEach((v) => gradient.append("stop").attr("offset", `${(v + 2) * 25}%`).attr("stop-color", HEAT(v)));
    svg.append("rect").attr("x", lx).attr("y", ly - 6).attr("width", legendWidth).attr("height", 8).attr("fill", "url(#heat-gradient)");
    svg.append("text").attr("class", "corner-tag").attr("x", lx).attr("y", ly + 13).text("−2 SD");
    svg.append("text").attr("class", "corner-tag").attr("x", lx + legendWidth / 2).attr("y", ly + 13).attr("text-anchor", "middle").text("AVERAGE 2024 DRIVER");
    svg.append("text").attr("class", "corner-tag").attr("x", lx + legendWidth).attr("y", ly + 13).attr("text-anchor", "end").text("+2 SD");
    box.append(AT.el("p", { class: "chart-note" },
      "Each cell is one measurement averaged over the season (every weekend counts once), relative to the field at each corner, "
      + "then scaled by how much 2024 drivers differ on it (a z-score). Similar rows = similar style. The distance is the "
      + "root-mean-square difference over all 30 cells."));
  }

  // ---------------------------------------------------------------- start

  async function init() {
    try {
      const [identification, signatures, features] = await Promise.all(
        [AT.getJSON("/api/identification"), AT.getJSON("/api/signatures"), AT.getJSON("/api/features")]);
      state.identification = identification;
      state.signatures = signatures;
      state.features = features.features;
    } catch (error) {
      byId("h3-chart").append(AT.el("p", { class: "message" }, `Could not load the results (${error.message}${error.body && error.body.hint ? "; " + error.body.hint : ""}).`));
      return;
    }
    renderTabs();
    renderH3();
    renderH4();
  }

  let resizeTimer = null;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => { if (state.signatures) { renderH3(); renderH4(); } }, 150);
  });

  init();
})();
