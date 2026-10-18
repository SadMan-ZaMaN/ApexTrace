/* Home page hero: two fastest qualifying laps replayed in real time.
 *
 * Everything drawn comes from the timing feed: the track outline is the
 * reference lap's own X/Y, and each car's position at time t is interpolated
 * between its measured samples (about 4 per second). Nothing is invented: when
 * playback reaches a lap's end, that car stops and shows its lap time.
 */
(async () => {
  const W = 800, H = 450, PAD = 36;
  const TRAIL_S = 1.4;          // seconds of trail behind each car
  const HOLD_S = 3.5;           // pause at the end before the replay restarts
  const svg = d3.select("#hero-svg");
  const title = document.getElementById("hero-title");
  const clock = document.getElementById("hero-clock");
  const readout = document.getElementById("hero-readout");

  let hero;
  try {
    hero = await AT.getJSON("/api/hero");
  } catch (error) {
    title.textContent = "Lap data unavailable";
    return;
  }
  title.textContent = `${hero.circuit} · ${hero.year} qualifying`;

  // ---------------------------------------------------------------- colours
  const cars = hero.cars;
  cars[0].paint = cars[0].colour;
  // the second car of the same team gets a lighter shade of the team colour
  cars[1].paint = cars[0].team === cars[1].team ? AT.mix(cars[1].colour, "#ffffff", 0.5) : cars[1].colour;

  // ---------------------------------------------------------------- track
  const track = hero.track;
  const fit = AT.fitTrack(track.x, track.y, W, H, PAD);
  const points = track.x.map((x, i) => [fit.x(x), fit.y(track.y[i])]);
  const path = d3.line().curve(d3.curveCatmullRom.alpha(0.5))(points) + "Z";

  svg.append("path").attr("d", path).attr("fill", "none").attr("stroke", "#1f2126")
    .attr("stroke-width", 15).attr("stroke-linejoin", "round");
  svg.append("path").attr("d", path).attr("fill", "none").attr("stroke", "#3d3f46")
    .attr("stroke-width", 1.3).attr("stroke-linejoin", "round");

  // start/finish line: a short tick across the track at the first point
  const [p0, p1] = [points[0], points[3]];
  const len = Math.hypot(p1[0] - p0[0], p1[1] - p0[1]) || 1;
  const nx = -(p1[1] - p0[1]) / len, ny = (p1[0] - p0[0]) / len;   // normal to the direction of travel
  svg.append("line").attr("x1", p0[0] - nx * 11).attr("y1", p0[1] - ny * 11)
    .attr("x2", p0[0] + nx * 11).attr("y2", p0[1] + ny * 11)
    .attr("stroke", "#f2f1ed").attr("stroke-width", 2.5);

  // detected braking zones: labelled just outside the track
  const cx = d3.mean(points, (p) => p[0]), cy = d3.mean(points, (p) => p[1]);
  const corners = svg.append("g");
  for (const corner of hero.corners) {
    const px = fit.x(AT.interp(corner.s_m, track.s, track.x));
    const py = fit.y(AT.interp(corner.s_m, track.s, track.y));
    const dx = px - cx, dy = py - cy, d = Math.hypot(dx, dy) || 1;
    corners.append("circle").attr("cx", px).attr("cy", py).attr("r", 2.2).attr("fill", "#85847e");
    corners.append("text").attr("x", px + (dx / d) * 17).attr("y", py + (dy / d) * 17)
      .attr("text-anchor", "middle").attr("dominant-baseline", "central")
      .attr("class", "corner-tag").text(corner.name);
  }

  // ---------------------------------------------------------------- cars
  const layer = svg.append("g");
  for (const [k, car] of cars.entries()) {
    car.trail = layer.append("path").attr("fill", "none").attr("stroke", car.paint).attr("stroke-width", 3.2)
      .attr("stroke-linecap", "round").attr("stroke-opacity", 0.55)
      .attr("stroke-dasharray", k === 1 ? "5 4" : null);
    car.dot = layer.append("circle").attr("r", 6.5).attr("fill", car.paint)
      .attr("stroke", "#0b0c0e").attr("stroke-width", 2.5);
    car.tag = layer.append("text").attr("class", "corner-tag").attr("fill", "#f2f1ed").style("font-size", "13px")
      .style("paint-order", "stroke").attr("stroke", "#0b0c0e").attr("stroke-width", 4)
      .attr("text-anchor", k === 0 ? "end" : "start").text(car.code);
  }

  // readout rows below the track (bar | code + team | speed or lap time | gap)
  for (const [k, car] of cars.entries()) {
    car.speedNode = AT.el("span", { class: "speed num" });
    car.gapNode = AT.el("span", { class: "team num" });
    const row = AT.el("div", { class: "readout-car" },
      AT.el("span", { class: "bar", style: { background: car.paint } }),
      AT.el("div", {}, AT.el("div", { class: "code" }, car.code), AT.el("div", { class: "team" }, car.team)),
      AT.el("div", { style: { textAlign: "right" } }, car.speedNode, AT.el("div", {}, car.gapNode)));
    readout.append(row);
  }

  // distance -> time lookup for the gap, using only forward-moving samples
  function forward(s, t) {
    const fs = [], ft = [];
    for (let i = 0; i < s.length; i++) if (!fs.length || s[i] > fs[fs.length - 1]) { fs.push(s[i]); ft.push(t[i]); }
    return { s: fs, t: ft };
  }
  const lookupA = forward(cars[0].s, cars[0].t);
  const fastest = Math.min(...cars.map((c) => c.lap_time_s));

  function draw(t) {
    for (const [k, car] of cars.entries()) {
      const tc = Math.min(t, car.lap_time_s);
      const x = fit.x(AT.interp(tc, car.t, car.x)), y = fit.y(AT.interp(tc, car.t, car.y));
      const trail = [];
      for (let ts = Math.max(car.t[0], tc - TRAIL_S); ts <= tc; ts += 0.05) {
        trail.push([fit.x(AT.interp(ts, car.t, car.x)), fit.y(AT.interp(ts, car.t, car.y))]);
      }
      trail.push([x, y]);
      car.trail.attr("d", trail.length > 1 ? d3.line()(trail) : null);
      car.dot.attr("cx", x).attr("cy", y);
      car.tag.attr("x", x + (k === 0 ? -10 : 10)).attr("y", y + (k === 0 ? -9 : 15));

      const finished = t >= car.lap_time_s;
      car.speedNode.textContent = "";
      if (finished) {
        car.speedNode.textContent = AT.lapTime(car.lap_time_s);
        car.speedNode.style.color = car.lap_time_s === fastest ? "var(--purple)" : "";
      } else {
        car.speedNode.style.color = "";
        car.speedNode.append(String(Math.round(AT.interp(tc, car.t, car.speed))), AT.el("small", {}, "km/h"));
      }
      if (k === 0) {
        car.gapNode.textContent = finished ? "fastest lap" : "reference";
      } else if (finished) {
        car.gapNode.textContent = `${AT.signed(car.lap_time_s - cars[0].lap_time_s)} s`;
      } else {
        // gap = how much later than car A this car reached its current position
        const s = AT.interp(tc, car.t, car.s);
        const timeA = AT.interp(s, lookupA.s, lookupA.t);
        car.gapNode.textContent = `gap ${AT.signed(tc - timeA, 2)} s`;
      }
    }
    clock.textContent = AT.lapTime(Math.min(t, Math.max(...cars.map((c) => c.lap_time_s))));
  }

  const duration = Math.max(...cars.map((c) => c.lap_time_s));
  if (AT.reducedMotion) {          // no animation: show the finished laps
    draw(duration);
    return;
  }

  // ---------------------------------------------------------------- playback loop (paused when off screen)
  let visible = true, start = null, raf = null;
  function frame(now) {
    if (start === null) start = now;
    let t = (now - start) / 1000;
    if (t > duration + HOLD_S) { start = now; t = 0; }
    draw(Math.min(t, duration));
    raf = visible ? requestAnimationFrame(frame) : null;
  }
  new IntersectionObserver((entries) => {
    visible = entries[0].isIntersecting && !document.hidden;
    if (visible && raf === null) { start = null; raf = requestAnimationFrame(frame); }
  }).observe(document.getElementById("hero"));
  document.addEventListener("visibilitychange", () => {
    visible = !document.hidden;
    if (visible && raf === null) { start = null; raf = requestAnimationFrame(frame); }
  });
  raf = requestAnimationFrame(frame);
})();
