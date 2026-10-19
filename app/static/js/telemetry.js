/* Lap compare page: two qualifying laps on one track coordinate.
 *
 * Where the data comes from (Flask JSON API, see app/routes.py):
 *   /api/sessions                 season and event pickers
 *   /api/sessions/<key>           drivers, kept laps, detected corners, track outline
 *   /api/compare/<key>?a=..&b=..  both laps' measured samples + the gap curve + mini-sectors
 *
 * How it is drawn (D3): every chart shares ONE x scale, the track distance in
 * metres, so a vertical line means "the same place on the track" in all of
 * them. Lines join the measured samples; nothing is smoothed or upsampled.
 */
(() => {
  const page = document.getElementById("telemetry-page");
  const byId = (id) => document.getElementById(id);
  const ui = {
    season: byId("season"), event: byId("event"),
    driverA: byId("driver-a"), lapA: byId("lap-a"), driverB: byId("driver-b"), lapB: byId("lap-b"),
    swap: byId("swap"), cards: byId("cards"), corners: byId("corner-strip"),
    charts: byId("charts"), lights: byId("lights"), map: d3.select("#map"),
    mapCaption: byId("map-caption"), legend: byId("map-legend"), notes: byId("notes"),
    replayControls: byId("replay-controls"), replayReadout: byId("replay-readout"),
  };
  const ALIGNMENT_M = page.dataset.alignmentError;

  // The charts, top to bottom. Heights are the plot heights in pixels.
  const PANELS = [
    { id: "speed", title: "Speed", unit: "km/h", height: 230 },
    { id: "gap", title: "Gap", unit: "seconds, B behind A is up", height: 120 },
    { id: "throttle", title: "Throttle", unit: "%", height: 104 },
    { id: "brake", title: "Brake", unit: "on / off", height: 66 },
    { id: "gear", title: "Gear", unit: "", height: 96 },
  ];
  const M = { left: 52, right: 14, top: 28, bottom: 8 };
  const AXIS_BAND = 34;                 // room for the distance axis under the last chart
  const CORNER_WINDOW = [-300, 200];    // the window the features are measured in (corners.window_bounds)
  const SAMPLE_DOTS_BELOW_M = 1600;     // show the individual samples when zoomed in this far

  const state = { index: [], session: null, a: null, b: null, data: null, domain: null, corner: null, request: 0,
    replay: null, replayView: null, replayMap: null };

  // ---------------------------------------------------------------- small lookups

  const driver = (code) => state.session.drivers.find((d) => d.code === code);
  const lapOf = (pick) => driver(pick.code).laps.find((l) => l.lap === pick.lap);
  const sessionBest = () => Math.min(...state.session.drivers.map((d) => d.laps[0].time_s));

  function parseLap(text) {
    const match = /^([A-Z]{3}):(\d+)$/.exec(text || "");
    return match ? { code: match[1], lap: Number(match[2]) } : null;
  }

  /** Driver A keeps the team colour. Driver B gets a lighter shade when the two
   *  colours are the same team or too alike, and is always drawn dashed. */
  function paints() {
    const A = driver(state.a.code), B = driver(state.b.code);
    let b = B.colour;
    if (A.team === B.team || AT.colourDistance(A.colour, B.colour) < 25) b = AT.mix(B.colour, "#ffffff", 0.5);
    return { a: A.colour, b };
  }

  /** Samples whose distance moves forward (for "value at distance s" lookups; see app/data.increasing_distance). */
  function forward(lap) {
    const out = { s: [], t: [], speed: [], throttle: [], brake: [], gear: [], x: [], y: [] };
    for (let i = 0; i < lap.s.length; i++) {
      if (out.s.length && lap.s[i] <= out.s[out.s.length - 1]) continue;
      for (const key of Object.keys(out)) out[key].push(lap[key][i]);
    }
    return out;
  }

  // ---------------------------------------------------------------- pickers

  function option(value, text, disabled = false) {
    return AT.el("option", { value, disabled }, text);
  }

  function fillSeasons(selectedYear) {
    const years = [...new Set(state.index.map((s) => s.year))].sort((a, b) => b - a);
    ui.season.replaceChildren(...years.map((y) => option(y, y === 2025 ? `${y} · test` : String(y))));
    ui.season.value = selectedYear;
  }

  function fillEvents(year) {
    const rows = state.index.filter((s) => s.year === Number(year)).sort((a, b) => a.round - b.round);
    ui.event.replaceChildren(...rows.map((s) => {
      let text = `R${String(s.round).padStart(2, "0")} · ${s.location}`;
      if (!s.available) text += " · no lap data";
      else if (s.wet) text += " · wet";
      return option(s.key, text, !s.available);
    }));
  }

  function fillDriverAndLaps() {
    const drivers = state.session.drivers;
    const driverOptions = () => drivers.map((d) => option(d.code, `${d.code} · ${d.team}`));
    ui.driverA.replaceChildren(...driverOptions());
    ui.driverB.replaceChildren(...driverOptions());
    ui.driverA.value = state.a.code;
    ui.driverB.value = state.b.code;
    fillLaps(ui.lapA, state.a);
    fillLaps(ui.lapB, state.b);
  }

  function fillLaps(select, pick) {
    const laps = driver(pick.code).laps;
    // fastest first (the export sorts them), so the first entry is the driver's best lap
    select.replaceChildren(...laps.map((l) => option(l.lap,
      `${AT.lapTime(l.time_s)} · L${l.lap}${l.compound ? " · " + l.compound[0] : ""}`)));
    select.value = pick.lap;
  }

  /** A = the session's fastest driver, B = their teammate (or the next fastest driver). */
  function defaultPair() {
    const drivers = state.session.drivers;      // sorted fastest first by the export
    const first = drivers[0];
    const mate = drivers.find((d) => d.code !== first.code && d.team === first.team) || drivers[1];
    return [{ code: first.code, lap: first.laps[0].lap }, { code: mate.code, lap: mate.laps[0].lap }];
  }

  function valid(pick) {
    return pick && driver(pick.code) && driver(pick.code).laps.some((l) => l.lap === pick.lap);
  }

  // ---------------------------------------------------------------- loading

  async function init() {
    try {
      state.index = await AT.getJSON("/api/sessions");
    } catch (error) {
      showMessage(`Could not load the session list (${error.message}).`);
      return;
    }
    const params = new URLSearchParams(location.search);
    const fromUrl = Number(params.get("session"));
    const key = state.index.some((s) => s.key === fromUrl && s.available) ? fromUrl : Number(page.dataset.defaultSession);
    const useDefaults = !fromUrl || key === Number(page.dataset.defaultSession);
    const a = parseLap(params.get("a")) || (useDefaults ? parseLap(page.dataset.defaultA) : null);
    const b = parseLap(params.get("b")) || (useDefaults ? parseLap(page.dataset.defaultB) : null);
    const year = state.index.find((s) => s.key === key).year;
    fillSeasons(year);
    fillEvents(year);
    ui.event.value = key;
    await loadSession(key, a, b);
  }

  async function loadSession(key, a, b) {
    state.session = await AT.getJSON(`/api/sessions/${key}`);
    const [defaultA, defaultB] = defaultPair();
    state.a = valid(a) ? a : defaultA;
    state.b = valid(b) ? b : defaultB;
    state.domain = null;
    state.corner = null;
    fillDriverAndLaps();
    renderCornerStrip();
    await loadCompare();
  }

  async function loadCompare() {
    const query = `a=${state.a.code}:${state.a.lap}&b=${state.b.code}:${state.b.lap}`;
    history.replaceState(null, "", `?session=${state.session.key}&${query}`);
    renderCards();
    if (!state.session.raw_available) {
      state.data = null;
      renderMap();
      showMessage("The raw samples for this season aren't on this computer, so only lap times are shown. "
        + "Build them with python experiments/09_build_dataset.py (2023–2024).");
      return;
    }
    const request = ++state.request;            // ignore answers to older requests
    ui.lights.hidden = false;
    try {
      const data = await AT.getJSON(`/api/compare/${state.session.key}?${query}`);
      if (request !== state.request) return;
      data.a.f = forward(data.a);
      data.b.f = forward(data.b);
      state.data = data;
      renderCharts();
      renderMap();
      renderNotes();
      setupReplay();
    } catch (error) {
      if (request === state.request) showMessage(`Could not load these laps (${error.message}).`);
    } finally {
      if (request === state.request) ui.lights.hidden = true;
    }
  }

  function showMessage(text) {
    ui.charts.querySelectorAll(".chart-panel, .message, .tooltip").forEach((n) => n.remove());
    ui.charts.append(AT.el("p", { class: "message" }, text));
  }

  // ---------------------------------------------------------------- driver cards

  function renderCards() {
    const colours = paints();
    const best = sessionBest();
    const lapA = lapOf(state.a);
    ui.cards.replaceChildren(...["a", "b"].map((which) => {
      const pick = state[which];
      const d = driver(pick.code);
      const lap = lapOf(pick);
      let gap;
      if (which === "b") gap = `${AT.signed(lap.time_s - lapA.time_s)} s to ${state.a.code}`;
      else gap = lap.time_s === best ? "session best" : `${AT.signed(lap.time_s - best)} s to session best`;
      const tyre = lap.compound ? `${lap.compound.toLowerCase()} tyre${lap.tyre_life ? `, age ${lap.tyre_life}` : ""}` : "tyre unknown";
      const rate = (lap.samples / lap.time_s).toFixed(1);
      return AT.el("article", { class: "card" },
        AT.el("span", { class: "bar", style: { background: colours[which] } }),
        AT.el("span", { class: "code" }, d.code),
        AT.el("div", {},
          AT.el("div", { class: "who" }, `${which.toUpperCase()} · ${d.name}`),
          AT.el("div", { class: "meta" }, `${d.team} · lap ${lap.lap} · ${tyre} · ${lap.samples} samples (${rate}/s)`)),
        AT.el("div", {},
          AT.el("div", { class: "time num" + (lap.time_s === best ? " best" : "") }, AT.lapTime(lap.time_s)),
          AT.el("div", { class: "gap num" }, gap)));
    }));
  }

  // ---------------------------------------------------------------- corner strip

  function renderCornerStrip() {
    const buttons = [cornerButton("Full lap", null, "")];
    for (const corner of state.session.corners) {
      buttons.push(cornerButton(corner.name, corner, `${corner.type} · ${corner.min_speed_kmh}`));
    }
    ui.corners.replaceChildren(...buttons);
  }

  function cornerButton(label, corner, detail) {
    const pressed = corner ? state.corner === corner.name : state.domain === null;
    const button = AT.el("button", { type: "button", class: "corner-btn", "aria-pressed": String(pressed),
      title: corner ? `Zoom to ${corner.name}: ${corner.s_m.toFixed(0)} m, minimum ${corner.min_speed_kmh} km/h on the reference lap` : "Show the whole lap" },
    label, detail ? AT.el("small", {}, detail) : null);
    button.addEventListener("click", () => {
      if (corner) {
        state.domain = [corner.s_m + CORNER_WINDOW[0], corner.s_m + CORNER_WINDOW[1]];
        state.corner = corner.name;
      } else {
        state.domain = null;
        state.corner = null;
      }
      refreshView();
    });
    return button;
  }

  function refreshView() {
    renderCornerStrip();
    if (state.data) {
      renderCharts();
      renderMap();
    }
  }

  // ---------------------------------------------------------------- charts

  function renderCharts() {
    const { a, b, delta } = state.data;
    const colours = paints();
    const length = state.session.track.length_m;
    const domain = state.domain || [0, length];
    ui.charts.querySelectorAll(".chart-panel, .message, .tooltip").forEach((n) => n.remove());
    const width = ui.charts.clientWidth;
    const x = d3.scaleLinear().domain(domain).range([M.left, width - M.right]);
    const inView = (s) => s >= domain[0] && s <= domain[1];
    const series = [
      { key: "a", lap: a, colour: colours.a, dash: null, code: state.a.code },
      { key: "b", lap: b, colour: colours.b, dash: "6 4", code: state.b.code },
    ];
    const showDots = domain[1] - domain[0] <= SAMPLE_DOTS_BELOW_M;
    const charts = {};

    // legend: which line is which driver (colour AND line style, never colour alone)
    const lineKey = (colour, dash) => {
      const key = AT.el("span", { class: "key" });
      d3.select(key).append("svg").attr("width", 24).attr("height", 10).append("line")
        .attr("x1", 1).attr("x2", 23).attr("y1", 5).attr("y2", 5).attr("stroke", colour).attr("stroke-width", 2.5)
        .attr("stroke-dasharray", dash);
      return key;
    };
    const legendA = lineKey(colours.a, null), legendB = lineKey(colours.b, "6 4");
    legendA.append(`${state.a.code} (A), lap ${state.a.lap}`);
    legendB.append(`${state.b.code} (B), lap ${state.b.lap}`);
    ui.charts.append(AT.el("div", { class: "chart-panel chart-legend" }, legendA, legendB,
      AT.el("span", { class: "key muted" }, showDots ? "dots = measured samples" : "zoom in to see the measured samples")));

    // ruler strip above the charts: the names of the detected braking zones
    const ruler = AT.el("div", { class: "chart-panel ruler" });
    ui.charts.append(ruler);
    const rulerSvg = d3.select(ruler).append("svg").attr("width", width).attr("height", 22);
    for (const corner of state.session.corners) {
      if (!inView(corner.s_m)) continue;
      rulerSvg.append("text").attr("class", "corner-tag").attr("x", x(corner.s_m)).attr("y", 15)
        .attr("text-anchor", "middle").attr("fill", state.corner === corner.name ? "#f2f1ed" : null).text(corner.name);
    }

    for (const [index, panel] of PANELS.entries()) {
      const last = index === PANELS.length - 1;
      const height = panel.height + (last ? AXIS_BAND : 0);
      const holder = AT.el("div", { class: "chart-panel" },
        AT.el("div", { class: "chart-title" }, AT.el("b", {}, panel.title), panel.unit ? ` · ${panel.unit}` : ""));
      ui.charts.append(holder);
      const svg = d3.select(holder).append("svg").attr("width", width).attr("height", height);
      const clipId = `clip-${panel.id}`;
      svg.append("clipPath").attr("id", clipId).append("rect")
        .attr("x", M.left).attr("y", 0).attr("width", width - M.left - M.right).attr("height", panel.height);
      const grid = svg.append("g");
      const plot = svg.append("g").attr("clip-path", `url(#${clipId})`);
      charts[panel.id] = { svg, grid, plot, height: panel.height };

      // braking zones: a hairline at each detected corner (named in the ruler above)
      for (const corner of state.session.corners) {
        if (!inView(corner.s_m)) continue;
        plot.append("line").attr("class", "corner-rule").attr("x1", x(corner.s_m)).attr("x2", x(corner.s_m))
          .attr("y1", 0).attr("y2", panel.height);
      }
      if (last) {
        const axis = d3.axisBottom(x).ticks(Math.max(3, Math.floor(width / 110))).tickSizeOuter(0)
          .tickFormat((d) => d3.format(",")(d));
        svg.append("g").attr("class", "axis").attr("transform", `translate(0,${panel.height})`).call(axis);
        svg.append("text").attr("class", "corner-tag").attr("x", width - M.right).attr("y", panel.height + 30)
          .attr("text-anchor", "end").text("DISTANCE FROM THE LINE · METRES");
      }
    }

    // a y axis + horizontal gridlines for one chart
    function yAxis(chart, y, ticks, format) {
      chart.grid.append("g").attr("class", "gridline").attr("transform", `translate(${M.left},0)`)
        .call(d3.axisLeft(y).tickValues(ticks).tickSize(-(width - M.left - M.right)).tickFormat(""));
      chart.grid.append("g").attr("class", "axis").attr("transform", `translate(${M.left},0)`)
        .call(d3.axisLeft(y).tickValues(ticks).tickSize(0).tickPadding(8).tickFormat(format)).select(".domain").remove();
    }
    const visible = (lap, key) => lap.s.map((s, i) => [s, lap[key][i]]).filter(([s]) => s >= domain[0] - 60 && s <= domain[1] + 60);

    // --- speed
    {
      const chart = charts.speed;
      const values = [...visible(a, "speed"), ...visible(b, "speed")].map((p) => p[1]);
      const y = d3.scaleLinear().domain([d3.min(values) - 8, d3.max(values) + 8]).nice()
        .range([chart.height - M.bottom, M.top]);
      yAxis(chart, y, y.ticks(5), (d) => d);
      for (const sr of series) {
        chart.plot.append("path").attr("fill", "none").attr("stroke", sr.colour).attr("stroke-width", 2)
          .attr("stroke-linejoin", "round").attr("stroke-linecap", "round").attr("stroke-dasharray", sr.dash)
          .attr("d", d3.line().x((d, i) => x(sr.lap.s[i])).y((d) => y(d))(sr.lap.speed));
        if (showDots) {
          chart.plot.append("g").selectAll("circle").data(sr.lap.s.map((s, i) => [s, sr.lap.speed[i]]).filter(([s]) => inView(s)))
            .join("circle").attr("cx", (d) => x(d[0])).attr("cy", (d) => y(d[1])).attr("r", 2.6)
            .attr("fill", sr.colour).attr("stroke", "#0b0c0e").attr("stroke-width", 1.5);
        }
      }
      charts.speed.y = y;
    }

    // --- gap (B relative to A)
    {
      const chart = charts.gap;
      const points = delta.s.map((s, i) => [s, delta.d[i]]).filter(([s]) => s >= domain[0] - 20 && s <= domain[1] + 20);
      const values = points.map((p) => p[1]);
      let low = Math.min(0, d3.min(values) ?? 0), high = Math.max(0, d3.max(values) ?? 0);
      const pad = Math.max(0.02, (high - low) * 0.12);
      const y = d3.scaleLinear().domain([low - pad, high + pad]).range([chart.height - M.bottom, M.top]);
      yAxis(chart, y, y.ticks(4), (d) => (d === 0 ? "0" : AT.signed(d, 2)));
      chart.plot.append("line").attr("x1", M.left).attr("x2", width - M.right).attr("y1", y(0)).attr("y2", y(0))
        .attr("stroke", "#4a4c53");
      chart.plot.append("path").attr("fill", colours.b).attr("fill-opacity", 0.1)
        .attr("d", d3.area().x((d) => x(d[0])).y0(y(0)).y1((d) => y(d[1]))(points));
      chart.plot.append("path").attr("fill", "none").attr("stroke", colours.b).attr("stroke-width", 2)
        .attr("d", d3.line().x((d) => x(d[0])).y((d) => y(d[1]))(points));
      charts.gap.y = y;
    }

    // --- throttle
    {
      const chart = charts.throttle;
      const y = d3.scaleLinear().domain([0, 100]).range([chart.height - M.bottom, M.top]);
      yAxis(chart, y, [0, 50, 100], (d) => d);
      for (const sr of series) {
        chart.plot.append("path").attr("fill", "none").attr("stroke", sr.colour).attr("stroke-width", 2)
          .attr("stroke-linejoin", "round").attr("stroke-dasharray", sr.dash)
          .attr("d", d3.line().x((d, i) => x(sr.lap.s[i])).y((d) => y(d))(sr.lap.throttle));
      }
    }

    // --- brake: one row per driver, a block wherever the brake flag is on
    {
      const chart = charts.brake;
      const rows = d3.scaleBand().domain(["a", "b"]).range([M.top - 4, chart.height - M.bottom]).paddingInner(0.35);
      for (const sr of series) {
        chart.svg.append("text").attr("class", "corner-tag").attr("x", M.left - 8).attr("y", rows(sr.key) + rows.bandwidth() / 2)
          .attr("text-anchor", "end").attr("dominant-baseline", "central").text(sr.code);
        chart.plot.append("rect").attr("x", M.left).attr("width", width - M.left - M.right)
          .attr("y", rows(sr.key)).attr("height", rows.bandwidth()).attr("fill", "#16171b");
        // one block per run of "on" samples; the flag holds until the next sample says otherwise
        const lap = sr.lap;
        let i = 0;
        while (i < lap.s.length) {
          if (!lap.brake[i]) { i += 1; continue; }
          let j = i;
          while (j + 1 < lap.s.length && lap.brake[j + 1]) j += 1;
          const end = j + 1 < lap.s.length ? lap.s[j + 1] : lap.s[j] + 5;
          chart.plot.append("rect").attr("x", x(lap.s[i])).attr("width", Math.max(1, x(end) - x(lap.s[i])))
            .attr("y", rows(sr.key)).attr("height", rows.bandwidth()).attr("fill", sr.colour);
          i = j + 1;
        }
      }
    }

    // --- gear: a step line (a gear holds until the next sample)
    {
      const chart = charts.gear;
      const y = d3.scaleLinear().domain([1, 8]).range([chart.height - M.bottom, M.top]);
      yAxis(chart, y, [2, 4, 6, 8], (d) => d);
      for (const sr of series) {
        chart.plot.append("path").attr("fill", "none").attr("stroke", sr.colour).attr("stroke-width", 2)
          .attr("stroke-dasharray", sr.dash).attr("d",
            d3.line().curve(d3.curveStepAfter).x((d, i) => x(sr.lap.s[i])).y((d) => y(d))(sr.lap.gear));
      }
    }

    attachInteraction(charts, x, domain, width, series);

    // replay position lines: where each car is at the replay time (A solid, B dashed)
    const lines = [];
    for (const chart of Object.values(charts)) {
      const pair = {};
      for (const sr of series) {
        pair[sr.key] = chart.svg.append("line").attr("y1", 0).attr("y2", chart.height).attr("stroke", sr.colour)
          .attr("stroke-width", 1.5).attr("stroke-dasharray", sr.dash).style("pointer-events", "none").style("display", "none");
      }
      lines.push(pair);
    }
    state.replayView = { x, domain, lines };
    if (state.replay) state.replay.render();
  }

  // ---------------------------------------------------------------- hover readout, drag to zoom

  function attachInteraction(charts, x, domain, width, series) {
    const tooltip = AT.el("div", { class: "tooltip", hidden: true });
    ui.charts.append(tooltip);
    const lines = [];
    const brushes = [];
    for (const chart of Object.values(charts)) {
      lines.push(chart.svg.append("line").attr("class", "crosshair").attr("y1", 0).attr("y2", chart.height).style("display", "none"));
      brushes.push(chart.svg.append("rect").attr("y", 0).attr("height", chart.height)
        .attr("fill", "#f2f1ed").attr("fill-opacity", 0.07).style("display", "none"));
    }
    let dragFrom = null;

    function pointerS(event, svgNode) {
      const [mx] = d3.pointer(event, svgNode);
      return Math.max(domain[0], Math.min(domain[1], x.invert(Math.max(M.left, Math.min(width - M.right, mx)))));
    }

    function update(s, event) {
      const px = x(s);
      for (const line of lines) line.attr("x1", px).attr("x2", px).style("display", null);
      if (dragFrom !== null) {
        const left = Math.min(x(dragFrom), px), right = Math.max(x(dragFrom), px);
        for (const brush of brushes) brush.attr("x", left).attr("width", right - left).style("display", null);
      }
      fillTooltip(tooltip, s, series);
      tooltip.hidden = false;
      const box = ui.charts.getBoundingClientRect();
      const left = event.clientX - box.left + 16;
      tooltip.style.left = `${left + 190 > box.width ? left - 210 : left}px`;
      tooltip.style.top = `${Math.max(0, Math.min(event.clientY - box.top - 20, box.height - 190))}px`;
      showMarkers(s);
    }

    function hide() {
      for (const line of lines) line.style("display", "none");
      tooltip.hidden = true;
      showMarkers(null);
    }

    for (const chart of Object.values(charts)) {
      const overlay = chart.svg.append("rect").attr("x", M.left).attr("y", 0)
        .attr("width", width - M.left - M.right).attr("height", chart.height)
        .attr("fill", "transparent").style("cursor", "crosshair").style("touch-action", "none");
      const node = chart.svg.node();
      overlay.on("pointermove", (event) => update(pointerS(event, node), event));
      overlay.on("pointerleave", () => { if (dragFrom === null) hide(); });
      overlay.on("pointerdown", (event) => {
        dragFrom = pointerS(event, node);
        overlay.node().setPointerCapture(event.pointerId);
      });
      overlay.on("pointerup", (event) => {
        if (dragFrom === null) return;
        const to = pointerS(event, node);
        const from = dragFrom;
        dragFrom = null;
        for (const brush of brushes) brush.style("display", "none");
        if (Math.abs(x(to) - x(from)) > 12) {        // a real drag, not a click
          state.domain = [Math.min(from, to), Math.max(from, to)];
          state.corner = null;
          refreshView();
        } else if (state.replay) {                   // a click: move the replay to when car A was here
          const a = state.data.a.f;
          state.replay.seek(AT.interp(to, a.s, a.t));
        }
      });
      overlay.on("dblclick", () => {
        state.domain = null;
        state.corner = null;
        refreshView();
      });
    }
  }

  function valuesAt(lap, s) {
    const f = lap.f;
    return {
      speed: Math.round(AT.interp(s, f.s, f.speed)),
      throttle: Math.round(AT.interp(s, f.s, f.throttle)),
      brake: AT.stepValue(s, f.s, f.brake),
      gear: AT.stepValue(s, f.s, f.gear),
    };
  }

  function fillTooltip(tooltip, s, series) {
    const { delta } = state.data;
    const near = state.session.corners.find((c) => s >= c.s_m + CORNER_WINDOW[0] && s <= c.s_m + CORNER_WINDOW[1]);
    const values = series.map((sr) => valuesAt(sr.lap, s));
    const gap = s >= delta.s[0] && s <= delta.s[delta.s.length - 1] ? AT.interp(s, delta.s, delta.d) : null;
    const row = (label, format) => AT.el("tr", {}, AT.el("td", { class: "k" }, label),
      ...values.map((v) => AT.el("td", { class: "v num" }, format(v))));
    tooltip.replaceChildren(
      AT.el("div", { class: "tt-head" }, `${d3.format(",")(Math.round(s))} m${near ? ` · ${near.name} zone` : ""}`),
      AT.el("table", {},
        AT.el("tr", {}, AT.el("td", {}),
          ...series.map((sr) => AT.el("td", { class: "v" },
            AT.el("span", { class: "linekey" + (sr.dash ? " dashed" : ""), style: { borderTopColor: sr.colour } }), sr.code))),
        row("Speed", (v) => `${v.speed}`),
        row("Throttle", (v) => `${v.throttle}%`),
        row("Brake", (v) => (v.brake ? "on" : "off")),
        row("Gear", (v) => `${v.gear}`),
        AT.el("tr", {}, AT.el("td", { class: "k" }, "Gap"), AT.el("td", {}),
          AT.el("td", { class: "v num" }, gap === null ? "–" : `${AT.signed(gap, 3)} s`))));
  }

  // ---------------------------------------------------------------- track map

  const MAP = { W: 400, H: 300, PAD: 26 };
  let markers = null;

  function renderMap() {
    const svg = ui.map;
    svg.selectAll("*").remove();
    const track = state.session.track;
    const fit = AT.fitTrack(track.x, track.y, MAP.W, MAP.H, MAP.PAD);
    const at = (s) => [fit.x(AT.interp(s, track.s, track.x)), fit.y(AT.interp(s, track.s, track.y))];
    const points = track.x.map((x, i) => [fit.x(x), fit.y(track.y[i])]);
    const line = d3.line().curve(d3.curveCatmullRom.alpha(0.5));
    svg.append("path").attr("d", line(points) + "Z").attr("fill", "none").attr("stroke", "#1f2126")
      .attr("stroke-width", 12).attr("stroke-linejoin", "round");

    const colours = paints();
    const legend = [];
    if (state.data) {
      const sectors = state.data.mini_sectors;
      for (const [i, sector] of sectors.entries()) {
        const inside = track.s.map((s, k) => [s, k]).filter(([s]) => s > sector.start_m && s < sector.end_m)
          .map(([, k]) => points[k]);
        const segment = [at(sector.start_m), ...inside, at(sector.end_m)];
        const colour = sector.faster === "a" ? colours.a : sector.faster === "b" ? colours.b : "#55575f";
        const path = svg.append("path").attr("d", line(segment)).attr("fill", "none").attr("stroke", colour)
          .attr("stroke-width", 5).attr("stroke-linecap", "butt");
        const who = sector.faster === "a" ? `${state.a.code} faster by ${Math.abs(sector.gain_s).toFixed(3)} s`
          : sector.faster === "b" ? `${state.b.code} faster by ${Math.abs(sector.gain_s).toFixed(3)} s`
            : `within ${(0.02).toFixed(2)} s (measurement error)`;
        path.append("title").text(`Mini-sector ${i + 1}, ${sector.start_m.toFixed(0)}–${sector.end_m.toFixed(0)} m: ${who}`);
      }
      const counts = { a: 0, b: 0, even: 0 };
      for (const sector of sectors) counts[sector.faster] += 1;
      ui.mapCaption.textContent = `${sectors.length} mini-sectors`;
      legend.push(key(colours.a, `${state.a.code} faster (${counts.a})`),
        key(colours.b, `${state.b.code} faster (${counts.b})`),
        key("#55575f", `even, under 0.02 s (${counts.even})`));
    } else {
      svg.append("path").attr("d", line(points) + "Z").attr("fill", "none").attr("stroke", "#3d3f46").attr("stroke-width", 1.4);
      ui.mapCaption.textContent = "";
    }
    ui.legend.replaceChildren(...legend);

    // the zoomed stretch, outlined in white
    if (state.domain) {
      const inside = track.s.map((s, k) => [s, k]).filter(([s]) => s > state.domain[0] && s < state.domain[1]).map(([, k]) => points[k]);
      const stretch = [at(Math.max(0, state.domain[0])), ...inside, at(Math.min(track.length_m, state.domain[1]))];
      svg.append("path").attr("d", line(stretch)).attr("fill", "none").attr("stroke", "#f2f1ed")
        .attr("stroke-width", 1.6).attr("stroke-opacity", 0.9);
    }

    // start/finish tick and corner names
    const [p0, p1] = [points[0], points[3]];
    const len = Math.hypot(p1[0] - p0[0], p1[1] - p0[1]) || 1;
    const nx = -(p1[1] - p0[1]) / len, ny = (p1[0] - p0[0]) / len;
    svg.append("line").attr("x1", p0[0] - nx * 9).attr("y1", p0[1] - ny * 9).attr("x2", p0[0] + nx * 9)
      .attr("y2", p0[1] + ny * 9).attr("stroke", "#f2f1ed").attr("stroke-width", 2);
    const cx = d3.mean(points, (p) => p[0]), cy = d3.mean(points, (p) => p[1]);
    for (const corner of state.session.corners) {
      const [px, py] = at(corner.s_m);
      const dx = px - cx, dy = py - cy, d = Math.hypot(dx, dy) || 1;
      svg.append("text").attr("class", "corner-tag").attr("x", px + (dx / d) * 15).attr("y", py + (dy / d) * 15)
        .attr("text-anchor", "middle").attr("dominant-baseline", "central")
        .attr("fill", state.corner === corner.name ? "#f2f1ed" : null).text(corner.name);
    }

    // hover markers (moved by the charts' crosshair)
    markers = { fit, a: null, b: null };
    state.replayMap = null;
    if (state.data) {
      for (const which of ["a", "b"]) {
        markers[which] = svg.append("circle").attr("r", 5.5).attr("fill", colours[which])
          .attr("stroke", "#0b0c0e").attr("stroke-width", 2.5).style("display", "none");
      }
      // replay cars: a short trail and a dot each (B's trail dashed, like its chart lines)
      const cars = {};
      for (const which of ["a", "b"]) {
        cars[which] = {
          trail: svg.append("path").attr("fill", "none").attr("stroke", colours[which]).attr("stroke-width", 3)
            .attr("stroke-linecap", "round").attr("stroke-opacity", 0.6).attr("stroke-dasharray", which === "b" ? "5 4" : null),
          dot: svg.append("circle").attr("r", 6.5).attr("fill", colours[which]).attr("stroke", "#0b0c0e").attr("stroke-width", 2.5),
        };
      }
      // click the map: jump the replay to when car A passed the nearest point
      const lapA = state.data.a;
      const screenX = lapA.x.map((v) => fit.x(v)), screenY = lapA.y.map((v) => fit.y(v));
      svg.style("cursor", "pointer").on("click", (event) => {
        const [px, py] = d3.pointer(event, svg.node());
        if (state.replay) state.replay.seek(lapA.t[AT.nearestSample(screenX, screenY, px, py)]);
      });
      state.replayMap = { fit, cars };
      if (state.replay) state.replay.render();
    }
  }

  // ---------------------------------------------------------------- replay

  function setupReplay() {
    if (state.replay) state.replay.destroy();
    const duration = Math.max(lapOf(state.a).time_s, lapOf(state.b).time_s);
    state.replay = new AT.Replay(ui.replayControls, { duration, onFrame: drawReplay });
    state.replay.seek(0);
  }

  /** Draw both cars at replay time t: map dots and trails, chart position lines, live readout. */
  function drawReplay(t) {
    if (!state.data || !state.replayMap) return;
    const TRAIL_S = 1.2;
    const now = {};
    for (const which of ["a", "b"]) {
      const lap = state.data[which];
      const tc = Math.min(t, lapOf(state[which]).time_s);       // a finished car waits at the line
      now[which] = { s: AT.interp(tc, lap.t, lap.s), speed: AT.interp(tc, lap.t, lap.speed) };
      const { fit, cars } = state.replayMap;
      const trail = [];
      for (let ts = Math.max(lap.t[0], tc - TRAIL_S); ts <= tc; ts += 0.05) {
        trail.push([fit.x(AT.interp(ts, lap.t, lap.x)), fit.y(AT.interp(ts, lap.t, lap.y))]);
      }
      const px = fit.x(AT.interp(tc, lap.t, lap.x)), py = fit.y(AT.interp(tc, lap.t, lap.y));
      trail.push([px, py]);
      cars[which].trail.attr("d", trail.length > 1 ? d3.line()(trail) : null);
      cars[which].dot.attr("cx", px).attr("cy", py);
      if (state.replayView) {
        const { x, domain, lines } = state.replayView;
        const inside = now[which].s >= domain[0] && now[which].s <= domain[1];
        for (const pair of lines) {
          pair[which].attr("x1", x(now[which].s)).attr("x2", x(now[which].s)).style("display", inside && t > 0 ? null : "none");
        }
      }
    }
    // gap at car A's position (time) and how far behind B is on track (metres)
    const delta = state.data.delta;
    const gap = now.a.s >= delta.s[0] && now.a.s <= delta.s[delta.s.length - 1] ? AT.interp(now.a.s, delta.s, delta.d) : null;
    const metres = now.a.s - now.b.s;
    ui.replayReadout.replaceChildren(
      AT.el("span", {}, `${state.a.code} `, AT.el("b", {}, `${Math.round(now.a.speed)} km/h`)),
      AT.el("span", {}, `${state.b.code} `, AT.el("b", {}, `${Math.round(now.b.speed)} km/h`)),
      AT.el("span", {}, "gap ", AT.el("b", {}, gap === null ? "–" : `${AT.signed(gap, 3)} s`),
        t > 0 ? ` (${state.b.code} ${Math.abs(metres).toFixed(0)} m ${metres >= 0 ? "behind" : "ahead"})` : ""));
  }

  function key(colour, text) {
    return AT.el("span", { class: "key" }, AT.el("span", { class: "swatch", style: { background: colour } }), text);
  }

  function showMarkers(s) {
    if (!markers || !state.data) return;
    for (const which of ["a", "b"]) {
      if (!markers[which]) continue;
      if (s === null) { markers[which].style("display", "none"); continue; }
      const f = state.data[which].f;
      markers[which].attr("cx", markers.fit.x(AT.interp(s, f.s, f.x))).attr("cy", markers.fit.y(AT.interp(s, f.s, f.y)))
        .style("display", null);
    }
  }

  // ---------------------------------------------------------------- notes

  function renderNotes() {
    const lapA = lapOf(state.a), lapB = lapOf(state.b);
    const gapCurve = state.data.delta.d[state.data.delta.d.length - 1];
    ui.notes.replaceChildren(
      AT.el("p", {}, `Lines join the measured samples: ${lapA.samples} for ${state.a.code} and ${lapB.samples} for ${state.b.code}, `
        + `about ${(lapA.samples / lapA.time_s).toFixed(1)} per second. Zoom into a braking zone to see each one.`),
      AT.el("p", {}, "Brake is on/off in the public feed: it shows when the pedal is pressed, not how hard."),
      AT.el("p", {}, "The gap compares both laps' clocks at the same distance, measured by integrating speed. "
        + `Check: it reaches ${AT.signed(gapCurve)} s just before the line; the official lap times differ by `
        + `${AT.signed(lapB.time_s - lapA.time_s)} s.`),
      AT.el("p", {}, `Distance on the charts is speed integrated over time, corrected by the car's track position `
        + `(a complementary filter, about ±${ALIGNMENT_M} m).`),
      AT.el("p", {}, "C1, C2, … are the braking zones detected on this session's fastest lap, not official turn numbers."));
  }

  // ---------------------------------------------------------------- events

  ui.season.addEventListener("change", async () => {
    fillEvents(ui.season.value);
    const first = [...ui.event.options].find((o) => !o.disabled);
    if (!first) return;
    ui.event.value = first.value;
    await loadSession(Number(first.value), null, null);
  });
  ui.event.addEventListener("change", () => loadSession(Number(ui.event.value), null, null));
  ui.driverA.addEventListener("change", () => {
    state.a = { code: ui.driverA.value, lap: driver(ui.driverA.value).laps[0].lap };
    fillLaps(ui.lapA, state.a);
    loadCompare();
  });
  ui.driverB.addEventListener("change", () => {
    state.b = { code: ui.driverB.value, lap: driver(ui.driverB.value).laps[0].lap };
    fillLaps(ui.lapB, state.b);
    loadCompare();
  });
  ui.lapA.addEventListener("change", () => { state.a.lap = Number(ui.lapA.value); loadCompare(); });
  ui.lapB.addEventListener("change", () => { state.b.lap = Number(ui.lapB.value); loadCompare(); });
  ui.swap.addEventListener("click", () => {
    [state.a, state.b] = [state.b, state.a];
    fillDriverAndLaps();
    loadCompare();
  });
  let resizeTimer = null;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => { if (state.data) renderCharts(); }, 150);
  });

  init();
})();
